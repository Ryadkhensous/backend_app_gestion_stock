from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, outerjoin
from typing import List
from app.core.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

from app.core.dependencies import get_current_tenant_id

router = APIRouter(prefix="/categories", tags=["Catégories"])

@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    # Requête optimisée : une seule jointure SQL avec COUNT au lieu d'un N+1, filtrée par locataire
    results = (
        db.query(Category, func.count(Product.id).label("products_count"))
        .filter(Category.tenant_id == tenant_id)
        .outerjoin(Product, (Product.category_id == Category.id) & (Product.tenant_id == tenant_id))
        .group_by(Category.id)
        .order_by(Category.name)
        .all()
    )
    categories_response = []
    for cat, count in results:
        cat_dict = CategoryResponse.model_validate(cat)
        cat_dict.products_count = count
        categories_response.append(cat_dict)
    return categories_response

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    existing = db.query(Category).filter(
        Category.tenant_id == tenant_id,
        Category.name.ilike(payload.name),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une catégorie avec ce nom existe déjà dans votre magasin.")
    
    cat_data = payload.model_dump()
    cat_data["tenant_id"] = tenant_id
    cat = Category(**cat_data)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    res = CategoryResponse.model_validate(cat)
    res.products_count = 0
    return res

@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    cat = db.query(Category).filter(
        Category.id == category_id,
        Category.tenant_id == tenant_id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    # Requête de count optimisée pour la réponse de mise à jour
    count = db.query(func.count(Product.id)).filter(
        Product.category_id == cat.id,
        Product.tenant_id == tenant_id,
    ).scalar() or 0
    res = CategoryResponse.model_validate(cat)
    res.products_count = count
    return res

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    cat = db.query(Category).filter(
        Category.id == category_id,
        Category.tenant_id == tenant_id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée.")
    db.delete(cat)
    db.commit()
    return None
