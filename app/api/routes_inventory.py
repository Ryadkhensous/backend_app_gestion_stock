from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import random

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.models.product import Product
from app.models.point_of_sale import PointOfSale
from app.models.stock_movement import StockMovement, MovementType

router = APIRouter(prefix="/inventory", tags=["Inventaire Physique & Réconciliation"])

class InventoryCountItem(BaseModel):
    product_id: int
    counted_quantity: int
    note: Optional[str] = None

class InventoryReconciliationRequest(BaseModel):
    items: List[InventoryCountItem]
    point_of_sale_id: Optional[int] = None
    session_title: Optional[str] = "Inventaire Physique"

class ReconciledItemResult(BaseModel):
    product_id: int
    product_name: str
    product_sku: str
    before_quantity: int
    counted_quantity: int
    variance: int
    adjustment_type: str

class InventoryReconciliationResponse(BaseModel):
    reference: str
    session_title: str
    total_reviewed: int
    total_adjusted: int
    adjustments: List[ReconciledItemResult]
    timestamp: datetime

@router.post("/reconcile", response_model=InventoryReconciliationResponse)
def reconcile_inventory(
    payload: InventoryReconciliationRequest,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Aucun article transmis pour la réconciliation.")

    # Vérifier POS si fourni
    if payload.point_of_sale_id:
        pos = db.query(PointOfSale).filter(
            PointOfSale.id == payload.point_of_sale_id,
            PointOfSale.tenant_id == tenant_id
        ).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Point de vente sélectionné introuvable.")

    date_str = datetime.now().strftime("%Y%m%d")
    random_suffix = random.randint(100, 999)
    session_ref = f"INV-{date_str}-{random_suffix}"

    adjusted_results = []
    movements = []

    for item in payload.items:
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            continue

        before_qty = product.quantity
        counted_qty = max(0, item.counted_quantity)
        variance = counted_qty - before_qty

        if variance != 0:
            # Appliquer le nouveau stock physique
            product.quantity = counted_qty

            if variance > 0:
                adj_type = "SURPLUS (IN)"
                mov = StockMovement(
                    tenant_id=tenant_id,
                    product_id=product.id,
                    point_of_sale_id=payload.point_of_sale_id,
                    movement_type=MovementType.IN,
                    quantity=variance,
                    reference=session_ref,
                    note=f"Ajustement Inventaire (+{variance} unités) - {item.note or payload.session_title}"
                )
                movements.append(mov)
            else:
                adj_type = "DEFICIT (OUT)"
                mov = StockMovement(
                    tenant_id=tenant_id,
                    product_id=product.id,
                    point_of_sale_id=payload.point_of_sale_id,
                    movement_type=MovementType.OUT,
                    quantity=abs(variance),
                    reference=session_ref,
                    note=f"Ajustement Inventaire ({variance} unités) - {item.note or payload.session_title}"
                )
                movements.append(mov)

            adjusted_results.append(ReconciledItemResult(
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku,
                before_quantity=before_qty,
                counted_quantity=counted_qty,
                variance=variance,
                adjustment_type=adj_type
            ))

    for m in movements:
        db.add(m)

    db.commit()

    return InventoryReconciliationResponse(
        reference=session_ref,
        session_title=payload.session_title or "Inventaire Physique",
        total_reviewed=len(payload.items),
        total_adjusted=len(adjusted_results),
        adjustments=adjusted_results,
        timestamp=datetime.now(timezone.utc)
    )
