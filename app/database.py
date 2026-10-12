import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./bulk_certificates.db")
    if value.startswith("sqlite") and "check_same_thread" not in value:
        return value
    return value


def make_engine(url: str | None = None):
    selected = url or database_url()
    options = {"check_same_thread": False} if selected.startswith("sqlite") else {}
    return create_engine(selected, connect_args=options)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
