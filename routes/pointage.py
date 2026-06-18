import asyncio
import json
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Query
import cv2
from fastapi.sse import EventSourceResponse

from pyzbar.wrapper import ZBarSymbol
from sqlalchemy.orm import joinedload

from models.config import Parametre
from services.auth import get_current_user, verify_access_token
from database.database import get_db
from models.employe import Employe
from models.pointages import Pointage, ScoringState
from services.employe import get_user_encoding
from services.pointage import take_picture, encoding, IMG_DIR
from shemas.employe import RequestModelEmp
from shemas.pointage import ChangeStatusPointageRequest, ModelScoring
from pyzbar.pyzbar import decode

from utils.global_var import SettingApp, VideoSetting

from datetime import (
    date,
    datetime,
    time,
    timedelta,
) 

import time as tm
import face_recognition
from fastapi import HTTPException, Depends

router = APIRouter(prefix="/pointage", tags=["pointage"])


async def prodige_donnees_pointages(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token(token)

        if user is None:
            #  Envoyer un événement spécial au lieu de crasher
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            donnees = db.query(Pointage).options(joinedload(Pointage.users)).all()
            payload = [
                ModelScoring.model_validate(d).model_dump(mode="json") for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)


"""Récupérer tous les pointages"""


@router.get("/pointages")
async def get_all_stream_req(token: str = Query(...)):
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
        pointages = db.query(Pointage).filter(Pointage.id_user == current_user.id).all()
        if not pointages:
            return []
        return pointages


"""Changer le status d'un pointages"""


@router.put("/{id}/change_status")
def change_pointage_status(
    id: int,
    body: ChangeStatusPointageRequest,
    current_user: RequestModelEmp = Depends(get_current_user),
):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="You can not access from this route"
        )

    with get_db() as db:
        pointage = db.query(Pointage).filter(Pointage.id == id).first()
        if not pointage:
            raise HTTPException(status_code=404, detail="Pointage not found")
        if body.numero_pointage == 1:
            pointage.status_arrivee = body.status
        elif body.numero_pointage == 2:
            pointage.status_depart = body.status
        db.commit()

    return {"message": "Statut du pointage mis à jour"}


"""lire le qr code"""


@router.get("/scan_qr")
def scan_qr(mat: str):
    scan_result = None
    timeout = 10
    start_time = tm.time()
    today = date.today().strftime("%d/%m/%Y")
    print(f"Début du scan QR code... {today}")

    while (tm.time() - start_time) < timeout:
        # Vérifie l'état du flux
        if not VideoSetting.flag:
            print("flux non démarré ?")
            tm.sleep(0.05)
            break

        if VideoSetting.frame is None:
            print("pas de frame disponible")
            tm.sleep(0.05)
            break

        # Vérifie que c'est bien un numpy array
        frame = VideoSetting.frame  # Copie locale pour éviter les race conditions
        if not isinstance(frame, np.ndarray):
            print(f"frame n'est pas un numpy array : {type(frame)}")
            tm.sleep(0.05)
            continue

        decoded_info = decode(frame, symbols=[ZBarSymbol.QRCODE])

        if not decoded_info:
            tm.sleep(0.05)
            continue

        for qrcode in decoded_info:
            decoded_text = qrcode.data.decode("utf-8")
            print(f"QR détecté : {decoded_text}")

            if mat in decoded_text and today in decoded_text:
                scan_result = decoded_text
                print("OK")
                break

        if scan_result:
            break

        tm.sleep(0.05)

    if not scan_result:
        raise HTTPException(status_code=400, detail="Aucun QR code détecté")

    qr = str(scan_result).split("|")[0]
    print(qr)
    with get_db() as db:
        emp = db.query(Employe).filter(Employe.qrCode == qr).first()

    if not emp:
        raise HTTPException(
            status_code=400, detail="Employé introuvable avec ce QR code"
        )

    return scan_result





HEURE_ARRIVEE = SettingApp.setting_cash["HEURE_ARRIVEE"]
HEURE_DEPART = SettingApp.setting_cash["HEURE_DEPART"]
HEURE_RETARD_TOLERE = SettingApp.setting_cash["HEURE_TOLEREE"]
JOUNEE_TRAVAIL = SettingApp.setting_cash["JOUNEE_TRAVAIL"]

HEURE_LIMITE = HEURE_ARRIVEE if HEURE_RETARD_TOLERE is None else HEURE_RETARD_TOLERE

HEURE_LIMITE_AVANT_ABSENCE = SettingApp.setting_cash["HEURE_LIMITE_AVANT_ABSENCE"]
HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE = SettingApp.setting_cash["HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE"]


@router.post("/pointer")
def pointer(current_user: RequestModelEmp = Depends(get_current_user)):

    # 1. Capturer et encoder le visage
    picture_encode = None
    if take_picture(current_user.matricule):
        picture_encode = encoding(current_user.matricule)

    if not picture_encode:
        raise HTTPException(status_code=400, detail="Aucun visage détecté dans l'image capturée.")

    # 2. Récupérer l'encodage de référence depuis le cache
    user_encode = get_user_encoding(current_user.id, current_user.photo)
    if user_encode is None:
        raise HTTPException(status_code=400, detail="Aucun visage détecté dans la photo de référence.")

    with get_db() as db:
        # 3. Récupérer le pointage du jour
        pointage = db.query(Pointage).filter(
            Pointage.id_user == current_user.id,
            Pointage.date_day == date.today()
        ).first()

        if not pointage:
            raise HTTPException(status_code=404,
                                detail="Pointage non trouvé pour aujourd'hui. Contactez l'administrateur.")

        # 4. Comparer les visages
        best_distance = 1.0
        for detected_face_encoding in picture_encode:
            distance = face_recognition.face_distance([user_encode], detected_face_encoding)
            if distance[0] < best_distance:
                best_distance = distance[0]

        print(f"Distance: {best_distance}")
        match_found = best_distance < 0.5
        now = datetime.now().time()

        # 5. Archiver la photo — commun aux deux cas
        file = Path(IMG_DIR / current_user.matricule / datetime.now().date() / "img.png")
        if not file.exists():
            raise HTTPException(status_code=404, detail="Photo de pointage introuvable.")
        new_name = file.rename(
            IMG_DIR / current_user.matricule / datetime.now().date() / f"img{pointage.numero_pointage}.png"
        )
        img_path = str(new_name)

        # 6. Mettre à jour le pointage
        if pointage.numero_pointage == 0:
            # ── 1er pointage — arrivée ──
            pointage.numero_pointage = 1
            pointage.heure_arrive = now
            pointage.photo_pointage_arrivee = img_path
            pointage.distance_arrivee = round(best_distance, 4)
            pointage.heure_depart = HEURE_LIMITE_AVANT_ABSENCE
            pointage.status_depart = ScoringState.PRESENT

            # Statut arrivée selon reconnaissance
            pointage.status_arrivee = (
                ScoringState.PENDING if not match_found
                else ScoringState.RETARD if now > HEURE_LIMITE
                else ScoringState.PRESENT
            )

            # Estimation initiale du temps de travail
            fin = datetime.combine(date.today(), HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE)
            arrivee = datetime.combine(date.today(), now)
            delta = fin - arrivee
            pointage.minutes_travail = int(delta.total_seconds() / 60) if delta.total_seconds() > 0 else 0
            pointage.minutes_sup = 0

        elif pointage.numero_pointage == 1 and HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE < now <= HEURE_LIMITE_AVANT_ABSENCE:
            # ── 2ème pointage — départ ──
            pointage.numero_pointage = 2
            pointage.heure_depart = now
            pointage.photo_pointage_depart = img_path
            pointage.distance_depart = round(best_distance, 4)
            pointage.status_depart = ScoringState.PRESENT if match_found else ScoringState.PENDING


            arrive = datetime.combine(date.today(), pointage.heure_arrive)
            depart = datetime.combine(date.today(), now)
            heure_travail = depart - arrive
            heure_sup = heure_travail - JOUNEE_TRAVAIL

            pointage.minutes_travail = int(heure_travail.total_seconds() / 60)
            pointage.minutes_sup = int(heure_sup.total_seconds() / 60) if heure_sup.total_seconds() > 0 else 0

        db.commit()
        db.refresh(pointage)

    return match_found


@router.delete("/delete/{id}")
def delete_pointage(id: int, current_user: RequestModelEmp = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="You can not access from this route"
        )

    with get_db() as db:
        pointage = db.query(Pointage).filter(Pointage.id == id).first()

        if not pointage:
            raise HTTPException(status_code=404, detail="Pointage not found")

        db.delete(pointage)
        db.commit()

    return {"message": "Pointage supprimé avec succès"}
