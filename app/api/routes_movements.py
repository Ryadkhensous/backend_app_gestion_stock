from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from app.core.database import get_db
from app.models.product import Product
from app.models.point_of_sale import PointOfSale
from app.models.stock_movement import StockMovement, MovementType
from app.schemas.stock_movement import StockMovementCreate, StockMovementResponse

router = APIRouter(prefix="/stock-movements", tags=["Mouvements de Stock"])

@router.get("/", response_model=List[StockMovementResponse])
def get_stock_movements(
    product_id: Optional[int] = Query(None),
    point_of_sale_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(StockMovement).options(
        joinedload(StockMovement.product),
        joinedload(StockMovement.point_of_sale)
    )
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if point_of_sale_id:
        query = query.filter(StockMovement.point_of_sale_id == point_of_sale_id)
    
    movements = query.order_by(StockMovement.created_at.desc()).limit(limit).all()
    
    results = []
    for m in movements:
        item = StockMovementResponse.model_validate(m)
        item.product_name = m.product.name if m.product else "Produit inconnu"
        item.point_of_sale_name = m.point_of_sale.name if m.point_of_sale else None
        results.append(item)
    return results

@router.post("/", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
def record_stock_movement(payload: StockMovementCreate, db: Session = Depends(get_db)):
    # with_for_update() : verrouillage pessimiste pour éviter les race conditions sur le stock
    product = db.query(Product).filter(Product.id == payload.product_id).with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    
    if payload.point_of_sale_id:
        pos = db.query(PointOfSale).filter(PointOfSale.id == payload.point_of_sale_id).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Point de vente introuvable.")

    # Validation et mise à jour des stocks
    if payload.movement_type == MovementType.IN:
        product.quantity += payload.quantity
    elif payload.movement_type in (MovementType.OUT, MovementType.TRANSFER):
        if product.quantity < payload.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuffisant pour '{product.name}'. Disponible : {product.quantity}, Demandé : {payload.quantity}"
            )
        product.quantity -= payload.quantity

    movement = StockMovement(**payload.model_dump())
    db.add(movement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflit lors de l'enregistrement du mouvement. Veuillez réessayer.")
    db.refresh(movement)

    res = StockMovementResponse.model_validate(movement)
    res.product_name = product.name
    res.point_of_sale_name = movement.point_of_sale.name if movement.point_of_sale else None
    return res
