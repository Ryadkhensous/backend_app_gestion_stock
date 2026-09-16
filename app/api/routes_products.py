import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads" / "products"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/products", tags=["Produits"])

@router.post("/upload-image")
async def upload_product_image(file: UploadFile = File(...)):
    """
    Télécharge une image de produit depuis l'appareil utilisateur
    et renvoie son chemin accessible sur le serveur.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    raw_ext = Path(file.filename or "").suffix.lower()
    
    if raw_ext in allowed_extensions:
        ext = raw_ext
    elif file.content_type and "image" in file.content_type:
        if "png" in file.content_type:
            ext = ".png"
        elif "webp" in file.content_type:
            ext = ".webp"
        elif "gif" in file.content_type:
            ext = ".gif"
        else:
            ext = ".jpg"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier non pris en charge. Formats acceptés : JPG, PNG, WEBP, GIF."
        )

    unique_filename = f"prod_{uuid.uuid4().hex}{ext}"
    destination = UPLOAD_DIR / unique_filename

    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    return {
        "url": f"/static/uploads/products/{unique_filename}",
        "filename": unique_filename,
    }

@router.get("/", response_model=List[ProductResponse])
def get_products(
    search: Optional[str] = Query(None, description="Recherche par nom ou référence SKU"),
    category_id: Optional[int] = Query(None, description="Filtrer par catégorie"),
    low_stock_only: bool = Query(False, description="Afficher uniquement les articles en alerte stock"),
    db: Session = Depends(get_db)
):
    query = db.query(Product).options(joinedload(Product.category))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter((Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if low_stock_only:
        query = query.filter(Product.quantity <= Product.min_stock_alert)
    
    products = query.order_by(Product.name).all()
    return products

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).options(joinedload(Product.category)).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    return product

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    existing = db.query(Product).filter(Product.sku.ilike(payload.sku)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un produit avec ce SKU existe déjà.")
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    if payload.sku and payload.sku != product.sku:
        existing = db.query(Product).filter(Product.sku.ilike(payload.sku), Product.id != product_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Cette référence SKU est déjà utilisée.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    db.delete(product)
    db.commit()
    return None
