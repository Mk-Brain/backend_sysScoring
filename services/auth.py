import os
from dotenv import load_dotenv

from datetime import timezone
from typing import Optional

from database.database import get_db
from sqlalchemy.orm import Session


from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta

from models.employe import Employe, StatutEmploye

load_dotenv()

ALGORITHM = os.getenv('ALGORITHM') or 'HS256'
SECRET_KEY = os.getenv('SECRET_KEY') or 'your_secret_key_here'

REGISTRATION_TOKEN_EXPIRE_DAYS = int(os.getenv('REGISTRATION_TOKEN_EXPIRE_DAYS')) if os.getenv('REGISTRATION_TOKEN_EXPIRE_DAYS') else 7

pwd_context = CryptContext(schemes=["argon2"], deprecated= 'auto')

oauth2_scheme_standard = OAuth2PasswordBearer(
    tokenUrl='/auth/login',
    scheme_name="Jeton_Inscription",
    description="objet pour l'autentification générale",
    auto_error=False
)
oauth2_scheme_register = OAuth2PasswordBearer(
    tokenUrl="/auth/pre_loging",
    scheme_name="Jeton_Authentification",
    description="objet pour l'autentification pour accéder à une demande",
    auto_error=False,
)

def verify_password(plain_password, ashed_password):
    return pwd_context.verify(plain_password, ashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def get_user_by_id(id: int, db: Session):
    user_in_db = db.query(Employe).get(id)
    return user_in_db

def get_user_by_email(email: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.email == email).first()
    return user_in_db

def get_user_by_register_number(register_number: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.matricule == register_number).first()
    return user_in_db


credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

"""Check if username and password are correct."""
def authenticate_user( username: str, password: str, db: Session):
    # Recherche de l'utilisateur
    user = get_user_by_email(db=db, email=username)

    #  Validation de l'existence
    if not user:
        return False
        
    # Validation du mot de passe
    if not verify_password(password, user.password):
        return False
        
    return user


"""Create a JWT access token."""
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire, "purpose": "access_token"})
    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return encoded_jwt

"""Create a JWT refresh token."""
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=2)

    to_encode.update({"exp": expire, "purpose": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


"""Authentification de l'utilisateur à partir du token JWT"""
async def get_current_user(token: str = Depends(oauth2_scheme_standard)):
    if not token:
        raise HTTPException(status_code=401, detail="jeton manquant")
    
    user = verify_access_token(token)
    if user is None:
        raise credentials_exception
    if user.status != StatutEmploye.ACTIF:
        raise HTTPException(status_code=403, detail="Compte utilisateur inactif")
    return user



"""verification de token pour les routes de l'API"""
def verify_access_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        purpose: str = payload.get("purpose")
        if purpose != "access_token":
            raise HTTPException(status_code=403, detail="Ce jeton n'est pas autorisé à accéder à cette ressource.")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with get_db() as db:
        user = get_user_by_email(email, db)
    return user

"""verification de token pour les routes de l'API"""
def verify_refresh_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        purpose: str = payload.get("purpose")
        if purpose != "refresh_token":
            raise HTTPException(status_code=403, detail="Ce jeton n'est pas autorisé à accéder à cette ressource.")
        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    with get_db() as db:
        user = get_user_by_email(email, db)
    return user


"""verification de token pour les connexion sse"""
def verify_access_token_stream(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        purpose: str = payload.get("purpose")
        if purpose != "access_token":
            raise HTTPException(status_code=403, detail="Ce jeton n'est pas autorisé à accéder à cette ressource.")
        email = payload.get("sub")
        if email is None:
            return None

    except JWTError:
        return None

    with get_db() as db:
        user = get_user_by_email(email, db)

    return user


"""generation du token d'inscription pour la validation de l'inscription"""
def create_registration_token(user_email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REGISTRATION_TOKEN_EXPIRE_DAYS) # Valide 7 jours
    payload = {
        "sub": user_email,
        "purpose": "registration_preview", # La clé de notre sécurité
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


"""Authentification pour l'acces aux données d'inscription"""
async def get_current_pending_user(token: str = Depends(oauth2_scheme_register)):
    if token is None:
        raise HTTPException(status_code=401, detail="jeton manquant")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub")
        purpose = payload.get("purpose")
        if purpose != "registration_preview":
            raise HTTPException(status_code=403, detail="Ce jeton n'est pas autorisé à accéder à cette ressource.")

        if user_email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    with get_db() as db:
        user = get_user_by_email(user_email, db)

    if user is None:
        raise HTTPException(status_code=404, detail="Demande introuvable")

    return user