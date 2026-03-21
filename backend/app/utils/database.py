"""
ARM Platform - Database Configuration
SQLAlchemy + PostgreSQL 연결 설정
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://arm_user:arm_password@localhost:5432/arm_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends용 DB 세션 제공"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
