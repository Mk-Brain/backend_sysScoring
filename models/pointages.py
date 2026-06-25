import enum
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Time, Enum, Double
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from database.database import Base

class ScoringState(str, enum.Enum):
    ABSENT          = "absent"           # Jamais pointé
    PENDING         = "pending"         # Reconnaissance échouée
    PRESENT         = "present"          # 2 pointages réussis, à l'heure
    RETARD          = "retard"           # 1er pointage après 8h, en attente du 2ème
    


class Pointage(Base):
    __tablename__ = "pointages"

    id = Column(Integer, primary_key=True)

    date_day = Column(Date, nullable=False, default=date.today())

    heure_arrive = Column(Time, nullable=True)
    heure_depart = Column(Time, nullable=True)

    minutes_travail = Column(Integer, default=0)

    minutes_sup = Column(Integer, default=0)

    numero_pointage = Column(Integer, default=0, nullable=False)

    distance_arrivee = Column(Double, default=1) #distance entre les visages
    distance_depart = Column(Double, default=1)

    status_arrivee = Column(
        Enum(ScoringState),
        default=ScoringState.ABSENT
    )
    status_depart = Column(
        Enum(ScoringState),
        default=ScoringState.PRESENT
    )

    photo_pointage_arrivee = Column(String(100))
    photo_pointage_depart = Column(String(100))

    id_user = Column(
        Integer,
        ForeignKey("users.id")
    )

    users = relationship("Employe", back_populates="pointages")

    # Le raccourci magique pour Pydantic
    @hybrid_property
    def nom(self) -> str:
        if self.users:
            return self.users.nom
        return "Inconnu"
    
    @hybrid_property
    def photo_user(self) -> str:
        if self.users:
            return self.users.photo
        return "Inconnu"