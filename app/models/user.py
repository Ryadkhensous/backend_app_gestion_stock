import enum
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from app.core.database import Base

class UserRole(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"  # Accès plateforme globale (développeur / créateur)
    ADMIN = "ADMIN"            # Propriétaire du magasin / directeur
    MANAGER = "MANAGER"        # Gestionnaire de stock / inventaires
    CASHIER = "CASHIER"        # Vendeur / Caisse uniquement

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CASHIER, nullable=False, index=True)
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
