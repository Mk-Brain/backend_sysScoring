import asyncio
import json
from datetime import date, timedelta
import calendar
from sqlalchemy import func


from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse

from services.auth import get_current_user, verify_access_token
from database.database import get_db
from models.statistique import Statistique
from models.pointages import Pointage, ScoringState
from models.employe import Employe
from models.demandes import DemandesInscription
from shemas.employe import RequestModelEmp
from shemas.statistiques import ModelResponseStats

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


@router.get("/my_stats", response_model=list[ModelResponseStats])
def get_statistiques(current_user: RequestModelEmp = Depends(get_current_user)):

    with get_db() as db:
        stats = (
            db.query(Statistique).filter(Statistique.id_user == current_user.id).all()
        )
    return stats


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
                if p.status
                in [
                    ScoringState.PRESENT,
                    ScoringState.RETARD_PRESENT,
                    ScoringState.PRESENT_PARTIEL,
                ]
            )
            retards_today = sum(
                1
                for p in pointages_today
                if p.status in [ScoringState.RETARD, ScoringState.RETARD_PRESENT]
            )
            absents_today = sum(
                1 for p in pointages_today if p.status == ScoringState.ABSENT
            )
            pointages_refuses_today = sum(
                1 for p in pointages_today if p.status == ScoringState.PENDING
            )

            # Compteurs d'hier
            presents_yesterday = sum(
                1
                for p in pointages_yesterday
                if p.status
                in [
                    ScoringState.PRESENT,
                    ScoringState.RETARD_PRESENT,
                    ScoringState.PRESENT_PARTIEL,
                ]
            )
            retards_yesterday = sum(
                1
                for p in pointages_yesterday
                if p.status in [ScoringState.RETARD, ScoringState.RETARD_PRESENT]
            )
            absents_yesterday = sum(
                1 for p in pointages_yesterday if p.status == ScoringState.ABSENT
            )
            pointages_refuses_yesterday = sum(
                1 for p in pointages_yesterday if p.status == ScoringState.PENDING
            )

            # ===== 2. ÉVOLUTIONS DE LA SEMAINE (7 JOURS) =====
            # GROSSE OPTIMISATION : Ta boucle d'origine exécutait 21 requêtes SQL (3 requêtes × 7 jours).
            # On réduit ça à UNE SEULE requête d'agrégation groupée par jour.
            week_end = week_start + timedelta(days=6)
            stats_week_brute = (
                db.query(
                    Pointage.date_day,
                    func.sum(
                        func.case(
                            whens=[
                                (
                                    Pointage.status.in_(
                                        [
                                            ScoringState.PRESENT,
                                            ScoringState.RETARD_PRESENT,
                                            ScoringState.PRESENT_PARTIEL,
                                        ]
                                    ),
                                    1,
                                )
                            ],
                            else_=0,
                        )
                    ).label("presents"),
                    func.sum(
                        func.case(
                            whens=[(Pointage.status == ScoringState.ABSENT, 1)], else_=0
                        )
                    ).label("absents"),
                    func.sum(
                        func.case(
                            whens=[
                                (
                                    Pointage.status.in_(
                                        [
                                            ScoringState.RETARD,
                                            ScoringState.RETARD_PRESENT,
                                        ]
                                    ),
                                    1,
                                )
                            ],
                            else_=0,
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
                        "jour": jours[i],
                        "valeur": int(day_data.absents or 0) if day_data else 0,
                    }
                )
                evolution_retards.append(
                    {
                        "jour": jours[i],
                        "valeur": int(day_data.retards or 0) if day_data else 0,
                    }
                )

            # ===== 3. LISTES ET SELECTIONS (Top 5, Recents, Absents) =====
            # Correction de la faille N+1 : Ajout de joinedload pour éviter que Python interroge la table User à chaque itération
            from sqlalchemy.orm import joinedload

            cinq_derniers = (
                db.query(Pointage)
                .options(joinedload(Pointage.users))
                .filter(Pointage.date_day == today)
                .order_by(Pointage.id.desc())
                .limit(5)
                .all()
            )
            cinq_derniers_pointages = [
                {
                    "nom": p.users.nom if p.users else "Inconnu",
                    "prenom": p.users.prenom if p.users else "",
                    "poste": p.users.poste if p.users and p.users.poste else "",
                    "heure": str(p.heure_arrive) if p.heure_arrive else "",
                    "status": p.status.value if p.status else "",
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
                    Pointage.status.in_(
                        [ScoringState.RETARD, ScoringState.RETARD_PRESENT]
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
                    Pointage.date_day == today, Pointage.status == ScoringState.ABSENT
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
                    Pointage.date_day == today, Pointage.status == ScoringState.PENDING
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
                if p.status
                in [
                    ScoringState.PRESENT,
                    ScoringState.RETARD_PRESENT,
                    ScoringState.PRESENT_PARTIEL,
                ]
            )
            presence_actuel = (
                (presents_month / len(month_pointages) * 100) if month_pointages else 0
            )

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
                if p.status
                in [
                    ScoringState.PRESENT,
                    ScoringState.RETARD_PRESENT,
                    ScoringState.PRESENT_PARTIEL,
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
        await asyncio.sleep(2)


"""Récupérer tous les pointages"""


@router.get("/dashbord")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_dashbord(token))


async def prodige_donnees_rapport(
    token: str, periode: str, date_deb: date, date_fin: date
):
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
                "actifs": 0,  # À dynamiser si un champ existe
                "inactifs": 0,
            }

            # ===== RESUME GLOBAL =====
            #  Correction : Le filtre d'origine était inversé (<= deb et >= fin)
            pointages_periode = (
                db.query(Pointage)
                .filter(Pointage.date_day >= date_deb, Pointage.date_day <= date_fin)
                .all()
            )

            presents = sum(
                1
                for p in pointages_periode
                if p.status
                in [
                    ScoringState.PRESENT,
                    ScoringState.RETARD_PRESENT,
                    ScoringState.PRESENT_PARTIEL,
                ]
            )
            retards = sum(
                1
                for p in pointages_periode
                if p.status in [ScoringState.RETARD, ScoringState.RETARD_PRESENT]
            )
            absents = sum(
                1 for p in pointages_periode if p.status == ScoringState.ABSENT
            )

            taux_presence = (
                (presents / len(pointages_periode) * 100) if pointages_periode else 0
            )

            resume_global = {
                "presences": presents,
                "absences": absents,
                "retards": retards,
                "taux_presence_global": taux_presence,
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
                    Pointage.status.in_(
                        [ScoringState.RETARD, ScoringState.RETARD_PRESENT]
                    ),
                )
                .group_by(Employe.id)
                .order_by(func.count(Pointage.id).desc())
                .limit(10)
                .all()
            )
            top__retards_periode = [
                {"nom": r[0], "prenom": r[1], "matricule": r[2], "retard": r[3]}
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
                    Pointage.status == ScoringState.ABSENT,
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
                    Pointage.status.in_(
                        [
                            ScoringState.PRESENT,
                            ScoringState.RETARD_PRESENT,
                            ScoringState.PRESENT_PARTIEL,
                        ]
                    ),
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
            emp = (
                db.query(
                    Employe.id,
                    Employe.nom,
                    Employe.prenom,
                    Employe.matricule,
                    Employe.poste,
                    func.group_concat(func.concat(Pointage.date_day, "")).label(
                        "jours_absence"
                    ),
                )
                .join(Pointage)
                .filter(
                    Pointage.date_day >= date_deb,
                    Pointage.date_day <= date_fin,
                    Pointage.status == ScoringState.ABSENT,
                )
                .group_by(Employe.id)
                .order_by(Employe.id)
                .all()
            )

            employes = [
                {
                    "id": e.id,
                    "matricule": e.matricule,
                    "nom": f"{e.nom} {e.prenom}",
                    "poste": e.poste,
                    "jours_absence": (
                        e.jours_absence.split(",") if e.jours_absence else []
                    ),
                    "statistiques": {},
                }
                for e in emp
            ]

            # LOGIQUE HYBRIDE : Étape 1 - Calcul du total théorique d'heures
            total = 0
            is_standard_periode = periode in ["hebdomadaire", "mensuelle", "annuel"]

            if is_standard_periode:
                if periode == "hebdomadaire":
                    total = 8 * 5
                elif periode == "mensuelle":
                    total = 8 * 22
                elif periode == "annuel":
                    total = 8 * 22 * 12
            else:
                # Calcul de la période personnalisée en jours réels
                delta = date_fin - date_deb
                nb_jours = max(delta.days + 1, 0)
                total = 8 * nb_jours

            # LOGIQUE HYBRIDE : Étape 2 - Sélection de la source des statistiques
            stats_mapping = {}

            if is_standard_periode:
                # CAS A : Période standard -> Lecture depuis la table Statistique
                stats_emp = (
                    db.query(
                        Statistique.id_user,
                        Statistique.nb_presence,
                        Statistique.nb_absence,
                        Statistique.nb_retard,
                        Statistique.total_minutes_travail / 60,
                        Statistique.total_minutes_sup / 60,
                    )
                    .filter(
                        Statistique.type_periode == periode,
                        Statistique.date_debut == date_deb,
                        Statistique.date_fin == date_fin,
                    )
                    .all()
                )
                stats_mapping = {
                    st[0]: {
                        "presences": st[1],
                        "absences": st[2],
                        "retards": st[3],
                        "taux_presence": (st[1] / total) * 100 if total > 0 else 0,
                        "heures_travail": st[4],
                        "heures_supplementaires": st[5],
                    }
                    for st in stats_emp
                }
            else:
                # CAS B : Période personnalisée -> Calcul à la volée sur la table Pointage
                stats_dynamiques = (
                    db.query(
                        Pointage.id_user,
                        func.sum(
                            func.case(
                                whens=[
                                    (
                                        Pointage.status.in_(
                                            [
                                                ScoringState.PRESENT,
                                                ScoringState.RETARD_PRESENT,
                                                ScoringState.PRESENT_PARTIEL,
                                            ]
                                        ),
                                        1,
                                    )
                                ],
                                else_=0,
                            )
                        ),
                        func.sum(
                            func.case(
                                whens=[(Pointage.status == ScoringState.ABSENT, 1)],
                                else_=0,
                            )
                        ),
                        func.sum(
                            func.case(
                                whens=[
                                    (
                                        Pointage.status.in_(
                                            [
                                                ScoringState.RETARD,
                                                ScoringState.RETARD_PRESENT,
                                            ]
                                        ),
                                        1,
                                    )
                                ],
                                else_=0,
                            )
                        ),
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
                stats_mapping = {
                    st[0]: {
                        "presences": int(st[1] or 0),
                        "absences": int(st[2] or 0),
                        "retards": int(st[3] or 0),
                        "taux_presence": (
                            (int(st[1] or 0) / total) * 100 if total > 0 else 0
                        ),
                        "heures_travail": float(st[4] or 0.0),
                        "heures_supplementaires": float(st[5] or 0.0),
                    }
                    for st in stats_dynamiques
                }

            # LOGIQUE HYBRIDE : Étape 3 - Injection sécurisée par ID
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

            # ===== EVOLUTION CHRONOLOGIQUE (Pour ton graphique Frontend) =====
            #  Correction : Remplacement des syntaxes cassées par du SQL CASE WHEN valide
            evolution_brute = (
                db.query(
                    Pointage.date_day,
                    func.sum(
                        func.case(
                            whens=[
                                (
                                    Pointage.status.in_(
                                        [
                                            ScoringState.PRESENT,
                                            ScoringState.RETARD_PRESENT,
                                            ScoringState.PRESENT_PARTIEL,
                                        ]
                                    ),
                                    1,
                                )
                            ],
                            else_=0,
                        )
                    ).label("presents"),
                    func.sum(
                        func.case(
                            whens=[(Pointage.status == ScoringState.ABSENT, 1)], else_=0
                        )
                    ).label("absents"),
                    func.sum(
                        func.case(
                            whens=[
                                (
                                    Pointage.status.in_(
                                        [
                                            ScoringState.RETARD,
                                            ScoringState.RETARD_PRESENT,
                                        ]
                                    ),
                                    1,
                                )
                            ],
                            else_=0,
                        )
                    ).label("retards"),
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
        await asyncio.sleep(2)


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

    return EventSourceResponse(prodige_donnees_rapport(token, periode, debut, fin))
