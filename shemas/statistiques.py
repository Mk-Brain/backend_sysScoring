from datetime import date, time, datetime

from pydantic import BaseModel


class ModelResponseStats(BaseModel):
    id : int
    type_periode:  str | None = None
    date_debut:  date | None = None
    date_fin:  date | None = None
    nb_pesence:  int | None = None
    nb_absence:  int | None = None
    nb_retard:  int | None = None
    total_minutes_travail:  int | None = None
    total_minutes_sup:  int | None = None
    total_minutes_absence:  int | None = None
    id_user : int

    class Config:
        from_attributes = True