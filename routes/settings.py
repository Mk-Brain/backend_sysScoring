from fastapi import APIRouter, Depends, HTTPException

from database.database import get_db
from models.config import Parametre
from models.employe import Employe
from services.Setting import update_cache_settings
from services.auth import get_current_user
from shemas.Setting import Setting, SettingResponsModel
from shemas.employe import RequestModelEmp
from utils.global_var import SettingApp

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)


@router.post("/set_settings")
async def add_settings(settings : list[Setting], current_user: Employe = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    with get_db() as db:
        for setting in settings:
            p = db.query(Parametre).filter(Parametre.cle == setting.cle).first()
            if p :
                p.valeur = setting.valeur
            else:
                param = Parametre(
                    cle = setting.cle,
                    valeur = setting.valeur,
                    description = setting.description,
                    actif = setting.actif,
                )
                db.merge(param)
        db.commit()
        update_cache_settings(db)
    return {"message" : "success"}

@router.get("/get_setting_list", response_model=list[SettingResponsModel])
async def get_settings(current_user: Employe = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    with get_db() as db:
       
        settings = db.query(Parametre).all()
    
    return settings

@router.get("/get_settings")
def get_settings_public(current_user: RequestModelEmp = Depends(get_current_user)):
    """Retourne les paramètres nécessaires au pointage côté mobile"""
    return {
        "HEURE_ARRIVEE": str(SettingApp.setting_cash.get("HEURE_ARRIVEE", "08:00:00")),
        "HEURE_DEPART": str(SettingApp.setting_cash.get("HEURE_DEPART", "16:00:00")),
        "HEURE_TOLEREE": str(SettingApp.setting_cash.get("HEURE_TOLEREE", "08:30:00")),
        "HEURE_LIMITE_AVANT_ABSENCE": str(SettingApp.setting_cash.get("HEURE_LIMITE_AVANT_ABSENCE", "09:00:00")),
        "HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE": str(SettingApp.setting_cash.get("HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE", "10:00:00")),
        "JOUNEE_TRAVAIL": str(SettingApp.setting_cash.get("JOUNEE_TRAVAIL", "08:00:00")),
    }