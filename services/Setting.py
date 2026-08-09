from datetime import datetime

from sqlalchemy.orm import Session

from models.config import Parametre
from utils.global_var import SettingApp


def get_settings(db: Session):
    settings = (
        db.query(Parametre.cle, Parametre.valeur)
        .filter(Parametre.actif == True) 
        .all()
    )
    SettingApp.setting_cash = {
        cle: datetime.strptime(valeur, "%H:%M:%S") .time()
        for cle, valeur in settings
    }

def update_cache_settings(db: Session):
    settings = (
        db.query(Parametre.cle, Parametre.valeur)
        .filter(Parametre.actif == True) 
        .all()
    )
    SettingApp.setting_cash = {cle: datetime.strptime(valeur, "%H:%M:%S") .time() for cle, valeur in settings}