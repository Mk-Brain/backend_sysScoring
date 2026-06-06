from pathlib import Path



from fastapi import APIRouter
import cv2


from pyzbar.wrapper import ZBarSymbol


from services.auth import get_current_user
from database.database import get_db
from models.employe import Employe
from models.pointages import Pointage, ScoringState
from services.pointage import take_picture, encoding
from shemas.employe import RequestModelEmp
from shemas.pointage import ModelScoring
from pyzbar.pyzbar import decode

from utils.global_var import VideoSetting

from datetime import date, datetime, time# Ajout de datetime, time pour calculer_minutes_travail si besoin ailleurs

import time as  tm
import face_recognition
from fastapi import HTTPException, Depends


router = APIRouter(
    prefix="/pointage",
    tags=["pointage"]
)


"""Récupérer tous les pointages"""
@router.get("/", response_model=list[ModelScoring])
def get_all_pointages(current_user: RequestModelEmp | None = Depends(get_current_user)):
    if current_user and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    with get_db() as db:
        pointages = db.query(Pointage).all()
        if not pointages:
            return []
        return pointages

"""Récupérer tous les pointages d'un user specifique"""
@router.get("/my_scoring", response_model=list[ModelScoring])
def get_all_pointages(current_user: RequestModelEmp | None = Depends(get_current_user)):
    with get_db() as db:
        pointages = db.query(Pointage).filter(
            Pointage.id_user == current_user.id
        ).all()
        if not pointages:
            return []
        return pointages


"""Changer le status d'un pointages"""
@router.put("/modify_scoring", response_model=ModelScoring)
def chang_status(id: int, status: str, current_user: RequestModelEmp | None = Depends(get_current_user)):
    if current_user and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="we can not access from this route")
    to_update = Pointage()
    with get_db() as db:
        to_update = db.query(Pointage).get(id)
        if not to_update:
            raise HTTPException(status_code=400, detail="scoring not found")
        to_update.status = status
        db.commit()
        db.refresh(to_update)
    return to_update



"""lire le qr code"""
@router.get('/scan_qr')
def scan_qr(mat: str):
    scan_result = None
    timeout = 10  # Temps max de recherche en secondes
    start_time = tm.time()

    print("Début du scan QR code...")

    # On boucle tant qu'on n'a pas dépassé le timeout et qu'aucun QR code n'est trouvé
    while (tm.time() - start_time) < timeout:
        print(tm.time() - start_time)
        if VideoSetting.flag and VideoSetting.frame is not None:

            # Analyse de la frame actuelle du flux

            decoded_info = decode(VideoSetting.frame, symbols=[ZBarSymbol.QRCODE])
            print("test")
            for qrcode in decoded_info:
                print("test1")
                decoded_text = qrcode.data.decode("utf-8")
                if mat in decoded_text:
                    print("test 2")
                    print("QR Code correspondant détecté !")
                    scan_result = decoded_text
                    break

            if scan_result:
                break  # On sort de la boucle while si on a trouvé

        # Petite pause pour ne pas saturer le CPU (ex: 20 images par seconde)
        tm.sleep(0.05)

    # Si après la boucle (timeout), rien n'a été trouvé
    if not scan_result:
        print('Aucun QR code détecté dans le temps imparti')
        raise HTTPException(status_code=400, detail="Aucun QR code détecté")

    # Reste de votre logique Base de données
    with get_db() as db:
        emp = db.query(Employe).filter(Employe.qrCode == scan_result).first()

    if not emp:
        raise HTTPException(status_code=400, detail="Employé introuvable avec ce QR code")

    return scan_result

"""def scan_qr(mat: str):
    scan_result = None

    if VideoSetting.flag:
            print("frame")
            decoded_info = decode(VideoSetting.frame, symbols=[ZBarSymbol.QRCODE])

            for qrcode in decoded_info:
                if mat in qrcode.data.decode("utf-8",):
                    print("rq")
                    scan_result = qrcode.data.decode("utf-8")
                    break


    if not scan_result:
        print('none')
        raise HTTPException(status_code=400, detail="none image")
    print(scan_result)
    with get_db() as db:
        emp = db.query(Employe).filter(Employe.qrCode == scan_result).first()

    if not emp:
        raise HTTPException(status_code=400, detail="qrcode not found4")
    return scan_result"""


HEURE_LIMITE = time(8, 0)
@router.post('/pointer')
def pointer(
        current_user: RequestModelEmp = Depends(get_current_user),
):
    # Prendre une photo et encoder
    picture_encode = None
    if take_picture(current_user.matricule):
        picture_encode = encoding(current_user.matricule)

    if not picture_encode:
        raise HTTPException(status_code=400, detail="Aucun visage détecté dans l'image capturée.")

    # Chargement la photo de référence de l'employé
    try:
        user_img = face_recognition.load_image_file(current_user.photo)
        user_encodings = face_recognition.face_encodings(user_img)
        if not user_encodings:
            raise HTTPException(status_code=400,
                                detail="Aucun visage détecté dans la photo de référence.")
        user_encode = user_encodings[0]
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail=f"Photo de référence introuvable à {current_user.photo}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")

    with get_db() as db:
        # Récupérer le pointage du jour
        pointage = db.query(Pointage).filter(
            Pointage.id_user == current_user.id,
            Pointage.date_day == date.today()
        ).first()

        if not pointage:
            raise HTTPException(status_code=404,
                                detail="Pointage non trouvé pour aujourd'hui. Contactez l'administrateur.")

        # Comparer les visages
        match_found = False
        for detected_face_encoding in picture_encode:
            result = face_recognition.compare_faces([user_encode], detected_face_encoding)
            if True in result:
                match_found = True
                break

        # mise à jour du pointage
        now = datetime.now().time()
        img_path = str(Path.cwd().parent / "backend" / "img" / current_user.matricule / "img.png")

        if match_found:
            if pointage.heure_arrive is None:
                # pointage — arrivée
                pointage.heure_arrive = now
                pointage.photo_pointage = img_path

                if now > HEURE_LIMITE:
                    pointage.status = ScoringState.RETARD
                else:
                    pointage.status = ScoringState.PRESENT_PARTIEL
            else:
                # 2 pointage — départ
                pointage.heure_depart = now

                # Calcul heure de travail en minutes
                arrive = datetime.combine(date.today(), pointage.heure_arrive)
                depart = datetime.combine(date.today(), now)
                pointage.heure_travail = int((depart - arrive).total_seconds() / 60)

                if pointage.status == ScoringState.RETARD:
                    pointage.status = ScoringState.RETARD_PRESENT
                else:
                    pointage.status = ScoringState.PRESENT
        else:
            # Reconnaissance échouée
            pointage.status = ScoringState.PENDING

        db.commit()
        db.refresh(pointage)

    return match_found
