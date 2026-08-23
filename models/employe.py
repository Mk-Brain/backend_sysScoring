import enum
from datetime import date, time

from sqlalchemy import Column, Integer, String, Enum, Date, Time
from sqlalchemy.orm import relationship

from database.database import Base

class Sexe(str, enum.Enum):
    MASCULIN = "MASCULIN"
    FEMININ = "FEMININ"

class StatutEmploye(str, enum.Enum):
    ACTIF = "actif"
    INACTIF = "inactif"
    ACCEPTED = "accepted"
    REFUSED = "refused"
    PENDING = "pending"

class RoleEmploye(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYE = "employe"


class Employe(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(30), nullable=False)
    prenom = Column(String(30), nullable=False)
    sexe = Column(Enum(Sexe), nullable=False)
    matricule = Column(String(10), unique=True)
    email = Column(String(50), unique=True)
    telephone = Column(String(12), unique=True)
    photo = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    poste = Column(String(50), nullable=True)
    qr_code = Column(String(255), nullable=True, unique=True)
    status = Column(Enum(StatutEmploye), default=StatutEmploye.PENDING, nullable=False)
    role = Column(Enum(RoleEmploye), default=RoleEmploye.EMPLOYE, nullable=False)

    # Champs liés à une éventuelle demande d'inscription / validation
    request_comments = Column(String(255), nullable=True)
    request_date = Column(Date, nullable=True)
    request_time = Column(Time, nullable=True)
    

    # Relations
    pointages = relationship("Pointage", back_populates="users")
    






