import os
from datetime import datetime, date
from pathlib import Path

from fastapi import HTTPException, Form, Query

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse


from services.auth import get_current_user, verify_access_token, get_user_by_email
from database.database import get_db

from models.demandes import DemandesInscription

from sqlalchemy import exists, select

from services.demande import verify_picture, prodige_donnees_dmd

from shemas.demande import (
    ResponseRequest,
    ModelRequest,
    ResponseChangeStatus,
    ModelUpdateRequest,
)
from shemas.employe import RequestModelEmp

router = APIRouter(prefix="/demande", tags=["demande"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)



@router.get("/get_request/{id}", response_model=ResponseRequest)
def get_all_(id: int ):
    with get_db() as db:
        demande = db.query(DemandesInscription).filter(DemandesInscription.id == id).first()
    if not demande:
        raise HTTPException(status_code="401", detail="demande non trouvés")
    return  demande


@router.get("/demandes")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_dmd(token))


"""effectuer une demande d'inscription"""
@router.post("/inscription", response_model=ResponseRequest)
async def new_inscrition(dem: ModelRequest = Form(media_type="multipart/form-data")):
    now = datetime.now().time()
    with get_db() as db:
        user = get_user_by_email(dem.email, db)
        if user:
            raise HTTPException(status_code=400, detail="Username already registered")
    # verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)
    chemin = Path(UPLOAD_DIR) / f"{dem.matricule}.jpg"
    images_location = str(chemin)
    with open(images_location, "wb") as f:
        content = await dem.photo.read()
        f.write(content)
    demande = DemandesInscription(
        nom=dem.nom,
        prenom=dem.prenom,
        sexe=dem.sexe,
        matricule=dem.matricule,
        email=dem.email,
        telephone=dem.telephone,
        photo=images_location,
        date_req=date.today(),
        password=dem.password,
        poste=dem.poste,
        hour_req=now
    )
    with get_db() as db:
        get_exist_dmd = select(
            exists().where(DemandesInscription.matricule == dem.matricule)
        )
        flag = db.scalar(get_exist_dmd)
        if flag:
            raise HTTPException(
                status_code=400,
                detail="Une demande d'inscription existe déjà pour ce matricule."
            )
        db.add(demande)
        db.commit()
        db.refresh(demande)
    return demande


"""modifier une demande d'inscription"""


@router.put("/change_inscription", response_model=ResponseRequest)
async def update_inscrition(
    dem: ModelUpdateRequest = Form(media_type="multipart/form-data"),
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
        dmd = (
            db.query(DemandesInscription)
            .filter(DemandesInscription.id == int(dem.id_req))
            .first()
        )
        dmd.hour_req = datetime.now().time()
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
    return dmd


"""changer le status d'une demande"""


@router.put("/change_status", response_model=ResponseChangeStatus)
def change_status(
    id: int,
    status: str,
    comments: str | None = None,
    current_user: RequestModelEmp = Depends(get_current_user),
):
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
    return demande


@router.delete(
    "/{id}",
)
def delete_request(id: int, current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="You can not access from this route"
        )

    with get_db() as db:
        demande = (
            db.query(DemandesInscription).filter(DemandesInscription.id == id).first()
        )

        if not demande:
            raise HTTPException(status_code=404, detail="Demande not found")

        db.delete(demande)
        db.commit()

    return {"message": "Demande supprimée avec succès"}
