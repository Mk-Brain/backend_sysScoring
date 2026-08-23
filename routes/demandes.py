from datetime import datetime, date
from pathlib import Path

from fastapi import HTTPException, Form, Query

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse


from models.employe import Employe, StatutEmploye
from services.auth import get_current_pending_user, get_password_hash, get_user_by_id, verify_access_token, get_user_by_email
from database.database import get_db

from services.demande import rename_img, save_img, verify_picture, prodige_donnees_dmd

from shemas.demande import (
    InscriptionType,
    NewInscriptionParameters,
    UpdateInscriptionParameters,
)
from utils.global_var import UPLOAD_DIR


router = APIRouter(prefix="/demande", tags=["demande"])



"""recupérer la demande d'inscription d'un nouvel employé"""
@router.get("/get_inscription", response_model=InscriptionType)
def get_all_(current_user: Employe = Depends(get_current_pending_user)):
    return current_user

# TODO: s'assurer de la prise en compte des méssages d'exeption
# TODO: implémenter les message emails pour avertir l'employé lorsque le compte est validé
# TODO: AJouter des nouveaux style de chargemeent de page su mobile
# TODO: prendre en compte les espace dans le num de tel sur la page d'inscription
# TODO: verrifier les codes d'erreur

"""Recupérer la liste de toutes les demandes des utilisateurs"""
@router.get("/demandes")
async def get_all_stream_req(token: str = Query(...)):
    user = verify_access_token(token)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_dmd(token))


"""effectuer une demande d'inscription"""
@router.post("/inscription")
async def new_inscrition(dem: NewInscriptionParameters = Form(media_type="multipart/form-data")):
    now = datetime.now().time()
    with get_db() as db:
        user = get_user_by_email(dem.email, db)
        if user:
            if user.status == StatutEmploye.PENDING: 
                raise HTTPException(status_code=400, detail=f"L'utilisateur{user.nom} a déjà fait une demande")
            else: 
                raise HTTPException(status_code=400, detail="L'utilisateur existe déjà")
        
    # verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)
    #enregistrement de la photo
    chemin = UPLOAD_DIR / f"{dem.matricule}.jpg"
    images_location = str(chemin)
    with open(images_location, "wb") as f:
        content = await dem.photo.read()
        f.write(content)

    #sauvegarde de la demande
    hashed_password = get_password_hash(dem.password)
    qrcode = f"{dem.nom} - {dem.matricule}"
    demande = Employe(
        nom=dem.nom,
        prenom=dem.prenom,
        sexe=dem.sexe,
        matricule=dem.matricule,
        email=dem.email,
        qr_code=qrcode,
        telephone=dem.telephone,
        photo=images_location,
        request_date=date.today(),
        password=hashed_password,
        poste=dem.poste,
        request_time=now
    )
    with get_db() as db:
        db.add(demande)
        db.commit()
    return {"message:": "inscription réussie"}



"""modifier une demande d'inscription"""
@router.put("/change_inscription")
async def update_inscrition(
    dem: UpdateInscriptionParameters = Form(media_type="multipart/form-data"),
    current_user: Employe = Depends(get_current_pending_user)
):
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(dem.photo)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    now = datetime.now().time()

    with get_db() as db:
        user = get_user_by_id(current_user.id, db)
        old_photo_path = user.photo
        old_matricule = user.matricule

        user.request_time = now
        user.request_date = date.today()
        user.status = StatutEmploye.PENDING
        user.request_comments = ""

        if dem.nom:
            user.nom = dem.nom
        if dem.prenom:
            user.prenom = dem.prenom
        if dem.sexe:
            user.sexe = dem.sexe
        if dem.email:
            user.email = dem.email
        if dem.telephone:
            user.telephone = dem.telephone
        if dem.poste:
            user.poste = dem.poste

        new_matricule = dem.matricule or user.matricule

        if dem.matricule:
            user.matricule = dem.matricule

        if dem.photo:
            if old_photo_path and old_matricule and new_matricule and new_matricule != old_matricule:
                old_file = Path(old_photo_path)
                if old_file.exists():
                    old_file.unlink(missing_ok=True)

            user.photo = await save_img(new_matricule, dem.photo)

        elif dem.matricule and old_photo_path and old_matricule and new_matricule != old_matricule:
            user.photo = rename_img(new_matricule, old_photo_path)

        db.commit()

    return {
        "message": "Inscription reçue. Compte en attente de validation."
    }
    
