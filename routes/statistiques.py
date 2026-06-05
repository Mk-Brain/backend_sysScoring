from datetime import date
import calendar

from fastapi import APIRouter, Depends, HTTPException

from services.auth import get_current_user
from database.database import get_db
from models.statistique import Statistique
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

