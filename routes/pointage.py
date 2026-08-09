import shutil
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Depends, APIRouter, Query
from fastapi.sse import EventSourceResponse
from sqlalchemy.orm import joinedload

from services.auth import get_current_user, verify_access_token
from database.database import get_db
from models.employe import Employe
from models.pointages import Pointage, ScoringState
from services.employe import get_user_encoding
from services.pointage import IMG_DIR, traiter_premier_pointage, traiter_deuxieme_pointage, archiver_photo, \
    get_or_create_pointage, calculer_match, take_picture, readqr, appliquer_changement_statut, prodige_donnees_pointages
from shemas.employe import RequestModelEmp
from shemas.pointage import ChangeStatusPointageRequest, ModelScoring
from utils.global_var import SettingApp

router = APIRouter(prefix="/pointage", tags=["pointage"])


"""Récupérer tous les pointages"""
@router.get("/pointages")
async def get_all_stream_req(token: str = Query()):
    user = verify_access_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    return EventSourceResponse(prodige_donnees_pointages(token))



"""Récupérer tous les pointages d'un user specifique"""
@router.get("/my_scoring", response_model=list[ModelScoring])
def get_all_pointages(current_user: RequestModelEmp | None = Depends(get_current_user)):
    with get_db() as db:
        pointages = db.query(Pointage).options(joinedload(Pointage.users)).filter(Pointage.id_user == current_user.id).all()
        if not pointages:
            return []
        return pointages


"""modifier le status d'un pointage"""
@router.put("/{id}/change_status")
def change_pointage_status(
    id: int,
    body: ChangeStatusPointageRequest,
    current_user: RequestModelEmp = Depends(get_current_user),
):
    """
    Permet à l'admin de modifier manuellement le statut d'un pointage.
    Met à jour les champs calculés en conséquence.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    settings = {
        "HEURE_ARRIVEE": SettingApp.setting_cash["HEURE_ARRIVEE"],
        "HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE": SettingApp.setting_cash["HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE"],
    }

    with get_db() as db:
        pointage = db.query(Pointage).filter(Pointage.id == id).first()
        if not pointage:
            raise HTTPException(status_code=404, detail="Pointage introuvable")

        appliquer_changement_statut(pointage, body, settings)

        db.commit()
        db.refresh(pointage)

    return {"message": "Statut mis à jour avec succès"}




"""lire le qr code"""
@router.get("/scan_qr")
def scan_qr(mat: str):
    scan_result = readqr(mat)

    with get_db() as db:
        emp = db.query(Employe).filter(Employe.qrCode == scan_result).first()

    if not emp:
        raise HTTPException(
            status_code=400, detail="Employé introuvable avec ce QR code"
        )

    return scan_result







"""pointer sa présence"""
@router.post("/pointer")
def pointer(current_user: RequestModelEmp = Depends(get_current_user)):
    """
    Endpoint de pointage — orchestre les différentes étapes :
    1. Capture et encodage du visage
    2. Comparaison avec la référence
    3. Archivage de la photo
    4. Mise à jour du pointage
    """

    # ── Récupérer les paramètres ──
    settings = {
        "HEURE_LIMITE": (
            SettingApp.setting_cash["HEURE_ARRIVEE"]
            if SettingApp.setting_cash["HEURE_TOLEREE"] is None
            else SettingApp.setting_cash["HEURE_TOLEREE"]
        ),
        "JOUNEE_TRAVAIL": SettingApp.setting_cash["JOUNEE_TRAVAIL"],
        "HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE": SettingApp.setting_cash["HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE"],
    }

    # ── Étape 1 : Capturer et encoder le visage ──
    picture_encode = take_picture(current_user.matricule)
    if not picture_encode:
        raise HTTPException(status_code=400, detail="Aucun visage détecté dans l'image capturée.")

    # ── Étape 2 : Récupérer l'encodage de référence ──
    user_encode = get_user_encoding(current_user.id, current_user.photo)
    if user_encode is None:
        raise HTTPException(status_code=400, detail="Aucun visage détecté dans la photo de référence.")

    # ── Étape 3 : Comparer les visages ──
    match_found, best_distance = calculer_match(picture_encode, user_encode)
    now = datetime.now().time()

    with get_db() as db:
        # ── Étape 4 : Récupérer ou créer le pointage ──
        pointage = get_or_create_pointage(db, current_user.id)

        # ── Étape 5 : Archiver la photo ──
        numero_photo = 1 if pointage.numero_pointage == 0 else 2
        img_path = archiver_photo(current_user.matricule, numero_photo)

        # ── Étape 6 : Mettre à jour selon le numéro de pointage ──
        if pointage.numero_pointage == 0:
            traiter_premier_pointage(pointage, match_found, best_distance, img_path, now, settings)
        elif pointage.numero_pointage == 1:
            traiter_deuxieme_pointage(pointage, match_found, best_distance, img_path, now, settings)

        db.commit()
        db.refresh(pointage)

    return match_found


@router.delete("/delete/{id}")
def delete_user(id: int, current_user: RequestModelEmp = Depends(get_current_user)):
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
        try:
            picture = Path(user.photo)
            if picture.exists() and picture.is_file():
                picture.unlink()
        except OSError as e:
            print(f"Erreur suppression photo: {e}")

        db.delete(user)
        db.commit()
