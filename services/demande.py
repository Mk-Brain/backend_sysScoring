import asyncio
from datetime import  datetime, timedelta
import json
from operator import and_, or_
from pathlib import Path

from fastapi import HTTPException, UploadFile ,File

from database.database import get_db

from models.employe import Employe, StatutEmploye

from services.auth import verify_access_token_stream
from shemas.demande import InscriptionType
from utils.global_var import UPLOAD_DIR


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

async def verify_picture(photo: UploadFile = File(...)):
    ext = photo.filename.split(".")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail="File type not allowed")

    # verification de la taille
    content = await photo.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, detail="File too large")


async def prodige_donnees_dmd(token: str):
    while True:
        # Vérifier le token à chaque itération
        user = verify_access_token_stream(token)

        if user is None:
            # Envoyer un événement spécial au lieu de crasher
            yield f"event: token_expired\ndata: {{}}\n\n"
            break  # Arrêter le générateur

        with get_db() as db:
            donnees = db.query(Employe).all()
            payload = [
                InscriptionType.model_validate(d).model_dump(mode="json")
                for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)


async def save_img(matricule: str, photo: UploadFile | None):
    if photo is None:
        raise HTTPException(status_code=400, detail="Aucune photo fournie.")

    await verify_picture(photo)
    await photo.seek(0)

    image_path = Path(UPLOAD_DIR) / f"{matricule}.jpg"
    content = await photo.read()
    image_path.write_bytes(content)
    return str(image_path)


def rename_img(matricule: str, photo: str):
    original_path = Path(photo)
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Photo de référence introuvable.")

    new_path = Path(UPLOAD_DIR) / f"{matricule}.jpg"
    if original_path != new_path:
        original_path.replace(new_path)

    return str(new_path)


def delete_inscription():
    cutoff_datetime = datetime.now() - timedelta(days=7)
    cutoff_date = cutoff_datetime.date()
    cutoff_time = cutoff_datetime.time()

    with get_db() as db:
        expired_users = db.query(Employe).filter(
            Employe.status == StatutEmploye.PENDING,
            or_(
                Employe.request_date < cutoff_date,
                and_(
                    Employe.request_date == cutoff_date,
                    Employe.request_time <= cutoff_time
                )
            )
        ).all()

        for user in expired_users:
            """print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{user.request_date}\n >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{user.request_time}")
            print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{cutoff_date}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{cutoff_time}")"""
            if user.photo:
                photo_path = Path(user.photo)
                if photo_path.exists():
                    photo_path.unlink()

        for user in expired_users:
            db.delete(user)

        db.commit()