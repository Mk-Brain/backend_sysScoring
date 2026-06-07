import face_recognition

from models.employe import Employe
from sqlalchemy.orm import Session

from utils.global_var import FaceRecognitionSetting


def get_user_by_id(id: int, db = Session):
    user_in_db = db.query(Employe).get(id)
    return user_in_db

def get_user_by_email(email: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.email == email).first()
    return user_in_db

def get_user_by_register_number(register_number: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.matricule == register_number).first()
    return user_in_db


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
