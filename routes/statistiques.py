import asyncio
import json
from datetime import date, timedelta, datetime
import calendar
from sqlalchemy import func, or_, case

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse

from sqlalchemy.orm import joinedload

from services.auth import get_current_user, verify_access_token
from database.database import get_db
from models.statistique import Statistique
from models.pointages import Pointage, ScoringState
from models.employe import Employe
from models.demandes import DemandesInscription
from shemas.employe import RequestModelEmp
from shemas.statistiques import ModelResponseStats
from utils.global_var import SettingApp
from collections import defaultdict
router = APIRouter(
    prefix="/statistiques",
    tags=["statistiques"],
)

"recuperer toutes le données de statistiques des employés"
@router.get("/", response_model=list[ModelResponseStats])
def get_statistiques(current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Authorization required")
    with get_db() as db:
        stats = db.query(Statistique).all()
    return stats


"récuperer les statistiques d'de l'utilisateur connecter"


def get_period_bounds(type_periode: str) -> tuple[date, date]:
    """Calcule les bornes de la période en cours"""
    today = date.today()

    if type_periode == "hebdomadaire":
        debut = today - timedelta(days=calendar.weekday(today.year, today.month, today.day))
        fin = debut + timedelta(days=6)
    elif type_periode == "mensuelle":
        debut = today.replace(day=1)
        fin = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    elif type_periode == "annuel":
        debut = date(today.year, 1, 1)
        fin = date(today.year, 12, 31)
    else:
        raise ValueError("type_periode invalide (hebdomadaire | mensuelle | annuel)")

    return debut, fin


async def prodige_statistique_employe(token: str, id_user: int):
    while True:
        user = verify_access_token(token)
        if user is None:
            yield f"event: token_expired\ndata: {{}}\n\n"
            break

        periodes = ["hebdomadaire", "mensuelle", "annuel"]

        with get_db() as db:
            resultats = []

            for type_periode in periodes:
                date_debut, date_fin = get_period_bounds(type_periode)

                result = (
                    db.query(
                        func.sum(case((Pointage.status_arrivee == ScoringState.PRESENT, 1), else_=0)),
                        func.sum(case((Pointage.status_arrivee == ScoringState.ABSENT, 1), else_=0)),
                        func.sum(case((Pointage.status_arrivee == ScoringState.RETARD, 1), else_=0)),
                        func.sum(Pointage.minutes_travail),
                        func.sum(Pointage.minutes_sup),
                    )
                    .filter(
                        Pointage.id_user == id_user,
                        Pointage.date_day >= date_debut,
                        Pointage.date_day <= date_fin,
                    )
                    .first()
                )

                nb_presence, nb_absence, nb_retard, total_minutes_travail, total_minutes_sup = (
                    int(result[0] or 0),
                    int(result[1] or 0),
                    int(result[2] or 0),
                    int(result[3] or 0),
                    int(result[4] or 0),
                )

                resultats.append({
                    "id": 0,
                    "type_periode": type_periode,
                    "date_debut": str(date_debut),
                    "date_fin": str(date_fin),
                    "nb_presence": nb_presence,
                    "nb_absence": nb_absence,
                    "nb_retard": nb_retard,
                    "total_minutes_travail": total_minutes_travail,
                    "total_minutes_sup": total_minutes_sup,
                    "total_minutes_absence": 0,
                    "id_user": id_user,
                })

        yield f"data: {json.dumps(resultats, ensure_ascii=False)}\n\n"
        await asyncio.sleep(30)


@router.get("/stats_employe")
async def get_stats_employe_stream(
    token: str = Query(...),
    id_user: int = Query(...),
):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")

    return EventSourceResponse(prodige_statistique_employe(token, id_user))








"""fornisseur de données pour le dashbord"""
async def prodige_donnees_dashbord(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            today = date.today()
            yesterday = today - timedelta(days=1)

            # Correction de la syntaxe de week_start (il y avait une virgule traîner à la fin créant un tuple)
            week_start = date(
                today.year,
                today.month,
                today.day - calendar.weekday(today.year, today.month, today.day),
            )

            # ===== 1. EFFECTIF & STATS COMPTEURS (Aujourd'hui et Hier) =====
            total_employes = db.query(Employe).count()

            # OPTIMISATION : On récupère les pointages d'aujourd'hui ET d'hier en UNE SEULE requête
            pointages_deux_jours = (
                db.query(Pointage)
                .filter(Pointage.date_day.in_([today, yesterday]))
                .all()
            )

            # Séparation en mémoire pour alléger la base de données
            pointages_today = [p for p in pointages_deux_jours if p.date_day == today]
            pointages_yesterday = [
                p for p in pointages_deux_jours if p.date_day == yesterday
            ]

            # Compteurs d'aujourd'hui
            presents_today = sum(
                1
                for p in pointages_today
                if p.status_arrivee
                in [
                    ScoringState.PRESENT,

                ]
            )
            
            retards_today = sum(
                1
                for p in pointages_today
                if p.status_arrivee in [ScoringState.RETARD]
            )
            
            absents_today = sum(
                1 for p in pointages_today if p.status_arrivee == ScoringState.ABSENT
            )

            pointages_refuses_today = sum(
                1 for p in pointages_today if p.status_arrivee == ScoringState.PENDING
            )

            # Compteurs d'hier
            presents_yesterday = sum(
                1
                for p in pointages_yesterday
                if p.status_arrivee
                in [
                    ScoringState.PRESENT,
                  
                ]
            )
            
            retards_yesterday = sum(
                1
                for p in pointages_yesterday
                if p.status_arrivee in [ScoringState.RETARD]
            )
            
            absents_yesterday = sum(
                1 for p in pointages_yesterday if p.status_arrivee == ScoringState.ABSENT
            )
            pointages_refuses_yesterday = sum(
                1 for p in pointages_yesterday if p.status_arrivee == ScoringState.PENDING
            )

            # ===== 2. ÉVOLUTIONS DE LA SEMAINE (7 JOURS) =====
            # GROSSE OPTIMISATION : Ta boucle d'origine exécutait 21 requêtes SQL (3 requêtes × 7 jours).
            # On réduit ça à UNE SEULE requête d'agrégation groupée par jour.
            week_end = week_start + timedelta(days=6)
            
            stats_week_brute = (
                db.query(
                    Pointage.date_day,
                    func.sum(
                        case(
                                (Pointage.status_arrivee.in_([ScoringState.PRESENT]),1,),
                            else_=0,
                        )
                    ).label("presents"),
                    func.sum(
                        case(
                            (Pointage.status_arrivee == ScoringState.ABSENT, 1), else_=0
                        )
                    ).label("absents"),
                    func.sum(
                        case(
                                (Pointage.status_arrivee.in_([ScoringState.RETARD,]),1,),else_=0,
                        )
                    ).label("retards"),
                )
                .filter(Pointage.date_day >= week_start, Pointage.date_day <= week_end)
                .group_by(Pointage.date_day)
                .all()
            )

            # Transformation des résultats bruts en dictionnaires pour un accès O(1)
            week_mapping = {row.date_day: row for row in stats_week_brute}

            evolution_presences = []
            evolution_absences = []
            evolution_retards = []
            jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

            for i in range(7):
                current_day = week_start + timedelta(days=i)
                day_data = week_mapping.get(current_day)

                evolution_presences.append(
                    {
                        "day": jours[i],
                        "value": int(day_data.presents or 0) if day_data else 0,
                    }
                )
                evolution_absences.append(
                    {
                        "day": jours[i],
                        "value": int(day_data.absents or 0) if day_data else 0,
                    }
                )
                evolution_retards.append(
                    {
                        "day": jours[i],
                        "value": int(day_data.retards or 0) if day_data else 0,
                    }
                )

            # ===== 3. LISTES ET SELECTIONS (Top 5, Recents, Absents) =====
            # Correction de la faille N+1 : Ajout de joinedload pour éviter que Python interroge la table User à chaque itération
            

            cinq_derniers = (
                db.query(Pointage)
                .options(joinedload(Pointage.users))
                .filter(Pointage.date_day == today)
                .order_by(Pointage.heure_arrive.desc())
                .limit(5)
                .all()
            )
           
            cinq_derniers_pointages = [
                {
                    "nom": p.users.nom if p.users else "Inconnu",
                    "prenom": p.users.prenom if p.users else "",
                    "poste": p.users.poste if p.users and p.users.poste else "",
                    "heure": str(p.heure_arrive) if p.heure_arrive else "",
                    "status": p.status_arrivee.value if p.status_arrivee else "",
                }
                for p in cinq_derniers
            ]

            # Top 5 Retards de la semaine
            retards_week = (
                db.query(
                    Employe.nom,
                    Employe.prenom,
                    func.count(Pointage.id).label("nb_retard"),
                )
                .join(Pointage)
                .filter(
                    Pointage.date_day >= week_start,
                    Pointage.date_day <= today,
                    Pointage.status_arrivee.in_(
                        [ScoringState.RETARD]
                    ),
                )
                .group_by(Employe.id)
                .order_by(func.count(Pointage.id).desc())
                .limit(5)
                .all()
            )
            
            top_cinq_retards_semaine = [
                {"nom": r[0], "prenom": r[1], "nb_retard": r[2]} for r in retards_week
            ]

            # Absents du jour
            absents_du_jour_list = (
                db.query(Pointage)
                .options(joinedload(Pointage.users))
                .filter(
                    Pointage.date_day == today, Pointage.status_arrivee == ScoringState.ABSENT
                )
                .all()
            )
            
            absents_du_jour = [
                {
                    "nom": p.users.nom if p.users else "Inconnu",
                    "prenom": p.users.prenom if p.users else "",
                    "poste": p.users.poste if p.users and p.users.poste else "",
                }
                for p in absents_du_jour_list
            ]

            # ===== 4. COUNTERS NOTIFICATIONS =====
            inscriptions_attente = (
                db.query(DemandesInscription)
                .filter(DemandesInscription.status == "pending")
                .count()
            )
           
            pointages_invalides = (
                db.query(Pointage)
                .filter(
                    Pointage.date_day == today,
                    or_(
                        Pointage.status_arrivee == ScoringState.PENDING,
                        Pointage.status_depart == ScoringState.PENDING
                    )
                )
                .count()
            )

            # ===== 5. CALCULS DES POURCENTAGES (Mois Actuel VS Précédent) =====
            # Mois actuel
            month_start = today.replace(day=1)
            month_pointages = (
                db.query(Pointage)
                .filter(Pointage.date_day >= month_start, Pointage.date_day <= today)
                .all()
            )

            presents_month = sum(
                1
                for p in month_pointages
                if p.status_arrivee
                in [
                    ScoringState.PRESENT,
                ]
            )

            presence_actuel = round(presents_month / len(month_pointages) * 100, 2) if month_pointages else 0

            # Mois précédent
            last_month_end = month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            
            month_precedent_pointages = (
                db.query(Pointage)
                .filter(
                    Pointage.date_day >= last_month_start,
                    Pointage.date_day <= last_month_end,
                )
                .all()
            )

            presents_last_month = sum(
                1
                for p in month_precedent_pointages
                if p.status_arrivee
                in [
                    ScoringState.PRESENT,
                ]
            )
            
            presence_precedent = (
                (presents_last_month / len(month_precedent_pointages) * 100)
                if month_precedent_pointages
                else 0
            )

            # ===== 6. ENVOI DU PAYLOAD =====
            payload = {
                "stats_jour": {
                    "total_employes": total_employes,
                    "presents": presents_today,
                    "retards": retards_today,
                    "absents": absents_today,
                    "pointages_refuses": pointages_refuses_today,
                },
                "stats_jour_precedent": {
                    "total_employes": total_employes,
                    "presents": presents_yesterday,
                    "retards": retards_yesterday,
                    "absents": absents_yesterday,
                    "pointages_refuses": pointages_refuses_yesterday,
                },
                "evolution_presences": evolution_presences,
                "evolution_absences": evolution_absences,
                "evolution_retards": evolution_retards,
                "repartition": {
                    "presents": presents_today,
                    "retards": retards_today,
                    "absents": absents_today,
                },
                "cinq_derniers_pointages": cinq_derniers_pointages,
                "top_cinq_retards_semaine": top_cinq_retards_semaine,
                "absents_du_jour": absents_du_jour,
                "notification": {
                    "inscriptions_attente": inscriptions_attente,
                    "pointages_invalide": pointages_invalides,
                },
                "pourcentage_presence": {
                    "mois_actuel": round(presence_actuel, 2),
                    "mois_precedent": round(presence_precedent, 2),
                },
            }

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(5)



"""Récupérer tous les pointages"""
@router.get("/dashbord")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_dashbord(token))

def nb_jours_total(date_deb: date, date_fin: date) -> int:
    """Compte tous les jours entre deux dates, week-ends inclus"""
    if date_deb > date_fin:
        return 0
    return (date_fin - date_deb).days + 1

"""fornisseur de données pour le rapport"""
async def prodige_donnees_rapport(
    token: str, periode: str, date_deb: date, date_fin: date
):
    date_deb = date_deb + timedelta(days=1)
    date_fin = date_fin + timedelta(days=1)
    nb_jours = nb_jours_ouvrables(date_deb, date_fin)

    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        if not date_deb or not date_fin:
            yield f"event: periode indefinie\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            # ====== TOTAL EMP =================
            effectif = {
                "total_employes": db.query(Employe).count(),
                "actifs": db.query(Employe).filter(Employe.status == "actif").count(),
                "inactifs": db.query(Employe).filter(Employe.status == "inactif").count(),
                "nb_jours": nb_jours
            }

            # ===== RESUME GLOBAL =====
            result = db.query(
                func.sum(case((Pointage.status_arrivee == ScoringState.PRESENT, 1), else_=0)),
                func.sum(case((Pointage.status_arrivee == ScoringState.RETARD, 1), else_=0)),
                func.sum(case((Pointage.status_arrivee == ScoringState.ABSENT, 1), else_=0)),
                func.count(Pointage.id)
            ).filter(Pointage.date_day >= date_deb, Pointage.date_day <= date_fin).first()

            presents, retards, absents, total_count = result
            presents = int(presents or 0)
            retards = int(retards or 0)
            absents = int(absents or 0)
            total_count = int(total_count or 0)

            # Taux de présence global = présences + retards (les deux sont des présences effectives)
            taux_presence_global = (
                ((presents + retards) / total_count * 100) if total_count else 0
            )

            resume_global = {
                "presences": presents,
                "absences": absents,
                "retards": retards,
                "taux_presence_global": round(taux_presence_global, 2),
            }

            # ===== TOP 10 RETARDS =====
            retards_periode = (
                db.query(
                    Employe.nom,
                    Employe.prenom,
                    Employe.matricule,
                    func.count(Pointage.id).label("retards"),
                )
                .join(Pointage)
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                    Pointage.status_arrivee.in_([ScoringState.RETARD]),
                )
                .group_by(Employe.id)
                .order_by(func.count(Pointage.id).desc())
                .limit(10)
                .all()
            )
            top__retards_periode = [
                {"nom": r[0], "prenom": r[1], "matricule": r[2], "retards": r[3]}
                for r in retards_periode
            ]

            # ===== TOP 10 ABSENCES =====
            absents_periode = (
                db.query(
                    Employe.nom,
                    Employe.prenom,
                    Employe.matricule,
                    func.count(Pointage.id).label("absences"),
                )
                .join(Pointage)
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                    Pointage.status_arrivee == ScoringState.ABSENT,
                )
                .group_by(Employe.id)
                .order_by(func.count(Pointage.id).desc())
                .limit(10)
                .all()
            )
            top__absents_periode = [
                {"nom": r[0], "prenom": r[1], "matricule": r[2], "absences": r[3]}
                for r in absents_periode
            ]

            # ===== TOP 10 PRESENCES =====
            presents_periode = (
                db.query(
                    Employe.nom,
                    Employe.prenom,
                    Employe.matricule,
                    func.count(Pointage.id).label("presences"),
                )
                .join(Pointage)
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                    Pointage.status_arrivee.in_([ScoringState.PRESENT]),
                )
                .group_by(Employe.id)
                .order_by(func.count(Pointage.id).desc())
                .limit(10)
                .all()
            )
            top__presents_periode = [
                {"nom": r[0], "prenom": r[1], "matricule": r[2], "presences": r[3]}
                for r in presents_periode
            ]

            # ===== LISTE DES EMPLOYES & ABSENCES PRECISES =====
            tous_les_employes = db.query(Employe).order_by(Employe.id).all()

            absences_brutes = (
                db.query(Pointage.id_user, Pointage.date_day)
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                    Pointage.status_arrivee == ScoringState.ABSENT,
                )
                .all()
            )


            absences_mapping = defaultdict(list)
            for absence in absences_brutes:
                absences_mapping[absence.id_user].append(str(absence.date_day))

            employes = [
                {
                    "id": e.id,
                    "matricule": e.matricule,
                    "nom": f"{e.nom} {e.prenom}",
                    "poste": e.poste or "",
                    "jours_absence": absences_mapping.get(e.id, []),
                    "statistiques": {},
                }
                for e in tous_les_employes
            ]

            # ===== STATISTIQUES PAR EMPLOYÉ =====
            stats_dynamiques = (
                db.query(
                    Pointage.id_user,
                    func.sum(case((Pointage.status_arrivee.in_([ScoringState.PRESENT]), 1), else_=0)),
                    func.sum(case((Pointage.status_arrivee == ScoringState.ABSENT, 1), else_=0)),
                    func.sum(case((Pointage.status_arrivee.in_([ScoringState.RETARD]), 1), else_=0)),
                    func.sum(Pointage.minutes_travail / 60),
                    func.sum(Pointage.minutes_sup / 60),
                )
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                )
                .group_by(Pointage.id_user)
                .all()
            )

            stats_mapping = {}
            for st in stats_dynamiques:
                emp_presences = int(st[1] or 0)
                emp_retards = int(st[3] or 0)

                #  Taux de présence employé = présences + retards / jours ouvrables
                taux_emp = (
                    ((emp_presences + emp_retards) / nb_jours * 100) if nb_jours > 0 else 0
                )

                stats_mapping[st[0]] = {
                    "presences": emp_presences,
                    "absences": int(st[2] or 0),
                    "retards": emp_retards,
                    "taux_presence": round(taux_emp, 2),
                    "heures_travail": round(float(st[4] or 0), 2),
                    "heures_supplementaires": round(float(st[5] or 0), 2),
                }

            for emp_dict in employes:
                emp_dict["statistiques"] = stats_mapping.get(
                    emp_dict["id"],
                    {
                        "presences": 0,
                        "absences": 0,
                        "retards": 0,
                        "taux_presence": 0,
                        "heures_travail": 0,
                        "heures_supplementaires": 0,
                    },
                )

            # ===== EVOLUTION CHRONOLOGIQUE =====
            evolution_brute = (
                db.query(
                    Pointage.date_day,
                    func.sum(case((Pointage.status_arrivee.in_([ScoringState.PRESENT]), 1), else_=0)).label("presents"),
                    func.sum(case((Pointage.status_arrivee == ScoringState.ABSENT, 1), else_=0)).label("absents"),
                    func.sum(case((Pointage.status_arrivee.in_([ScoringState.RETARD]), 1), else_=0)).label("retards"),
                )
                .filter(Pointage.date_day >= date_deb, Pointage.date_day <= date_fin)
                .group_by(Pointage.date_day)
                .order_by(Pointage.date_day)
                .all()
            )

            evolution = [
                {
                    "date": str(point.date_day),
                    "presents": int(point.presents or 0),
                    "absents": int(point.absents or 0),
                    "retards": int(point.retards or 0),
                }
                for point in evolution_brute
            ]

            # ===== ASSEMBLAGE DU PAYLOAD =====
            payload = {
                "periode": {
                    "type": periode,
                    "date_debut": str(date_deb),
                    "date_fin": str(date_fin),
                },
                "effectif": effectif,
                "resume_global": resume_global,
                "top_absences": top__absents_periode,
                "top_retards": top__retards_periode,
                "top_presences": top__presents_periode,
                "employes": employes,
                "evolution": evolution,
            }

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(10)



def nb_jours_ouvrables(date_deb, date_fin):
    """Compte les jours du lundi au vendredi entre deux dates"""
    count = 0
    while date_deb <= date_fin:
        if date_deb.weekday() < 5:  # 0=Lundi, 4=Vendredi
            count += 1
        date_deb += timedelta(days=1)
    return count

@router.get("/rapport")
async def get_repport_stream(
    token: str = Query(...),
    periode: str = Query(...),
    debut: str = Query(...),
    fin: str = Query,
):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_rapport(token, periode, datetime.strptime(debut, "%Y-%m-%d").date(), datetime.strptime(fin, "%Y-%m-%d").date()))



from decimal import Decimal

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)