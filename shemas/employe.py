from pydantic import BaseModel


class RequestModelEmp(BaseModel):
    id : int
    nom : str
    prenom: str
    matricule : str
    sexe : str
    telephone : str
    photo : str
    qrCode : str
    role: str
    email : str
    password : str
    poste : str
    status: str | None

class ValidatedInscriptionModelRequest(BaseModel):
    email:str 
    role: str
class ResponseModelEmp(BaseModel):
    id : int
    nom : str
    prenom: str
    matricule : str
    sexe : str
    telephone : str
    photo : str
    qrCode : str
    role: str
    email : str
    poste : str
    status: str | None

    class Config:
        from_attributes = True


from fastapi import UploadFile

class RequestModelNewEmp(BaseModel):
    nom: str
    prenom: str
    matricule: str
    sexe: str
    telephone: str
    photo: UploadFile
    qrCode: str = "employe"
    role: str
    email: str
    password: str
    poste: str
    status: str | None
