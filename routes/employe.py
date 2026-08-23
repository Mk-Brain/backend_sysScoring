from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.sse import EventSourceResponse


from services.auth import get_current_user, get_password_hash, get_user_by_email, verify_access_token, get_user_by_id
from database.database import  get_db
from models.employe import Employe, StatutEmploye
from models.pointages import Pointage

from services.demande import verify_picture
from services.employe import  delete_picture, prodige_donnees_emp

from shemas.employe import ResponseModelEmp, RequestModelNewEmp
from fastapi.responses import FileResponse

from utils.global_var import IMG_DIR, UPLOAD_DIR


router = APIRouter(
    prefix="/employe",
    tags=["employe"]
)

"""Récupérer tous les employés"""
@router.get("/users")
async def get_all_stream_user(token: str = Query(...)):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_emp(token))





"recuperer l'utilisateur connecté"
@router.get("/self", response_model=ResponseModelEmp)
async def read_users_me(current_user: Employe | None = Depends(get_current_user)):
    return current_user    



"""valider / regéter une inscription"""
@router.post("/add_user")
def add_user(
    email:str,
    role: str,
    current_user: Employe | None = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    if role not in ("admin", "employe"):
        raise HTTPException(status_code=400, detail="Role invalide")
    with get_db() as db:
        emp = db.query(Employe).filter(Employe.email == email).first()
        if not emp:
            raise HTTPException(status_code=400, detail="Request do not exist")
        qrcode = f"{emp.nom} - {emp.matricule}"
        emp.role = role
        emp.qr_code = qrcode
        emp.status = StatutEmploye.ACTIF
        db.commit()

    return {"message": "success"}

# FIXME: protéger la route d'ajout d'uun nouvel utilisateur par l'admin
"""Ajouter directement un nouvel employé sans passé par l'inscription"""
@router.post("/new_user")
async def new_user(
    dem: RequestModelNewEmp = Form(media_type="multipart/form-data"),
    current_user: Employe | None = Depends(get_current_user)
    ):
    if current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    # verification de l'extension
    await verify_picture(dem.photo)
    await dem.photo.seek(0)
    chemin = Path(UPLOAD_DIR) / f"{dem.matricule}.jpg"
    images_location = str(chemin)
    with open(images_location, "wb") as f:
        content = await dem.photo.read()
        f.write(content)
    hashed_password = get_password_hash(dem.password)
    qrcode = f"{dem.nom} - {dem.matricule}"
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
        qr_code=qrcode,
        role=dem.role,
        status=dem.status
    )
    with get_db() as db:
        user = get_user_by_email(dem.email, db)
        if user:
            raise HTTPException(status_code=400, detail="L'utilisateur existe déjà")
        db.add(demande)
        db.commit()
            
    return {"message": "success"}


"""modifier un utilisateur"""
@router.put("/update_user", response_model=ResponseModelEmp)
def update_user(id_user: int,
                nom : str | None = None,
                prenom : str | None = None,
                matricule : str | None = None,
                sexe : str | None = None,
                telephone : str | None = None,
                photo : str | None = None,
                role: str | None = None,
                email : str | None = None,
                poste : str | None = None,
                current_user: Employe | None = Depends(get_current_user)
                ):
    if current_user.role != "admin":
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
        if role:
            to_update.role = role
        if poste:
            to_update.poste = poste
        if nom or matricule:
            to_update.qr_code = f"{to_update.nom} - {to_update.matricule}"
        db.commit()
        db.refresh(to_update)
    return to_update



#retourne une photo de reférence à partir du matricule
@router.get("/picture", response_class=FileResponse)
async def picture(name: str):
    file_path = Path(UPLOAD_DIR) / f"{name}.jpg"
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image non trouvée")

    return FileResponse(file_path)

#retourne n'importe quelle image ayant un chemin valide
@router.get("/scoring_picture", response_class=FileResponse)
async def scoring_picture(name: str):
    file = Path(name)
    if not file.exists() or not file.is_file():
        raise HTTPException(status_code=404, detail="Image non trouvée")

    return FileResponse(file)


"""Modifier le status d'un employé"""
@router.patch("/{user_id}/status")
def update_status(
    user_id: int,
    status: str ,
    current_user: Employe = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    if status not in ("actif", "inactif", "pending", "rejected"):
        raise HTTPException(status_code=400, detail="Statut invalide")

    with get_db() as db:
        emp = db.query(Employe).get(user_id)
        if not emp:
            raise HTTPException(status_code=404, detail="Employé introuvable")

        emp.status = status
        db.commit()
        db.refresh(emp)

    return {"message": "success", "status": status}
# TODO: supprimmer la route de modification de status et passer par la route de modif générale de l'utilisateur


"""Supprimer un employé"""
@router.delete("/delete/{id}")
def delete_user(id: int, current_user: Employe = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can not access from this route")

    with get_db() as db:
        user = db.query(Employe).filter(Employe.id == id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db.query(Pointage).filter(Pointage.id_user == id).delete()

        # Suppression des images de pointage (dossier par matricule, sous-dossiers par date)
        folderuser = Path(IMG_DIR) / user.matricule
        try:
            if folderuser.exists() and folderuser.is_dir():
                shutil.rmtree(folderuser)
        except OSError as e:
            print(f"Erreur suppression dossier pointage: {e}")

        # Suppression de la photo de profil
        delete_picture(user.photo)
        db.delete(user)
        db.commit()

