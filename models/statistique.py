from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship

from database.database import Base


class Statistique(Base):
    __tablename__ = "statistiques"

    id = Column(Integer, primary_key=True)

    type_periode = Column(String(20))

    date_debut = Column(Date)
    date_fin = Column(Date)

    nb_presence = Column(Integer, default=0)
    nb_absence = Column(Integer, default=0)
    nb_retard = Column(Integer, default=0)

    total_minutes_travail = Column(Integer, default=0)
    total_minutes_sup = Column(Integer, default=0)
    total_minutes_absence = Column(Integer, default=0)

    id_user = Column(Integer, ForeignKey("users.id"))

    users = relationship(
        "Employe",
        back_populates="statistiques"
    )