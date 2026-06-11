from pydantic import BaseModel


class RequestModelEmp(BaseModel):
    id : int
    nom : str
    prenom: str
    matricule : str
    sexe : str
    telephone : str
    photo : str
    qrCode : str = "employe"
    role: str
    email : str
    password : str
    poste : str

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

    class Config:
        from_attributes = True