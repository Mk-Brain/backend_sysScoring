from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import cv2

from dotenv import load_dotenv
from fastapi import  FastAPI
from fastapi_crons import Crons
from fastapi.middleware.cors import CORSMiddleware

from database.database import backend, get_db

from routes.employe import router as employe_router
from routes.pointage import router as pointage_router
from routes.demandes import router as demande_router
from routes.auth import router as auth_router
from routes.statistiques import router as stats_router
from routes.settings import router as settings_router
from services.Setting import get_settings
from services.employe import preload_cache, clear_cache
from services.pointage import init_pointage

from utils.global_var import VideoSetting, FaceRecognitionSetting


load_dotenv()

# ── Modèle DNN ──
BASE_DIR = Path(__file__).parent
modelFile = str(BASE_DIR / "assets" / "res10_300x300_ssd_iter_140000_fp16.caffemodel")
configFile = str(BASE_DIR / "assets" / "deploy.prototxt")
#FaceRecognitionSetting.net = cv2.dnn.readNetFromCaffe(configFile, modelFile)




# ── Caméra ──
def start_read():
    """Lecture continue du flux vidéo dans un thread séparé"""
    cap = cv2.VideoCapture(VideoSetting.camera_id)
    while True:
        VideoSetting.flag, VideoSetting.frame = cap.read()


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Démarrer la caméra
    """thread = threading.Thread(target=start_read, daemon=True)
    thread.start()
    print("Caméra démarrée")"""

    with get_db() as db:
        #  Précharger le cache des encodages
        preload_cache(db)
        # 2. initialiser les pointages
        init_pointage(db=db)
        # 2. Précharger les paramètres
        get_settings(db)

    print("Application prête")
    yield
    # ── Arrêt ──
    FaceRecognitionSetting.encoding_cache.clear()
    print("Serveur arrêté")

# ── Application ──
app = FastAPI(
    title="Système de Pointage",
    description="API pour gestion des employés et du pointage de présence",
    version="1.0.0",
    lifespan=lifespan
)

crons = Crons(app, state_backend=backend)

# ── Crons ──
current_date = date.today()

@crons.cron(expr="0 0 * * *", name="init scoring")
def init_scoring():
    with get_db() as db:
        return init_pointage(db=db)

@crons.cron(expr="0 0 * * *", name="clear cache")
def clear_():
    """Vidage du cache à minuit"""
    clear_cache()




origins = [
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ── Routes ──
app.include_router(employe_router)
app.include_router(pointage_router)
app.include_router(demande_router)
app.include_router(auth_router)
app.include_router(stats_router)
app.include_router(settings_router)


@app.get('/')
def home():
    return {"message": "Bienvenue au système de pointage"}

@app.get('/health')
def health_check():
    return {"status": "OK"}

