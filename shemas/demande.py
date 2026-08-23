from datetime import time, date


from fastapi import UploadFile, File
from pydantic import BaseModel


"""API queries parameters"""
# Type de données pour la création d'une nouvelle demande d'inscription
class NewInscriptionParameters(BaseModel):
    nom : str
    prenom : str
    sexe: str
    matricule : str
    email : str
    telephone : str
    password : str
    poste : str
    photo: UploadFile = File(...)

# Type de données pour la modification d'une demande d'inscription
class UpdateInscriptionParameters(BaseModel):
    nom : str | None = None
    prenom : str | None = None
    sexe: str | None = None
    matricule : str | None = None
    email : str | None = None
    telephone : str | None = None
    poste : str | None = None
    photo: UploadFile | None = File(None)



""" API answers """
# Type de réponse API pour la demande d'inscription
class InscriptionType(BaseModel):
    id: int
    nom : str
    prenom : str
    sexe: str
    matricule : str
    email : str
    telephone : str
    photo : str
    poste : str | None = None
    status: str | None = None
    request_comments: str | None = None
    request_date: date 
    request_time:  time

    class Config:
        from_attributes = True



