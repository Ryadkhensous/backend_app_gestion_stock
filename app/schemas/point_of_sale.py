from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class PointOfSaleBase(BaseModel):
    name: str = Field(..., description="Nom de l'établissement ou magasin")
    address: str = Field(..., description="Adresse physique")
    city: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude GPS (-90 à 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude GPS (-180 à 180)")
    phone: Optional[str] = None
    manager_name: Optional[str] = None
    is_active: bool = True

class PointOfSaleCreate(PointOfSaleBase):
    pass

class PointOfSaleUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude GPS (-90 à 90)")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude GPS (-180 à 180)")
    phone: Optional[str] = None
    manager_name: Optional[str] = None
    is_active: Optional[bool] = None

class PointOfSaleResponse(PointOfSaleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
