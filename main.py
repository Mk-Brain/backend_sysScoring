
import threading
import calendar
from datetime import date

import cv2
from dotenv import load_dotenv
from fastapi import  FastAPI
from fastapi_crons import Crons

from database.database import  backend, get_db
from models.employe import Employe
from routes.employe import router as employe_router
from routes.pointage import router as pointage_router
from routes.demandes import router as demande_router
from routes.auth import router as auth_router
from routes.statistiques import router as stats_router
from services.pointage import init_pointage
from services.statitiques import init_stats_week, init_stats_month, init_stats_year, \
    traitement_statistiques_journalieres

from utils.global_var import VideoSetting

# Initialiser les tables
#Base.metadata.create_all(engine)

load_dotenv()

app = FastAPI(
    title="Système de Pointage",
    description="API pour gestion des employés et du pointage pointage de presence",
    version="1.0.0"
)

crons = Crons(app, state_backend=backend)



# Inclusion les routes
app.include_router(employe_router)
app.include_router(pointage_router)
app.include_router(demande_router)
app.include_router(auth_router)
app.include_router(stats_router)

@app.get('/')
def home():
    return {"message": "Bienvenue au système de pointage"}

@app.get('/health')
def health_check():
    return {"status": "OK"}

#@crons.cron("0 16 * * *", name="intit_scoring")
#@crons.cron("* * * * * ", name="init_week_stats")
def init_scoring():
    with get_db() as db:
        return  init_pointage(db=db)

current_date = date.today()

#@crons.cron("0 7 * * 6", name="init_week_stats")
#@crons.cron("5 * * * *", name="init_week_stats")
def init_week_stats():
    with get_db() as db:
        id_users = db.query(Employe.id).all()
        for id_user in id_users:
            init_stats_week(
                db=db,
                employe_id=id_user[0],
                date_debut=date(current_date.year, current_date.month, current_date.day - calendar.weekday(current_date.year, current_date.month, current_date.day)),
                date_fin=date(current_date.year, current_date.month, current_date.day + (6 - calendar.weekday(current_date.year, current_date.month, current_date.day)))
            )
            db.commit()

#@crons.cron("0 7 30 * *", name="init_month_stats")
#@crons.cron("5 * * * *", name="init_week_stats")
def init_month_stats():
    with get_db() as db:
        id_users = db.query(Employe.id).all()
        for id_user in id_users:
            init_stats_month(
                db=db,
                employe_id=id_user[0],
                date_debut=date(current_date.year, current_date.month, 1),
                date_fin=date(current_date.year, current_date.month, calendar.monthrange(current_date.year, current_date.month)[1]))
            db.commit()

#@crons.cron("0 7 31 12 *", name="init_year_stats")
#@crons.cron("5 * * * *", name="init_week_stats")
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


#@crons.cron("0 23 * * *", name="update stats")
#@crons.cron("10 * * * *", name="init_week_stats")
def lancer_mise_a_jour_statistiques():
    with get_db() as db:
        try:
            traitement_statistiques_journalieres(db)

        finally:
            db.close()

@app.on_event("startup")
def start_startup():
    threading.Thread(target=start_read, daemon=True).start()

"""lancer l'enregistrement video"""
def start_read():
    cap = cv2.VideoCapture(VideoSetting.camera_id)
    while True:
        VideoSetting.flag, VideoSetting.frame = cap.read()
