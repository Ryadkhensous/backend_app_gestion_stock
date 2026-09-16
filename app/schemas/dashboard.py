from pydantic import BaseModel
from typing import List
from app.schemas.product import ProductResponse
from app.schemas.stock_movement import StockMovementResponse

class DashboardStats(BaseModel):
    total_products: int
    total_stock_units: int
    total_inventory_value: float
    total_points_of_sale: int
    active_points_of_sale: int
    low_stock_alerts_count: int
    low_stock_products: List[ProductResponse]
    recent_movements: List[StockMovementResponse]
