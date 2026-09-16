from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from app.models.stock_movement import MovementType

class StockMovementBase(BaseModel):
    product_id: int
    point_of_sale_id: Optional[int] = None
    movement_type: MovementType
    quantity: int = Field(..., gt=0, description="Quantité déplacée (doit être positive)")
    reference: Optional[str] = None
    note: Optional[str] = None

class StockMovementCreate(StockMovementBase):
    pass

class StockMovementResponse(StockMovementBase):
    id: int
    created_at: datetime
    product_name: Optional[str] = None
    point_of_sale_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
