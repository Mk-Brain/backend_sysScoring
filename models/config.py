from datetime import date

from sqlalchemy import Boolean, Column, Date, Integer, String

from database.database import Base


class Parametre(Base):
    __tablename__ = "parametres"

    id = Column(Integer, primary_key=True)

    cle = Column(String(100), unique=True)
    valeur = Column(String(255))
    description = Column(String(255))
    actif = Column(Boolean, default=True)
    #section = Column(String(100), nullable=False)