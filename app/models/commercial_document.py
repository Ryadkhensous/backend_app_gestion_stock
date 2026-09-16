import enum
from datetime import datetime, timezone
from sqlalchemy import String, Float, Text, ForeignKey, DateTime, Enum, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from app.core.database import Base

class DocumentType(str, enum.Enum):
    ORDER = "ORDER"       # Bon de commande
    DELIVERY = "DELIVERY" # Bon de livraison

class DocumentDirection(str, enum.Enum):
    OUTGOING = "OUTGOING" # Sortant (livraison vers point de vente ou client)
    INCOMING = "INCOMING" # Entrant (réception fournisseur / approvisionnement)

class DocumentStatus(str, enum.Enum):
    DRAFT = "DRAFT"         # Brouillon
    VALIDATED = "VALIDATED" # Validé / En attente
    DELIVERED = "DELIVERED" # Livré / Réceptionné (stock effectif)
    CANCELLED = "CANCELLED" # Annulé

class CommercialDocument(Base):
    __tablename__ = "commercial_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False, index=True)
    direction: Mapped[DocumentDirection] = mapped_column(Enum(DocumentDirection), nullable=False, default=DocumentDirection.OUTGOING)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.DRAFT, index=True)

    point_of_sale_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("points_of_sale.id", ondelete="SET NULL"), nullable=True, index=True)
    partner_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    parent_document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("commercial_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    issue_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    point_of_sale = relationship("PointOfSale")
    items = relationship("DocumentItem", back_populates="document", cascade="all, delete-orphan")
    parent_document = relationship("CommercialDocument", remote_side=[id], backref="child_documents")


class DocumentItem(Base):
    __tablename__ = "document_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("commercial_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    # SET NULL au lieu de CASCADE : préserve l'historique comptable si le produit est supprimé du catalogue
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    document = relationship("CommercialDocument", back_populates="items")
    product = relationship("Product")
