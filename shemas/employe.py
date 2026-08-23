from pydantic import BaseModel
from fastapi import UploadFile

#TODO: renommer les types de données et ajouter des commentaire pour mieux les identifier
"""API queries parameters"""

class RequestModelNewEmp(BaseModel):
    nom: str
    prenom: str
    matricule: str
    sexe: str
    telephone: str
    photo: UploadFile
    role: str = "employe"
    email: str
    password: str
    poste: str
    status: str | None



""" API answers """
class ResponseModelEmp(BaseModel):
    id : int
    nom : str
    prenom: str
    matricule : str
    sexe : str
    telephone : str
    photo : str
    qr_code : str | None
    role: str
    email : str
    poste : str
    status: str | None

    class Config:
        from_attributes = True