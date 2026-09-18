from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.models.product import Product
from app.models.point_of_sale import PointOfSale
from app.models.stock_movement import StockMovement
from app.schemas.dashboard import DashboardStats
from app.schemas.product import ProductResponse
from app.schemas.stock_movement import StockMovementResponse

router = APIRouter(prefix="/dashboard", tags=["Tableau de Bord & KPIs"])

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    # 1. Total produits calculé en SQL pour ce tenant
    total_products = db.query(func.count(Product.id)).filter(Product.tenant_id == tenant_id).scalar() or 0

    # 2. Agrégation des stocks et valeur d'inventaire calculée par la base de données
    stock_summary = db.query(
        func.coalesce(func.sum(Product.quantity), 0).label("total_units"),
        func.coalesce(func.sum(Product.quantity * Product.price), 0.0).label("total_value")
    ).filter(Product.tenant_id == tenant_id).first()
    total_stock_units = int(stock_summary.total_units) if stock_summary else 0
    total_inventory_value = round(float(stock_summary.total_value), 2) if stock_summary else 0.0
    
    # 3. Points de vente du tenant
    total_pos = db.query(func.count(PointOfSale.id)).filter(PointOfSale.tenant_id == tenant_id).scalar() or 0
    active_pos = db.query(func.count(PointOfSale.id)).filter(
        PointOfSale.tenant_id == tenant_id,
        PointOfSale.is_active == True
    ).scalar() or 0
    
    # 4. Alerte stock bas (uniquement les produits concernés du tenant)
    low_stock_products = db.query(Product).options(
        joinedload(Product.category)
    ).filter(
        Product.tenant_id == tenant_id,
        Product.quantity <= Product.min_stock_alert
    ).all()
    low_stock_count = len(low_stock_products)
    
    # 5. Derniers mouvements du tenant avec jointures préchargées
    recent_movs_raw = db.query(StockMovement).options(
        joinedload(StockMovement.product),
        joinedload(StockMovement.point_of_sale)
    ).filter(
        StockMovement.tenant_id == tenant_id
    ).order_by(StockMovement.created_at.desc()).limit(5).all()
    
    recent_movements = []
    for m in recent_movs_raw:
        item = StockMovementResponse.model_validate(m)
        item.product_name = m.product.name if m.product else None
        item.point_of_sale_name = m.point_of_sale.name if m.point_of_sale else None
        recent_movements.append(item)

    return DashboardStats(
        total_products=total_products,
        total_stock_units=total_stock_units,
        total_inventory_value=total_inventory_value,
        total_points_of_sale=total_pos,
        active_points_of_sale=active_pos,
        low_stock_alerts_count=low_stock_count,
        low_stock_products=[ProductResponse.model_validate(p) for p in low_stock_products],
        recent_movements=recent_movements
    )
