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
    current_date = datetime.today()
    all_user_id = db.query(*[Employe.id]).all()
    for id in all_user_id:
        scoring = Pointage(
            date_day = date.today(),
            heure_arrive = current_date.time(),
            heure_depart = current_date.time(),
            status = ScoringState.ABSENT,
            photo_pointage = "",
            id_user = id[0],
        )
        db.add(scoring)
    db.commit()
    print(">>>>>>>>>>message: pointages initialisés<<<<<<<<<<<<<<<")


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

    face_crop = None
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            startX, startY = max(0, startX), max(0, startY)
            endX, endY = min(w, endX), min(h, endY)

            face_crop = frame[startY:endY, startX:endX]
            break

    if face_crop is None or face_crop.size == 0:
        return False

    save_path = Path.cwd().parent / "backend" / "img" / mat / "img.png"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    return cv2.imwrite(str(save_path), face_crop)"""

def take_picture(mat: str):
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
    return cv2.imwrite(str(save_path), frame)


def encoding(mat: str):
    img_path = Path.cwd().parent / "backend" / "img" / mat / "img.png"

    # Vérifier que le fichier existe
    if not img_path.exists():
        return None

    img = cv2.imread(str(img_path))
    if img is None:
        return None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    #Encoder le visage
    encs = face_recognition.face_encodings(img_rgb)

    return encs if encs else None