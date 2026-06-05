from fastapi import HTTPException, UploadFile ,File

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

