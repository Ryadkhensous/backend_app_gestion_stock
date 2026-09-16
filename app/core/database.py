import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

logger = logging.getLogger("stock_app")
logging.basicConfig(level=logging.INFO)

class Base(DeclarativeBase):
    pass

def get_engine():
    global DATABASE_URL
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
            pool_recycle=1800,
            pool_timeout=30,
        )
        # Test connection
        with engine.connect() as conn:
            logger.info(f"Connected successfully to PostgreSQL database: {DATABASE_URL.split('@')[-1]}")
        return engine
    except Exception as e:
        logger.warning(
            f"Could not connect to PostgreSQL ({repr(e)}). "
            f"Falling back to local SQLite database (sqlite:///./gestion_stock.db) for development."
        )
        fallback_url = "sqlite:///./gestion_stock.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})

engine = get_engine()

# Optimisations haute performance pour SQLite
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
