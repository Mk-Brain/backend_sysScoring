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


@router.get("/", response_model=list[ModelResponseStats])
def get_statistiques(current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Authorization required")
    with get_db() as db:
        stats = db.query(Statistique).all()
    return stats

@router.get("/my_stats", response_model=list[ModelResponseStats])
def get_statistiques(current_user: RequestModelEmp = Depends(get_current_user)):

    with get_db() as db:
        stats = db.query(Statistique).filter(Statistique.id_user == current_user.id).all()
    return stats



async def prodige_donnees(token: str):
    while True:
        # ✅ Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            # ✅ Envoyer un événement spécial au lieu de crasher
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            today = date.today()
            yesterday = today - timedelta(days=1)
            week_start = today - timedelta(days=6)
            
            # ===== STATS DU JOUR =====
            pointages_today = db.query(Pointage).filter(Pointage.date_day == today).all()
            total_employes = db.query(Employe).count()
            presents_today = sum(1 for p in pointages_today if p.status in [ScoringState.PRESENT, ScoringState.RETARD_PRESENT])
            retards_today = sum(1 for p in pointages_today if p.status in [ScoringState.RETARD, ScoringState.RETARD_PRESENT])
            absents_today = sum(1 for p in pointages_today if p.status == ScoringState.ABSENT)
            pointages_refuses_today = sum(1 for p in pointages_today if p.status == ScoringState.PENDING)
            
            # ===== STATS DU JOUR PRÉCÉDENT =====
            pointages_yesterday = db.query(Pointage).filter(Pointage.date_day == yesterday).all()
            presents_yesterday = sum(1 for p in pointages_yesterday if p.status in [ScoringState.PRESENT, ScoringState.RETARD_PRESENT])
            retards_yesterday = sum(1 for p in pointages_yesterday if p.status in [ScoringState.RETARD, ScoringState.RETARD_PRESENT])
            absents_yesterday = sum(1 for p in pointages_yesterday if p.status == ScoringState.ABSENT)
            pointages_refuses_yesterday = sum(1 for p in pointages_yesterday if p.status == ScoringState.PENDING)
            
            # ===== ÉVOLUTION PRESENCES (7 DERNIERS JOURS) =====
            evolution_presences = []
            jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            for i in range(7):
                day = today - timedelta(days=6-i)
                count = db.query(Pointage).filter(
                    Pointage.date_day == day,
                    Pointage.status.in_([ScoringState.PRESENT, ScoringState.RETARD_PRESENT])
                ).count()
                evolution_presences.append({"day": jours[i], "value": count})
            
            # ===== ÉVOLUTION ABSENCES (7 DERNIERS JOURS) =====
            evolution_absences = []
            for i in range(7):
                day = today - timedelta(days=6-i)
                count = db.query(Pointage).filter(
                    Pointage.date_day == day,
                    Pointage.status == ScoringState.ABSENT
                ).count()
                evolution_absences.append({"jour": jours[i], "valeur": count})
            
            # ===== ÉVOLUTION RETARDS (7 DERNIERS JOURS) =====
            evolution_retards = []
            for i in range(7):
                day = today - timedelta(days=6-i)
                count = db.query(Pointage).filter(
                    Pointage.date_day == day,
                    Pointage.status.in_([ScoringState.RETARD, ScoringState.RETARD_PRESENT])
                ).count()
                evolution_retards.append({"jour": jours[i], "valeur": count})
            
            # ===== 5 DERNIERS POINTAGES DU JOUR =====
            cinq_derniers = db.query(Pointage).filter(
                Pointage.date_day == today
            ).order_by(Pointage.id.desc()).limit(5).all()
            
            cinq_derniers_pointages = [
                {
                    "nom": p.users.nom,
                    "prenom": p.users.prenom,
                    "poste": p.users.poste or "",
                    "heure": str(p.heure_arrive) if p.heure_arrive else "",
                    "status": p.status.value
                }
                for p in cinq_derniers
            ]
            
            # ===== TOP 5 RETARDS DE LA SEMAINE =====
            retards_week = db.query(
                Employe.nom,
                Employe.prenom,
                func.count(Pointage.id).label('nb_retard')
            ).join(Pointage).filter(
                Pointage.date_day >= week_start,
                Pointage.date_day <= today,
                Pointage.status.in_([ScoringState.RETARD, ScoringState.RETARD_PRESENT])
            ).group_by(Employe.id).order_by(func.count(Pointage.id).desc()).limit(5).all()
            
            top_cinq_retards_semaine = [
                {
                    "nom": r[0],
                    "prenom": r[1],
                    "nb_retard": r[2]
                }
                for r in retards_week
            ]
            
            # ===== ABSENTS DU JOUR =====
            absents_du_jour_list = db.query(Pointage).filter(
                Pointage.date_day == today,
                Pointage.status == ScoringState.ABSENT
            ).all()
            
            absents_du_jour = [
                {
                    "nom": p.users.nom,
                    "prenom": p.users.prenom,
                    "poste": p.users.poste or ""
                }
                for p in absents_du_jour_list
            ]
            
            # ===== NOTIFICATIONS =====
            inscriptions_attente = db.query(DemandesInscription).filter(
                DemandesInscription.status == 'pending'
            ).count()
            
            pointages_invalides = db.query(Pointage).filter(
                Pointage.date_day == today,
                Pointage.status == ScoringState.PENDING
            ).count()
            
            # ===== POURCENTAGE PRESENCE =====
            # Mois actuel
            month_start = today.replace(day=1)
            month_pointages = db.query(Pointage).filter(
                Pointage.date_day >= month_start,
                Pointage.date_day <= today
            ).all()
            presence_actuel = (
                sum(1 for p in month_pointages if p.status in [ScoringState.PRESENT, ScoringState.RETARD_PRESENT]) / len(month_pointages) * 100
                if month_pointages else 0
            )
            
            # Mois précédent
            last_month_end = month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            month_precedent_pointages = db.query(Pointage).filter(
                Pointage.date_day >= last_month_start,
                Pointage.date_day <= last_month_end
            ).all()
            presence_precedent = (
                sum(1 for p in month_precedent_pointages if p.status in [ScoringState.PRESENT, ScoringState.RETARD_PRESENT]) / len(month_precedent_pointages) * 100
                if month_precedent_pointages else 0
            )
            
            payload = {
                "stats_jour": {
                    "total_employes": total_employes,
                    "presents": presents_today,
                    "retards": retards_today,
                    "absents": absents_today,
                    "pointages_refuses": pointages_refuses_today
                },
                "stats_jour_precedent": {
                    "total_employes": total_employes,
                    "presents": presents_yesterday,
                    "retards": retards_yesterday,
                    "absents": absents_yesterday,
                    "pointages_refuses": pointages_refuses_yesterday
                },
                "evolution_presences": evolution_presences,
                "evolution_absences": evolution_absences,
                "evolution_retards": evolution_retards,
                "repartition": {
                    "presents": presents_today,
                    "retards": retards_today,
                    "absents": absents_today
                },
                "cinq_derniers_pointages": cinq_derniers_pointages,
                "top_cinq_retards_semaine": top_cinq_retards_semaine,
                "absents_du_jour": absents_du_jour,
                "notification": {
                    "inscriptions_attente": inscriptions_attente,
                    "pointages_invalide": pointages_invalides
                },
                "pourcentage_presence": {
                    "mois_actuel": round(presence_actuel, 2),
                    "mois_precedent": round(presence_precedent, 2)
                }
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

    return EventSourceResponse(prodige_donnees(token))