import asyncio
import json
from pathlib import Path

import face_recognition

from database.database import get_db
from models.employe import Employe
from sqlalchemy.orm import Session

from services.auth import verify_access_token_stream
from shemas.employe import ResponseModelEmp
from utils.global_var import FaceRecognitionSetting





def preload_cache(db: Session):
    """Charge les encodages de tous les employés au démarrage"""
    employes = db.query(Employe).all()
    for employe in employes:
        _load_encoding(employe.id, employe.photo)
    print(f" {len(FaceRecognitionSetting.encoding_cache)} encodages chargés")

def _load_encoding(user_id: int, photo_path: str):
    """Charge et met en cache l'encodage d'un employé"""
    try:
        user_img = face_recognition.load_image_file(photo_path)
        # model="small" — 3x plus rapide, suffisant pour la reconnaissance
        user_encodings = face_recognition.face_encodings(user_img, model="small")
        if user_encodings:
            FaceRecognitionSetting.encoding_cache[user_id] = user_encodings[0]
            return True
    except Exception as e:
        print(f"Impossible de charger l'encodage {user_id} : {str(e)}")
    return False

def get_user_encoding(user_id: int, photo_path: str):
    """Retourne l'encodage depuis le cache, le charge si absent"""
    if user_id not in FaceRecognitionSetting.encoding_cache:
        # Employé ajouté après le démarrage — chargement dynamique
        if not _load_encoding(user_id, photo_path):
            return None
    return FaceRecognitionSetting.encoding_cache[user_id]

def invalidate_user_cache(user_id: int):
    """À appeler quand la photo de référence d'un employé est mise à jour"""
    if user_id in FaceRecognitionSetting.encoding_cache:
        del FaceRecognitionSetting.encoding_cache[user_id]
        print(f"Cache invalidé pour l'employé {user_id}")

def clear_cache():
    """Vidage du cache à minuit — à brancher sur le cron"""
    FaceRecognitionSetting.encoding_cache.clear()
    print("Cache des encodages vidé")

async def prodige_donnees_emp(token: str):
    while True:
        user = verify_access_token_stream(token)

        if user is None:
            yield "event: token_expired\ndata: {}\n\n"
            break

        with get_db() as db:
            donnees = db.query(Employe).all()
            payload = [
                ResponseModelEmp.model_validate(d).model_dump(mode="json")
                for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        await asyncio.sleep(2)

def delete_picture(path: str):
    try:
        picture = Path(path)
        if picture.exists() and picture.is_file():
                picture.unlink()
    except OSError as e:
        print(f"Erreur suppression photo: {e}")