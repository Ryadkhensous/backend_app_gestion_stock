import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/gestion_stock_db"
)
# Render, Supabase et d'autres plateformes utilisent parfois postgres:// qui n'est plus supporté tel quel par SQLAlchemy 2.x
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

API_V1_PREFIX = "/api"
PROJECT_NAME = "Stock & POS Management API"
VERSION = "1.0.0"

# Configuration Sécurité & JWT Multi-Tenant
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-stock-app-multi-tenant-2026-secure")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")) # 7 jours par défaut
