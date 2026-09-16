import sys
from pathlib import Path
from contextlib import asynccontextmanager
import logging

# Assure que le dossier 'backend' est toujours dans sys.path quel que soit le dossier de lancement
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import PROJECT_NAME, VERSION, API_V1_PREFIX
from app.core.database import engine, Base, SessionLocal
# L'import des modèles permet d'enregistrer toutes les tables dans les métadonnées SQLAlchemy
from app.models import Product  # noqa: F401
from app.api.routes_categories import router as categories_router
from app.api.routes_products import router as products_router
from app.api.routes_points_of_sale import router as pos_router
from app.api.routes_movements import router as movements_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_documents import router as documents_router
from app.api.routes_pos import router as pos_checkout_router
from app.api.routes_inventory import router as inventory_router
from app.api.routes_analytics import router as analytics_router

logger = logging.getLogger("stock_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création automatique des tables dans la base de données
    logger.info("Création et vérification des tables en base de données...")
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="API REST de gestion de stock et cartographie Google Maps des points de vente",
    lifespan=lifespan
)

# Configuration CORS pour autoriser les requêtes depuis Flutter (mobile, émulateur et web)
# Note : allow_credentials=True est incompatible avec allow_origins=["*"] selon la spec CORS.
# Si une authentification par cookies est ajoutée, remplacer ["*"] par les domaines explicites.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compression GZIP pour réduire de 70-90% la taille des transferts JSON
app.add_middleware(GZipMiddleware, minimum_size=500)

# Enregistrement des routes de l'API
app.include_router(dashboard_router, prefix=API_V1_PREFIX)
app.include_router(products_router, prefix=API_V1_PREFIX)
app.include_router(categories_router, prefix=API_V1_PREFIX)
app.include_router(pos_router, prefix=API_V1_PREFIX)
app.include_router(movements_router, prefix=API_V1_PREFIX)
app.include_router(documents_router, prefix=API_V1_PREFIX)
app.include_router(pos_checkout_router, prefix=API_V1_PREFIX)
app.include_router(inventory_router, prefix=API_V1_PREFIX)
app.include_router(analytics_router, prefix=API_V1_PREFIX)
 
# Servir les fichiers uploadés (images de produits, logos, etc.)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "products").mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="static_uploads")

@app.get("/")
def root():
    return {
        "app": PROJECT_NAME,
        "version": VERSION,
        "status": "online",
        "docs": "/docs"
    }
