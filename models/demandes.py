import enum
from datetime import  date, time

from sqlalchemy import Column, Integer, String, Enum, Date, Time

from database.database import Base

class Sexe(str, enum.Enum):
    MASCULIN = "MASCULIN"
    FEMININ = "FEMININ"

class DemandesInscription(Base):
    __tablename__ = "inscritions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(30), nullable=False)
    prenom = Column(String(30), nullable=False)
    sexe = Column(Enum(Sexe), nullable=False)
    matricule = Column(String(6), unique=True)
    email = Column(String(50), unique=True)
    telephone = Column(String(12), unique=True)
    photo = Column(String(100),nullable=False)
    password = Column(String(100), nullable=False)
    poste = Column(String(50))
    date_req = Column(Date, nullable=False, default=date.today())
    hour_req = Column(Time, nullable=False, default=time())
    status = Column(Enum('accepted', 'refused', 'pending'), default="pending")
    comments = Column(String(100))
    
    