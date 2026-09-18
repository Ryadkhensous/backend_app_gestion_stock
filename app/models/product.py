from sqlalchemy import Integer, String, Float, Text, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # Code référence / code-barres
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)         # Prix de vente unitaire
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)    # Coût d'achat unitaire
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)      # Quantité en stock
    min_stock_alert: Mapped[int] = mapped_column(Integer, nullable=False, default=5) # Seuil d'alerte stock bas
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="products")
    category = relationship("Category", back_populates="products")
    movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'sku', name='uq_tenant_product_sku'),
        Index('idx_products_tenant_category', 'tenant_id', 'category_id'),
    )

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_stock_alert
