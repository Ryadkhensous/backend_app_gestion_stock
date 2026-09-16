from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from app.schemas.category import CategoryResponse

class ProductBase(BaseModel):
    name: str
    sku: str = Field(..., description="Référence produit ou code-barres")
    description: Optional[str] = None
    price: float = Field(0.0, ge=0.0)
    cost_price: float = Field(0.0, ge=0.0)
    quantity: int = Field(0, ge=0)
    min_stock_alert: int = Field(5, ge=0)
    category_id: Optional[int] = None
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0, description="Prix de vente (>= 0)")
    cost_price: Optional[float] = Field(None, ge=0.0, description="Coût d'achat (>= 0)")
    quantity: Optional[int] = Field(None, ge=0, description="Quantité en stock (>= 0)")
    min_stock_alert: Optional[int] = Field(None, ge=0, description="Seuil d'alerte stock bas (>= 0)")
    category_id: Optional[int] = None
    image_url: Optional[str] = None

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_low_stock: bool
    category: Optional[CategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)
