from datetime import time

import numpy

class VideoSetting:
    camera_id = 0
    flag = False
    frame = None

class FaceRecognitionSetting:
    net = None                  # Initialisé dans le lifespan
    encoding_cache = {}         # Préchargé dans le lifespan

class SettingApp:
    setting_cash: dict[str, time] = {
        "HEURE_ARRIVEE":  time(hour=8, minute=0),
        "HEURE_DEPART":  time(hour=16, minute=0),
        "HEURE_TOLEREE":  time(hour=8, minute=30),
        "JOUNEE_TRAVAIL":  time(hour=8, minute=0),
        "HEURE_LIMITE_AVANT_ABSENCE":  time(hour=9, minute=0),
        "HEURE_LIMITE_AVANT_DEUXIEME_POINTAGE":  time(hour=10, minute=0)
    }