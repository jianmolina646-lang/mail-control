"""Sesión de SQLAlchemy con pool chico (VPS de 2 GB)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_use_lifo=True,
    connect_args={
        "options": (
            f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS} "
            "-c lock_timeout=10000 "
            f"-c idle_in_transaction_session_timeout="
            f"{settings.DB_IDLE_TRANSACTION_TIMEOUT_MS}"
        )
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
