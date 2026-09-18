import enum
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class MovementType(str, enum.Enum):
    IN = "IN"           # Entrée (approvisionnement)
    OUT = "OUT"         # Sortie (vente, avarie)
    TRANSFER = "TRANSFER" # Transfert vers un point de vente

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    point_of_sale_id = Column(Integer, ForeignKey("points_of_sale.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type = Column(Enum(MovementType), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    reference = Column(String(100), nullable=True, index=True) # N° Bon de livraison / facture
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    product = relationship("Product", back_populates="movements")
    point_of_sale = relationship("PointOfSale", back_populates="movements")

    __table_args__ = (
        Index('idx_movements_tenant_date', 'tenant_id', 'created_at'),
    )
