import threading
import calendar
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import cv2
from apscheduler.triggers import cron
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi_crons import Crons
from fastapi.middleware.cors import CORSMiddleware

from database.database import backend, get_db
from models.config import Parametre
from models.employe import Employe
from routes.employe import router as employe_router
from routes.pointage import router as pointage_router
from routes.demandes import router as demande_router
from routes.auth import router as auth_router
from routes.statistiques import router as stats_router
from routes.settings import router as settings_router
from services.Setting import get_settings
from services.employe import preload_cache, clear_cache
from services.pointage import init_pointage
from services.statitiques import (init_stats_week, init_stats_month,
                                   init_stats_year, traitement_statistiques_journalieres)

from utils.global_var import VideoSetting, FaceRecognitionSetting


load_dotenv()

# ── Modèle DNN ──
BASE_DIR = Path(__file__).parent
modelFile = str(BASE_DIR / "assets" / "res10_300x300_ssd_iter_140000_fp16.caffemodel")
configFile = str(BASE_DIR / "assets" / "deploy.prototxt")

# Verify model files exist on startup
if not os.path.exists(modelFile):
    raise FileNotFoundError(f"Face recognition model file not found: {modelFile}")
if not os.path.exists(configFile):
    raise FileNotFoundError(f"Face recognition config file not found: {configFile}")

print("Face recognition models verified at startup")
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

    # 2. Précharger le cache des encodages
    with get_db() as db:
        preload_cache(db)
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

@crons.cron(expr="09 11 * * *", name="init scoring")
def init_scoring():
    with get_db() as db:
        return init_pointage(db=db)

#@crons.cron(expr="14 * * * 7", name="init week stats")
def init_week_stats():
    with get_db() as db:
        id_users = db.query(Employe.id).all()
        for id_user in id_users:
            init_stats_week(
                db=db,
                employe_id=id_user[0],
                date_debut=date(current_date.year, current_date.month,
                                current_date.day - calendar.weekday(current_date.year, current_date.month, current_date.day)),
                date_fin=date(current_date.year, current_date.month,
                              current_date.day + (6 - calendar.weekday(current_date.year, current_date.month, current_date.day)))
            )
            db.commit()

#@crons.cron(expr="20 * * * *", name="init month stats")
def init_month_stats():
    with get_db() as db:
        id_users = db.query(Employe.id).all()
        for id_user in id_users:
            init_stats_month(
                db=db,
                employe_id=id_user[0],
                date_debut=date(current_date.year, current_date.month, 1),
                date_fin=date(current_date.year, current_date.month,
                              calendar.monthrange(current_date.year, current_date.month)[1])
            )
            db.commit()

#@crons.cron(expr="20 * * * *", name="init year stats")
def init_year_stats():
    with get_db() as db:
        id_users = db.query(Employe.id).all()
        for id_user in id_users:
            init_stats_year(
                db=db,
                employe_id=id_user[0],
                date_debut=date(year=current_date.year, month=1, day=1),
                date_fin=date(year=current_date.year, month=12, day=31)
            )
            db.commit()

#@crons.cron(expr="*/2 * * * *", name="update statistiques")
def lancer_mise_a_jour_statistiques():
    with get_db() as db:
        try:
            traitement_statistiques_journalieres(db)
        finally:
            db.close()

@crons.cron(expr="0 0 * * *", name="clear cache")
def clear_():
    """Vidage du cache à minuit"""
    clear_cache()




# CORS configuration - load allowed origins from environment
# Fallback to localhost origins for development
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8080,http://localhost"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
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
