import os
from datetime import timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from services.auth import authenticate_user, create_access_token, create_refresh_token, create_registration_token, verify_refresh_token, get_current_user, \
    verify_password, get_password_hash
from database.database import get_db
from models.employe import Employe, StatutEmploye
from fastapi import APIRouter





ACCESS_TOKEN_EXPIRE_MINUTES: str | None = os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')
REFRESH_TOKEN_EXPIRE_DAYS: str | None = os.getenv('REFRESH_TOKEN_EXPIRE_DAYS')

expire_access = int(ACCESS_TOKEN_EXPIRE_MINUTES if ACCESS_TOKEN_EXPIRE_MINUTES is not None else 15)
expire_refresh = int(REFRESH_TOKEN_EXPIRE_DAYS if REFRESH_TOKEN_EXPIRE_DAYS is not None else 1)


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/login")
async def login_for_access_token( form_data: OAuth2PasswordRequestForm = Depends()):
    # À faire: authentifier l'utilisateur
    with get_db() as db:
        user = authenticate_user(form_data.username, form_data.password, db)
    #print(f"formulaire : {form_data.username}, {form_data.password}")

    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    if user.status != StatutEmploye.ACTIF:
        raise HTTPException(status_code=403, detail="Compte utilisateur inactif")
    # À faire: créer le token JWT
    access_token = create_access_token(data={"sub": user.email},
                                       expires_delta=timedelta(minutes=expire_access))
    refresh_token = create_refresh_token(data={"sub": user.email},
                                         expires_delta=timedelta(days=expire_refresh))

    return {"access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
            }



@router.post("/pre_loging")
async def login_for_access_token( form_data: OAuth2PasswordRequestForm = Depends()):
    with get_db() as db:
        user = authenticate_user(form_data.username, form_data.password, db)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    
    if user.status != StatutEmploye.PENDING:
        raise HTTPException(status_code=403, detail="Le compte à déjà été validé")

    registration_token = create_registration_token(user.email)
    return {
        "access_token": registration_token,
        "token_type": "bearer"
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh")
def refresh_token(payload: RefreshTokenRequest):
    user: Employe | None = verify_refresh_token(payload.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if user.status != StatutEmploye.ACTIF:
        raise HTTPException(status_code=403, detail="Compte utilisateur inactif")
    new_access_token = create_access_token({"sub": user.email})
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


class UpdatePasswordRequest(BaseModel):
    password: str
    new_password: str

@router.post("/update_password")
def update_password(
    payload: UpdatePasswordRequest,
    current_user: Employe = Depends(get_current_user)
):
    flag = verify_password(payload.password, current_user.password)
    if not flag:
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    new_password_hash = get_password_hash(payload.new_password)

    with get_db() as db:
        emp = db.query(Employe).get(current_user.id)
        emp.password = new_password_hash
        db.commit()

    return {"message": "success"}
