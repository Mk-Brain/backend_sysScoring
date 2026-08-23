from datetime import time
from pathlib import Path


"""paramètres de la caméra"""
class VideoSetting:
    camera_id = 0
    flag = False
    frame = None

"""paramètres de reconnaissance faciale"""
class FaceRecognitionSetting:
    net = None                  
    encoding_cache = {}         

"""paramètres horaire de l'application"""
class SettingApp:
    setting_cash: dict[str, time] = {
        "HEURE_ARRIVEE":  time(hour=8, minute=0),
        "HEURE_DEPART":  time(hour=16, minute=0),
        "HEURE_TOLEREE":  time(hour=8, minute=30),
        "JOUNEE_TRAVAIL":  time(hour=8, minute=0),
        "HEURE_LIMITE_AVANT_ABSENCE":  time(hour=9, minute=0),
        "HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE":  time(hour=10, minute=0)
    }

"""url du flux vidéo"""
VIDEO_URL = "http://192.168.10.150:8001/videostream"

BASE_DIR = Path(__file__).parent.parent

"""repertoire des photo des employés"""
UPLOAD_DIR = BASE_DIR / "assets" / "users_pictures"

"""repertoire des photos de pointages"""
IMG_DIR = BASE_DIR /"assets" / "scoring_img"

# ── Modèle DNN ──
modelFile = BASE_DIR / "assets" / "res10_300x300_ssd_iter_140000_fp16.caffemodel"
configFile = BASE_DIR / "assets" / "deploy.prototxt"