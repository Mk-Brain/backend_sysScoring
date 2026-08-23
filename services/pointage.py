import asyncio
import json
from datetime import date, datetime, time, timedelta
import time as tm

import cv2


import face_recognition_models
import numpy as np
from fastapi import HTTPException

from database.database import get_db
from models.employe import Employe
from sqlalchemy.orm import Session, joinedload

from models.pointages import Pointage, ScoringState

from pathlib import Path
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol

from services.auth import verify_access_token_stream
from shemas.pointage import ChangeStatusPointageRequest, ModelScoring
from utils.global_var import IMG_DIR, VIDEO_URL, FaceRecognitionSetting


net = FaceRecognitionSetting.net 
url = VIDEO_URL

"""fonction d'initialisation des pointages"""
def init_pointage(db: Session):
    today = date.today()
    all_user_ids = db.query(*[Employe.id]).filter(Employe.status == "actif").all()

    if not all_user_ids:
        print(" Aucun employé actif trouvé — init_pointage annulée")
        return

    for user_id  in all_user_ids:

        # verrification de l'exitance d'un pointage
        existing = db.query(Pointage).filter(
            Pointage.id_user == user_id[0],
            Pointage.date_day == today
        ).first()

        if existing:
            continue

        scoring = Pointage(
            date_day=date.today(),
            heure_arrive=None,
            heure_depart=None,
            status_arrivee=ScoringState.ABSENT,
            status_depart=ScoringState.ABSENT,
            photo_pointage_arrivee="",
            photo_pointage_depart="",
            numero_pointage = 0,
            minutes_travail = 0,
            minutes_sup = 0,
            id_user=user_id[0],
        )
        db.add(scoring)
    db.commit()


def take_picture(mat: str):
    """
    Capture le frame actuel, vérifie la présence d'un visage via DNN
    et sauvegarde le frame complet si un visage est détecté.
    On sauvegarde le frame complet (pas le crop) pour que
    face_recognition puisse faire sa propre détection avec plus de contexte.
    """

    cap = cv2.VideoCapture(url)

    ret, frame = cap.read()

    if frame is None or frame.size == 0:
        return False

    # DNN — détection de visage
    # blobFromImage gère lui-même le redimensionnement en 300x300
    blob = cv2.dnn.blobFromImage(
        frame, 1.0,
        (300, 300),
        (104.0, 177.0, 123.0)
    )
    net.setInput(blob)
    detections = net.forward()

    # Vérifier si au moins un visage est détecté avec confiance > 50%
    face_detected = any(
        detections[0, 0, i, 2] > 0.5
        for i in range(detections.shape[2])
    )

    if not face_detected:
        return False
    """
    Encode le visage depuis la photo capturée.
    Utilise model='small' (5 points) au lieu de 'large' (128 points)
    car 3x plus rapide et suffisant pour la comparaison.
    La conversion BGR->RGB est obligatoire car OpenCV lit en BGR
    et face_recognition attend du RGB.
    """
    save_path = IMG_DIR / mat / f"{datetime.now().date()}" / "img.png"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save = cv2.imwrite(str(save_path), frame)

    if not save:
        return False
    # BGR → RGB obligatoire pour face_recognition
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # model="small" — cohérent avec get_user_encoding()
    encs = face_recognition_models.face_encodings(img_rgb, model="small")
    cap.release()
    return encs if encs else None


def readqr(mat: str):
    scan_result = None
    timeout = 10
    start_time = tm.time()
    today = date.today().strftime("%d/%m/%Y")
    print(f"Début du scan QR code... {today}")

    cap = cv2.VideoCapture(url)

    while (tm.time() - start_time) < timeout:
        # Vérifie l'état du flux
        if not cap.isOpened():
            print("Erreur : Impossible d'ouvrir le flux vidéo")
            tm.sleep(0.05)
            continue

        ret, frame = cap.read()

        if not  ret:
            print("Erreur : Impossible d'ouvrir le flux vidéo")
            tm.sleep(0.05)
            continue

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
    cap.release()
    return qr



"""Récupère ou crée le pointage du jour"""
def get_or_create_pointage(db: Session, user_id: int) -> Pointage:
    """
    Récupère le pointage du jour ou le crée s'il n'existe pas.
    Permet de pointer même si l'initialisation n'a pas eu lieu.
    """
    pointage = db.query(Pointage).filter(
        Pointage.id_user == user_id,
        Pointage.date_day == date.today()
    ).first()

    if not pointage:
        pointage = Pointage(
            date_day=date.today(),
            heure_arrive=None,
            heure_depart=None,
            status_arrivee=ScoringState.ABSENT,
            status_depart=ScoringState.ABSENT,
            photo_pointage_arrivee="",
            photo_pointage_depart="",
            numero_pointage=0,
            minutes_travail=0,
            minutes_sup=0,
            id_user=user_id,
        )
        db.add(pointage)
        db.flush()  # assigne l'id sans valider la transaction

    return pointage

"""Compare les encodages et retourne distance + résultat"""
def calculer_match(picture_encode: list, user_encode) -> tuple[bool, float]:
    """
    Compare les encodages du visage capturé avec celui de référence.
    Retourne (match_found, best_distance).
    """
    best_distance = 1.0
    for detected_face_encoding in picture_encode:
        distance = face_recognition_models.face_distance([user_encode], detected_face_encoding)
        if distance[0] < best_distance:
            best_distance = distance[0]

    match_found = bool(best_distance < 0.5)
    return match_found, round(best_distance, 4)

"""Renomme et archive la photo capturée"""
def archiver_photo(matricule: str, numero: int) -> str:
    """
    Renomme img.png en imgN.png pour archiver la photo du pointage.
    Retourne le chemin du fichier archivé.
    """
    file = IMG_DIR / matricule / f"{date.today()}" / "img.png"

    if not file.exists():
        raise HTTPException(status_code=404, detail="Photo de pointage introuvable.")

    new_name = file.replace(
        IMG_DIR / matricule / f"{date.today()}" / f"img{numero}.png"
    )
    return str(new_name)

"""Met à jour les champs pour l'arrivée"""
def traiter_premier_pointage(
    pointage: Pointage,
    match_found: bool,
    best_distance: float,
    img_path: str,
    now: time,
    settings: dict,
) -> None:
    """
    Met à jour le pointage pour le 1er pointage (arrivée).
    Modifie l'objet pointage en place.
    """
    HEURE_LIMITE = settings["HEURE_LIMITE"]
    HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE = settings["HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE"]

    pointage.numero_pointage = 1
    pointage.heure_arrive = now
    pointage.photo_pointage_arrivee = img_path
    pointage.distance_arrivee = best_distance
    pointage.heure_depart = HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE
    pointage.status_depart = ScoringState.PRESENT

    pointage.status_arrivee = (
        ScoringState.PENDING if not match_found
        else ScoringState.RETARD if now > HEURE_LIMITE
        else ScoringState.PRESENT
    )

    fin = datetime.combine(date.today(), HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE)
    arrivee = datetime.combine(date.today(), now)
    delta = fin - arrivee
    pointage.minutes_travail = int(delta.total_seconds() / 60) if delta.total_seconds() > 0 else 0
    pointage.minutes_sup = 0

"""Met à jour les champs pour le départ"""
def traiter_deuxieme_pointage(
    pointage: Pointage,
    match_found: bool,
    best_distance: float,
    img_path: str,
    now: time,
    settings: dict,
) -> None:
    """
    Met à jour le pointage pour le 2ème pointage (départ).
    Modifie l'objet pointage en place.
    """
    JOUNEE_TRAVAIL = settings["JOUNEE_TRAVAIL"]

    pointage.numero_pointage = 2
    pointage.heure_depart = now
    pointage.photo_pointage_depart = img_path
    pointage.distance_depart = best_distance
    pointage.status_depart = ScoringState.PRESENT if match_found else ScoringState.PENDING

    arrive = datetime.combine(date.today(), pointage.heure_arrive)
    depart = datetime.combine(date.today(), now)
    heure_travail = depart - arrive
    heure_sup = heure_travail - timedelta(
        hours=JOUNEE_TRAVAIL.hour,
        minutes=JOUNEE_TRAVAIL.minute,
        seconds=JOUNEE_TRAVAIL.second
    )
    pointage.minutes_travail = int(heure_travail.total_seconds() / 60)
    pointage.minutes_sup = int(heure_sup.total_seconds() / 60) if heure_sup.total_seconds() > 0 else 0


"""Remet le pointage à zéro (ABSENT sur arrivée)"""
def reinitialiser_arrivee(pointage: Pointage) -> None:
    """
    Réinitialise complètement le pointage quand l'admin force ABSENT sur l'arrivée.
    Remet le pointage à l'état initial comme si l'employé n'avait jamais pointé.
    """
    pointage.heure_arrive = None
    pointage.heure_depart = None
    pointage.photo_pointage_arrivee = ""
    pointage.photo_pointage_depart = ""
    pointage.distance_arrivee = 1
    pointage.distance_depart = 1
    pointage.minutes_travail = 0
    pointage.minutes_sup = 0
    pointage.numero_pointage = 0
    pointage.status_arrivee = ScoringState.ABSENT
    pointage.status_depart = ScoringState.ABSENT

"""Efface le départ et recalcule le temps estimé"""
def reinitialiser_depart(pointage: Pointage, settings: dict) -> None:
    """
    Efface les données de départ quand l'admin force ABSENT sur le départ.
    Remet le pointage à l'état après le 1er pointage (arrivée uniquement).
    """
    HEURE_ARRIVEE = settings["HEURE_ARRIVEE"]
    HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE = settings["HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE"]

    pointage.numero_pointage = 1
    pointage.heure_depart = HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE
    pointage.photo_pointage_depart = ""
    pointage.distance_depart = 1
    pointage.status_depart = ScoringState.ABSENT

    # Recalcul du temps de travail estimé jusqu'à la limite du 2ème pointage
    heure_ref = pointage.heure_arrive if pointage.heure_arrive is not None else HEURE_ARRIVEE
    arrivee = datetime.combine(date.today(), heure_ref)
    fin = datetime.combine(date.today(), HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE)
    delta = fin - arrivee
    pointage.minutes_travail = int(delta.total_seconds() / 60) if delta.total_seconds() > 0 else 0
    pointage.minutes_sup = 0

"""Délègue selon numero_pointage et le statut demandé"""
def appliquer_changement_statut(
    pointage: Pointage,
    body: ChangeStatusPointageRequest,
    settings: dict,
) -> None:
    """
    Applique le changement de statut demandé par l'admin.
    Délègue à reinitialiser_arrivee() ou reinitialiser_depart() selon le cas.
    """
    if body.numero_pointage == 1:
        pointage.status_arrivee = body.status
        if body.status == ScoringState.ABSENT:
            reinitialiser_arrivee(pointage)

    elif body.numero_pointage == 2:
        pointage.status_depart = body.status
        if body.status == ScoringState.ABSENT:
            reinitialiser_depart(pointage, settings)

"""fournis les données de pointages en temps réel via SSE"""
async def prodige_donnees_pointages(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token_stream(token)

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
        await asyncio.sleep(3)