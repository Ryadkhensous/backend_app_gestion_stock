import enum
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, List
from app.core.database import Base

class SubscriptionPlan(str, enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    license_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan), default=SubscriptionPlan.PRO, nullable=False
    )
    max_users: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_products: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="tenant", cascade="all, delete-orphan")
    points_of_sale = relationship("PointOfSale", back_populates="tenant", cascade="all, delete-orphan")
