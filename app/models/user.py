import enum
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Float, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, Dict, Any
from app.core.database import Base

DEFAULT_SELLER_PERMISSIONS: Dict[str, Any] = {
    "can_discount": False,
    "max_discount_percent": 5.0,
    "can_edit_price": False,
    "can_view_margin": False,
    "can_cancel_sale": False,
    "can_give_credit": True,
    "can_manage_stock": False,
    "restricted_to_pos": True,
}

class UserRole(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"  # Accès plateforme globale (développeur / créateur)
    ADMIN = "ADMIN"            # Propriétaire du magasin / directeur
    MANAGER = "MANAGER"        # Gestionnaire de stock / inventaires
    CASHIER = "CASHIER"        # Vendeur / Caisse uniquement
    SELLER = "SELLER"          # Vendeur indépendant / commissionné

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CASHIER, nullable=False, index=True)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    commission_type: Mapped[str] = mapped_column(String(20), default="PERCENTAGE", nullable=False)
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, default=DEFAULT_SELLER_PERMISSIONS, nullable=True)
    point_of_sale_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("points_of_sale.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    tenant = relationship("Tenant", back_populates="users")
    point_of_sale = relationship("PointOfSale")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'username', name='uq_tenant_username'),
    )
