import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterable

from fastapi import HTTPException, Form, Query

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.sse import EventSourceResponse

from services.auth import get_current_user, verify_access_token
from database.database import get_db

from models.demandes import DemandesInscription

from sqlalchemy import exists, select

from services.demande import verify_picture
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


"""Récupérer toutes les demandes"""
"""@router.get("/demandes", response_model=list[ResponseRequest])
def get_all_(current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    with get_db() as db:
        demandes = db.query(DemandesInscription).all()
    if not demandes:
        return {"message": "Aucune demande d'inscrition"}
    return  demandes"""


import asyncio, json


async def prodige_donnees(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            # Envoyer un événement spécial au lieu de crasher
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            donnees = db.query(DemandesInscription).all()
            payload = [
                ResponseRequest.model_validate(d).model_dump(mode="json")
                for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)


@router.get("/demandes")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees(token))


"""effectuer une demande d'inscription"""
@router.post("/inscription", response_model=ResponseRequest)
async def new_inscrition(dem: ModelRequest = Form(media_type="multipart/form-data")):
    # verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)

    images_location = str(Path(UPLOAD_DIR / f"{dem.matricule}.jpg") )
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
        password=dem.password,
        poste=dem.poste,
    )
    with get_db() as db:
        get_exist_dmd = select(
            exists().where(DemandesInscription.matricule == dem.matricule)
        )
        flag = db.scalar(get_exist_dmd)
        if not flag:
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
