import asyncio
import json
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.sse import EventSourceResponse
from sqlalchemy import select, exists

 # removed import of UPLOAD_DIR from routes.demandes to avoid redeclaration / circular import
from services.auth import get_current_user, get_password_hash, get_user_by_email, verify_access_token
from database.database import  get_db
from models.demandes import DemandesInscription
from models.employe import Employe
from models.pointages import Pointage
from models.statistique import Statistique
from services.demande import verify_picture
from services.employe import get_user_by_id
from services.pointage import IMG_DIR
from shemas.employe import ResponseModelEmp, RequestModelEmp, ValidatedInscriptionModelRequest, RequestModelNewEmp, \
    UpdateStatusRequest
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/employe",
    tags=["employe"]
)


async def prodige_donnees(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            # Envoyer un événement spécial au lieu de crasher
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
        req = db.query(DemandesInscription).filter(DemandesInscription.email == params.email).first()
        if not req:
            raise HTTPException(status_code=400, detail="Request do not exist")

        req.status = "accepted"

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
            status="actif"
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

    return emp

@router.post("/new_user", response_model=ResponseModelEmp)
async def new_user(dem: RequestModelNewEmp = Form(media_type="multipart/form-data")):
    # verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)
    chemin = Path(UPLOAD_DIR) / f"{dem.matricule}.jpg"
    images_location = str(chemin)
    with open(images_location, "wb") as f:
        content = await dem.photo.read()
        f.write(content)
    hashed_password = get_password_hash(dem.password)
    demande = Employe(
        nom=dem.nom,
        prenom=dem.prenom,
        sexe=dem.sexe,
        matricule=dem.matricule,
        email=dem.email,
        telephone=dem.telephone,
        photo=images_location,
        password=hashed_password,
        poste=dem.poste,
        qrCode=dem.qrCode,
        role=dem.role,
        status=dem.status
    )
    with get_db() as db:
        get_exist_dmd = select(
            exists().where(Employe.matricule == dem.matricule)
        )
        flag = db.scalar(get_exist_dmd)
        if not flag:
            db.add(demande)
            db.commit()
            db.refresh(demande)
    return demande


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
                status: str | None = None
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
        if status:
            to_update.status = status
        db.commit()
        db.refresh(to_update)
    return to_update

UPLOAD_DIR = Path("uploads")

@router.get("/picture", response_class=FileResponse)
async def picture(name: str):
    file_path = UPLOAD_DIR / f"{name}.jpg"

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image non trouvée")

    return FileResponse(file_path)

@router.get("/scoring_picture", response_class=FileResponse)
async def scoring_picture(name: str):
    file = Path(name)
    if not file.exists() or not file.is_file():
        raise HTTPException(status_code=404, detail="Image non trouvée")

    return FileResponse(file)
@router.patch("/{user_id}/status")
def update_status(
    user_id: int,
    payload: UpdateStatusRequest,
    current_user: RequestModelEmp = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    if payload.status not in ("actif", "inactif"):
        raise HTTPException(status_code=400, detail="Statut invalide")

    with get_db() as db:
        emp = db.query(Employe).get(user_id)
        if not emp:
            raise HTTPException(status_code=404, detail="Employé introuvable")

        emp.status = payload.status
        db.commit()
        db.refresh(emp)

    return {"message": "success", "status": payload.status}

@router.delete("/delete/{id}")
def delete_user(id: int, current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can not access from this route")

    with get_db() as db:
        user = db.query(Employe).filter(Employe.id == id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db.query(Pointage).filter(Pointage.id_user == id).delete()
        db.query(Statistique).filter(Statistique.id_user == id).delete()

        # Suppression des images de pointage (dossier par matricule, sous-dossiers par date)
        folderuser = Path(IMG_DIR) / user.matricule
        try:
            if folderuser.exists() and folderuser.is_dir():
                shutil.rmtree(folderuser)
        except OSError as e:
            print(f"Erreur suppression dossier pointage: {e}")

        # Suppression de la photo de profil
        try:
            picture = Path(user.photo)
            if picture.exists() and picture.is_file():
                picture.unlink()
        except OSError as e:
            print(f"Erreur suppression photo: {e}")

        db.delete(user)
        db.commit()