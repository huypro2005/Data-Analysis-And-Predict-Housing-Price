from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import BASE_DIR
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", f"sqlite:///{BASE_DIR / 'training_management.db'}")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.db import models  # noqa: F401 — đảm bảo models được import trước khi tạo bảng
    Base.metadata.create_all(bind=engine)
