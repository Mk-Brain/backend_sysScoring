import os
from datetime import date, time, datetime
from pathlib import Path

import cv2
import face_recognition
import numpy as np
from fastapi import HTTPException

from models.employe import Employe
from sqlalchemy.orm import Session

from models.pointages import Pointage, ScoringState
from utils.global_var import VideoSetting

from pathlib import Path
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol
import time as tm

BASE_DIR = Path(__file__).parent

modelFile = str(BASE_DIR / "assets" / "res10_300x300_ssd_iter_140000_fp16.caffemodel")
configFile = str(BASE_DIR / "assets" / "deploy.prototxt")

net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


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

IMG_DIR = Path.cwd().parent / "backend" / "img" 

def take_picture(mat: str):
    """
    Capture le frame actuel, vérifie la présence d'un visage via DNN
    et sauvegarde le frame complet si un visage est détecté.
    On sauvegarde le frame complet (pas le crop) pour que
    face_recognition puisse faire sa propre détection avec plus de contexte.
    """
    url = "http://localhost:8000/video"
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
    encs = face_recognition.face_encodings(img_rgb, model="small")
    cap.release()
    return encs if encs else None


def readqr(mat: str):
    scan_result = None
    timeout = 10
    start_time = tm.time()
    today = date.today().strftime("%d/%m/%Y")
    print(f"Début du scan QR code... {today}")

    url = "http://localhost:8000/video"
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