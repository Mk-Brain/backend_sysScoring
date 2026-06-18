from pydantic import BaseModel
from datetime import  date, time

class ModelScoring(BaseModel):
    id: int
    nom: str
    date_day: date
    heure_arrive: time | None = None
    heure_depart: time | None = None
    status_arrivee: str | None = None
    status_depart: str| None = None
    photo_pointage_arrivee: str | None = None
    photo_pointage_depart: str | None = None
    photo_user: str
    minutes_travail: int | None = None
    minutes_sup: int | None = None
    numero_pointage: int
    distance_arrivee: int| None = None
    distance_depart: int| None = None
    id_user: int

    class Config:
        from_attributes = True

class ChangeStatusPointageRequest(BaseModel):
    numero_pointage: int
    status: str