import asyncio
import json

from fastapi import HTTPException, UploadFile ,File

from database.database import get_db
from models.demandes import DemandesInscription
from services.auth import verify_access_token_stream
from shemas.demande import ResponseRequest

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
            donnees = db.query(DemandesInscription).all()
            payload = [
                ResponseRequest.model_validate(d).model_dump(mode="json")
                for d in donnees
            ]

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)