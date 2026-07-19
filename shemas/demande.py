from datetime import time, date
from typing import Annotated

from fastapi import UploadFile, File, Form
from pydantic import BaseModel


class ModelRequest(BaseModel):
    nom : str
    prenom : str
    sexe: str
    matricule : str
    email : str
    telephone : str
    password : str
    poste : str
    photo: UploadFile = File(...)

class ModelUpdateRequest(BaseModel):
    id_req: str
    nom : str | None = None
    prenom : str | None = None
    sexe: str | None = None
    matricule : str | None = None
    email : str | None = None
    telephone : str | None = None
    password : str | None = None
    poste : str | None = None
    photo: UploadFile | None = File(None)

class ResponseRequest(BaseModel):
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
    comments: str | None = None
    date_req: date 
    hour_req:  time

    class Config:
        from_attributes = True

class ResponseChangeStatus(BaseModel):
    id: int
    nom : str
    prenom : str
    matricule : str
    status: str
    comments: str

    class Config:
        from_attributes = True


