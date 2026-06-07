import numpy

class VideoSetting:
    camera_id = 0
    flag = False
    frame = None

class FaceRecognitionSetting:
    net = None                  # Initialisé dans le lifespan
    encoding_cache = {}         # Préchargé dans le lifespan