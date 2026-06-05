from pydantic import BaseModel
from datetime import  date, time

class ModelScoring(BaseModel):
    id: int
    date_day: date
    heure_arrive: time
    heure_depart: time
    status: str
    photo_pointage: str
    id_user: int

    class Config:
        from_attributes = True