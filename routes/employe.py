import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse

from services.auth import get_current_user, get_password_hash, get_user_by_email, verify_access_token
from database.database import  get_db
from models.demandes import DemandesInscription
from models.employe import Employe
from models.pointages import Pointage
from models.statistique import Statistique
from services.employe import get_user_by_id
from shemas.employe import ResponseModelEmp, RequestModelEmp, ValidatedInscriptionModelRequest
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/employe",
    tags=["employe"]
)


async def prodige_donnees(token: str):
    while True:
        # ✅ Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            # ✅ Envoyer un événement spécial au lieu de crasher
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            donnees = db.query(Employe).all()
            payload = [
                ResponseModelEmp.model_validate(d).model_dump(mode="json")
                for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)

"""Récupérer tous les employés"""
@router.get("/users")
async def get_all_stream_user(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees(token))





"recuperer l'utilisateur connecté"
@router.get("/self", response_model=ResponseModelEmp)
async def read_users_me(current_user: RequestModelEmp | None = Depends(get_current_user)):
    return current_user    



"""valider une inscrition"""
@router.post("/add_user", response_model=ResponseModelEmp)
def add_user(
    params: ValidatedInscriptionModelRequest,
    current_user: RequestModelEmp | None = Depends(get_current_user)
):
    if current_user and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")

    with get_db() as db:
        user = get_user_by_email(params.email, db)
        if user:
            raise HTTPException(status_code=400, detail="Username already registered")

        
        req = db.query(DemandesInscription).filter(DemandesInscription.email == params.email).first()
        if not req:
            raise HTTPException(status_code=400, detail="Request do not exist")

        hashed_password = get_password_hash(req.password)
        qrcode = req.nom + "-" + req.matricule + "-" + req.email

        emp = Employe(
            nom=req.nom,
            prenom=req.prenom,
            matricule=req.matricule,
            sexe=req.sexe,
            telephone=req.telephone,
            photo=req.photo,
            qrCode=qrcode,
            email=req.email,
            password=hashed_password,
            poste=req.poste,
            role=params.role,
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

    return emp
"""Supprimer un utilisateur"""
@router.delete("/delete_user", response_model=dict[str, str])
def delete_user(id_user: int, current_user: RequestModelEmp | None = Depends(get_current_user)):
    if current_user and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")


    with get_db() as db:
        user_to_delete = get_user_by_id(id_user, db)
        if not user_to_delete:
            raise HTTPException(status_code=400, detail="user do not exist")
        sconring_to_delete = db.query(Pointage).filter(Pointage.id_user == id_user).all()
        if sconring_to_delete:
            for item in sconring_to_delete:
                db.delete(item)
        stat_to_delete = db.query(Statistique).filter(Statistique.id_user == id_user).all()
        if stat_to_delete:
            for item in stat_to_delete:
                db.delete(item)
        db.delete(user_to_delete)
        db.commit()
    return {"message" : "success"}

"""modifier un utilisateur"""
@router.put("/update_user", response_model=ResponseModelEmp)
def update_user(id_user: int,
                current_user: RequestModelEmp | None = Depends(get_current_user),
                nom : str | None = None,
                prenom : str | None = None,
                matricule : str | None = None,
                sexe : str | None = None,
                telephone : str | None = None,
                photo : str | None = None,
                qr_code : str | None = None,
                role: str | None = None,
                email : str | None = None,
                password : str | None = None,
                poste : str | None = None,
                ):
    if current_user and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    to_update = Employe()
    with get_db() as db:
        to_update = get_user_by_id(id_user, db)
        if not to_update:
            raise HTTPException(status_code=400, detail="user do not exist")

        if email:
            to_update.email = email
        if nom:
            to_update.nom = nom
        if prenom:
            to_update.prenom = prenom
        if matricule:
            to_update.matricule = matricule
        if sexe:
            to_update.sexe = sexe
        if telephone:
            to_update.telephone = telephone
        if photo:
            to_update.photo = photo
        if qr_code:
            to_update.qrCode = qr_code
        if role:
            to_update.role = role
        if password:
            to_update.password = password
        if poste:
            to_update.poste = poste
        db.commit()
        db.refresh(to_update)
    return to_update

@router.get("/picture", response_class=FileResponse)
async def picture(name: str):
    return f"uploads/{name}.jpg"

@router.delete("/delete/{id}", )
def delete_user(
    id: int,
    current_user: RequestModelEmp = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can not access from this route")

    with get_db() as db:
        user = db.query(Employe).filter(Employe.id == id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        
        db.query(Pointage).filter(Pointage.id_user == id).delete()

        
        db.query(Statistique).filter(Statistique.id_user == id).delete()

        db.delete(user)
        db.commit()

    return {"message": "Utilisateur supprimé avec succès"}