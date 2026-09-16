from sqlalchemy import Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True) # Code référence / code-barres
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)         # Prix de vente unitaire
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)    # Coût d'achat unitaire
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)      # Quantité en stock
    min_stock_alert: Mapped[int] = mapped_column(Integer, nullable=False, default=5) # Seuil d'alerte stock bas
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    category = relationship("Category", back_populates="products")
    movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_stock_alert
