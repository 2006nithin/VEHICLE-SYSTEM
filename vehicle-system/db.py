import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get DB URL from environment (Render provides this)
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback to SQLite for local use
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./vehicle_system.db"

# Fix for PostgreSQL URL (Render gives postgres://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

# Engine setup
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base
Base = declarative_base()
