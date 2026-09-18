import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.point_of_sale import PointOfSale
from app.schemas.point_of_sale import PointOfSaleCreate, PointOfSaleUpdate, PointOfSaleResponse

from app.core.dependencies import get_current_tenant_id

router = APIRouter(prefix="/points-of-sale", tags=["Points de Vente & Cartographie"])

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Rayon de la Terre en km
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.get("/", response_model=List[PointOfSaleResponse])
def get_points_of_sale(
    active_only: bool = Query(False, description="Afficher seulement les points de vente actifs"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(PointOfSale).filter(PointOfSale.tenant_id == tenant_id)
    if active_only:
        query = query.filter(PointOfSale.is_active == True)
    return query.order_by(PointOfSale.name).all()

@router.get("/nearby", response_model=List[PointOfSaleResponse])
def get_nearby_points_of_sale(
    lat: float = Query(..., description="Latitude actuelle"),
    lng: float = Query(..., description="Longitude actuelle"),
    radius_km: float = Query(50.0, description="Rayon de recherche en km"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    all_pos = db.query(PointOfSale).filter(
        PointOfSale.tenant_id == tenant_id,
        PointOfSale.is_active == True,
    ).all()
    nearby = []
    for pos in all_pos:
        dist = haversine_distance(lat, lng, pos.latitude, pos.longitude)
        if dist <= radius_km:
            nearby.append(pos)
    return nearby

@router.get("/{pos_id}", response_model=PointOfSaleResponse)
def get_point_of_sale(
    pos_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    pos = db.query(PointOfSale).filter(
        PointOfSale.id == pos_id,
        PointOfSale.tenant_id == tenant_id,
    ).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Point de vente introuvable.")
    return pos

@router.post("/", response_model=PointOfSaleResponse, status_code=status.HTTP_201_CREATED)
def create_point_of_sale(
    payload: PointOfSaleCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    pos_data = payload.model_dump()
    pos_data["tenant_id"] = tenant_id
    pos = PointOfSale(**pos_data)
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos

@router.put("/{pos_id}", response_model=PointOfSaleResponse)
def update_point_of_sale(
    pos_id: int,
    payload: PointOfSaleUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    pos = db.query(PointOfSale).filter(
        PointOfSale.id == pos_id,
        PointOfSale.tenant_id == tenant_id,
    ).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Point de vente introuvable.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pos, field, value)
    db.commit()
    db.refresh(pos)
    return pos

@router.delete("/{pos_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_point_of_sale(
    pos_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    pos = db.query(PointOfSale).filter(
        PointOfSale.id == pos_id,
        PointOfSale.tenant_id == tenant_id,
    ).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Point de vente introuvable.")
    db.delete(pos)
    db.commit()
    return None
