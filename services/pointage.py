import os
from datetime import date, time, datetime
from pathlib import Path

import cv2
import face_recognition
import numpy as np

from models.employe import Employe
from sqlalchemy.orm import Session

from models.pointages import Pointage, ScoringState
from utils.global_var import VideoSetting

from pathlib import Path

BASE_DIR = Path(__file__).parent

modelFile = str(BASE_DIR / "assets" / "res10_300x300_ssd_iter_140000_fp16.caffemodel")
configFile = str(BASE_DIR / "assets" / "deploy.prototxt")

net = cv2.dnn.readNetFromCaffe(configFile, modelFile)

"""fonction d'initialisation des pointages"""
def init_pointage(db: Session):
    """
    Initialise les pointages du jour pour tous les employés.
    Les heures sont nulles — elles seront renseignées au pointage.
    Le statut par défaut est ABSENT.
    """
    all_user_ids = db.query(Employe.id).all()
    for (user_id,) in all_user_ids:
        scoring = Pointage(
            date_day=date.today(),
            heure_arrive=None,      # None au lieu de l'heure actuelle
            heure_depart=None,      # None au lieu de l'heure actuelle
            status=ScoringState.ABSENT,
            photo_pointage="",
            id_user=user_id,
        )
        db.add(scoring)
    db.commit()
    print("Pointages initialisés")


"""def take_picture(mat: str):
    frame = VideoSetting.frame

    if frame is None or frame.size == 0:
        return False

    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)), 1.0,
        (300, 300), (104.0, 177.0, 123.0)
    )
    net.setInput(blob)
    detections = net.forward()

    #vérifier qu'un visage est présent
    face_detected = False
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            face_detected = True
            break

    if not face_detected:
        return False

    # Sauvegarder le frame entier
    save_path = Path.cwd().parent / "backend" / "img" / mat / "img.png"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    return cv2.imwrite(str(save_path), frame)"""

IMG_DIR = Path.cwd().parent / "backend" / "img"

def take_picture(mat: str) -> bool:
    """
    Capture le frame actuel, vérifie la présence d'un visage via DNN
    et sauvegarde le frame complet si un visage est détecté.
    On sauvegarde le frame complet (pas le crop) pour que
    face_recognition puisse faire sa propre détection avec plus de contexte.
    """
    frame = VideoSetting.frame

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

    # Sauvegarder le frame original complet
    save_path = IMG_DIR / mat / "img.png"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    return cv2.imwrite(str(save_path), frame)


def encoding(mat: str):
    """
    Encode le visage depuis la photo capturée.
    Utilise model='small' (5 points) au lieu de 'large' (128 points)
    car 3x plus rapide et suffisant pour la comparaison.
    La conversion BGR->RGB est obligatoire car OpenCV lit en BGR
    et face_recognition attend du RGB.
    """
    img_path = IMG_DIR / mat / "img.png"

    if not img_path.exists():
        return None

    img = cv2.imread(str(img_path))
    if img is None:
        return None

    # BGR → RGB obligatoire pour face_recognition
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # model="small" — cohérent avec get_user_encoding()
    encs = face_recognition.face_encodings(img_rgb, model="small")
    return encs if encs else None
