import os

from fastapi import HTTPException, Form

from fastapi import APIRouter, Depends


from services.auth import get_current_user
from database.database import  get_db

from models.demandes import DemandesInscription

from sqlalchemy import exists, select

from services.demande import verify_picture
from shemas.demande import ResponseRequest, ModelRequest, ResponseChangeStatus, ModelUpdateRequest
from shemas.employe import RequestModelEmp

router = APIRouter(
    prefix="/demande",
    tags=["demande"]
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)



"""Récupérer toutes les demandes"""
@router.get("/", response_model=list[ResponseRequest])
def get_all_(current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    with get_db() as db:
        demandes = db.query(DemandesInscription).all()
    if not demandes:
        return {"message": "Aucune demande d'inscrition"}
    return  demandes


"""effectuer une demande d'inscription"""
@router.post("/inscription", response_model=ResponseRequest)
async def new_inscrition(dem:ModelRequest = Form(media_type="multipart/form-data")):
    #verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)
    images_location = os.path.join(UPLOAD_DIR, f"{dem.matricule}.jpg")
    with open(images_location, "wb") as f:
        content = await dem.photo.read()
        f.write(content)
    demande = DemandesInscription(
        nom=dem.nom,
        prenom= dem.prenom,
        sexe= dem.sexe,
        matricule=dem.matricule,
        email=dem.email,
        telephone=dem.telephone,
        photo=images_location,
        password=dem.password,
        poste=dem.poste,
    )
    with get_db() as db:
        get_exist_dmd = select(exists().where(DemandesInscription.matricule == dem.matricule))
        flag = db.scalar(get_exist_dmd)
        if not flag:
            db.add(demande)
            db.commit()
            db.refresh(demande)
    return demande

"""modifier une demande d'inscription"""
@router.put("/change_inscription", response_model=ResponseRequest)
async def update_inscrition(
    dem:ModelUpdateRequest = Form(media_type="multipart/form-data")
    ):
    global images_location
    if dem.photo:
        await verify_picture(dem.photo)
        await dem.photo.seek(0)
        images_location = os.path.join(UPLOAD_DIR, f"{dem.matricule}.jpg")
        with open(images_location, "wb") as f:
            content = await dem.photo.read()
            f.write(content)
    dmd = DemandesInscription()
    with get_db() as db:
        dmd = db.query(DemandesInscription).filter(DemandesInscription.id == int(dem.id_req)).first()
        dmd.status = "pending"
        if dem.nom:
            dmd.nom = dem.nom
        if dem.prenom:
            dmd.prenom = dem.prenom
        if dem.sexe:
            dmd.sexe = dem.sexe
        if dem.matricule:
            dmd.matricule = dem.matricule
        if dem.email:
            dmd.email = dem.email
        if dem.telephone:
            dmd.telephone = dem.telephone
        if dem.photo:
            dmd.photo = images_location
        if dem.password:
            dmd.password = dem.password
        if dem.poste:
            dmd.poste = dem.poste
        db.commit()
        db.refresh(dmd)
    return  dmd

"""recuperer une demande"""
@router.get("/get_request", response_model=ResponseRequest)
def get_request(id_request: int):
    with get_db() as db:
        dmd = db.query(DemandesInscription).get(id_request)
    return dmd

"""changer le status d'une demande"""
@router.put("/change_status", response_model=ResponseChangeStatus)
def change_status(id: int, status: str, comments: str | None = None, current_user: RequestModelEmp = Depends(get_current_user)) :
    if current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    demande = DemandesInscription()
    with get_db() as db:
        demande = db.query(DemandesInscription).get(id)
        if not demande:
            raise HTTPException(status_code=400, detail="inscription request not found")
        demande.status = status
        if comments:
            demande.comments = comments
        db.commit()
        db.refresh(demande)
    return  demande


