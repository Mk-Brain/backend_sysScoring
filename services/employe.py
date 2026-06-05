from models.employe import Employe
from sqlalchemy.orm import Session


def get_user_by_id(id: int, db = Session):
    user_in_db = db.query(Employe).get(id)
    return user_in_db

def get_user_by_email(email: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.email == email).first()
    return user_in_db

def get_user_by_register_number(register_number: str, db: Session):
    user_in_db = db.query(Employe).filter(Employe.matricule == register_number).first()
    return user_in_db