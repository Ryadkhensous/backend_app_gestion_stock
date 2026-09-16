from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class PointOfSale(Base):
    __tablename__ = "points_of_sale"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)   # Coordonnées GPS pour Google Maps
    longitude = Column(Float, nullable=False)  # Coordonnées GPS pour Google Maps
    phone = Column(String(50), nullable=True)
    manager_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    movements = relationship("StockMovement", back_populates="point_of_sale")
