import enum
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Time, Enum
from sqlalchemy.orm import relationship

from database.database import Base

class ScoringState(str, enum.Enum):
    ABSENT          = "absent"           # Jamais pointé
    PENDING         = "pending"          # Reconnaissance échouée
    PRESENT_PARTIEL = "present_partiel"  # 1er pointage validé, en attente du 2ème
    PRESENT         = "present"          # 2 pointages réussis, à l'heure
    RETARD          = "retard"           # 1er pointage après 8h, en attente du 2ème
    RETARD_PRESENT  = "retard_present"   # 2 pointages réussis, arrivée en retard

class Pointage(Base):
    __tablename__ = "pointages"

    id = Column(Integer, primary_key=True)

    date_day = Column(Date, nullable=False, default=date.today())

    heure_arrive = Column(Time, nullable=True)
    heure_depart = Column(Time, nullable=True)

    heure_travail = Column(Integer, default=0)

    status = Column(
        Enum(ScoringState),
        default=ScoringState.ABSENT
    )

    photo_pointage = Column(String(100))

    id_user = Column(
        Integer,
        ForeignKey("users.id")
    )

    users = relationship("Employe", back_populates="pointages")