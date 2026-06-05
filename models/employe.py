from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship
from database.database import Base
from models.demandes import Sexe


class Employe(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(30), nullable=False)
    prenom = Column(String(30), nullable=False)
    sexe = Column(Enum(Sexe), nullable=False)
    matricule = Column(String(5), unique=True)
    email = Column(String(50), unique=True)
    telephone = Column(String(12), unique=True)
    photo = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    poste = Column(String(50))
    qrCode = Column(String(255), nullable=False, unique=True)
    role = Column(Enum('admin', 'employe'), default='employe', nullable=False)

    # Relations
    pointages = relationship("Pointage", back_populates="users")
    statistiques = relationship('Statistique', back_populates='users')



