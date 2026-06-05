from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

#from sqlalchemy.ext.asyncio import create_async_engine

from fastapi_crons.state.sqlalchemy import SQLAlchemyStateBackend


load_dotenv()

root = os.getenv('DATABASE_ROOT')
password = os.getenv('DATABASE_PASSWORD')
host = os.getenv('DATABASE_HOST')
db = os.getenv('DATABASE_NAME')

DATABASE_URL = f"mysql+pymysql://{root}:{password}@{host}/{db}"

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
backend = SQLAlchemyStateBackend(engine)

Base = declarative_base()

LocalSession = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@contextmanager
def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()