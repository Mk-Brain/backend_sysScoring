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

from services.employe import get_user_by_email

load_dotenv()

ALGORITHM = os.getenv('ALGORITHM')

SECRET_KEY = os.getenv('SECRET_KEY')

pwd_context = CryptContext(schemes=["argon2"], deprecated= 'auto')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/token')

key = SECRET_KEY if SECRET_KEY is not None else ""
algo= ALGORITHM if ALGORITHM is not None else ""


def verify_password(plain_password, ashed_password):
    return pwd_context.verify(plain_password, ashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

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

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        key,
        algorithm=algo
    )
    return encoded_jwt

"""Create a JWT refresh token."""
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=2)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, key, algorithm=algo)


"""Get the current user from the JWT token."""
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, key, algorithms=ALGORITHM)
        email: str = payload.get("sub")
        print(email)
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    with get_db() as db:
        user = get_user_by_email(email, db)
    if user is None:
        raise credentials_exception
    return user

def verify_token(refresh_token: str, user_refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, key, algorithms=[ALGORITHM])
        email = payload.get("sub")

        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if refresh_token != user_refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    with get_db() as db:
        user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return user