import json
from datetime import  datetime


from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse

from services.auth import get_current_user, verify_access_token
from database.database import get_db
from models.statistique import Statistique
from services.statitiques import prodige_statistique_employe, prodige_donnees_dashbord, prodige_donnees_rapport

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




@router.get("/stats_employe")
async def get_stats_employe_stream(
    token: str = Query(...),
    id_user: int = Query(...),
):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")

    return EventSourceResponse(prodige_statistique_employe(token, id_user))



"""Récupérer tous les pointages"""
@router.get("/dashbord")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_dashbord(token))




@router.get("/rapport")
async def get_repport_stream(
    token: str = Query(...),
    periode: str = Query(...),
    debut: str = Query(...),
    fin: str = Query(...),
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