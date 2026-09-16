from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from app.models.commercial_document import DocumentType, DocumentDirection, DocumentStatus

class DocumentItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantité d'articles")
    unit_price: float = Field(..., ge=0.0, description="Prix unitaire")
    cost_price: Optional[float] = Field(0.0, ge=0.0, description="Coût d'achat unitaire")

class DocumentItemCreate(DocumentItemBase):
    pass

class DocumentItemResponse(DocumentItemBase):
    id: int
    total_price: float
    product_name: Optional[str] = None
    product_sku: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommercialDocumentBase(BaseModel):
    reference_number: str
    doc_type: DocumentType
    direction: DocumentDirection = DocumentDirection.OUTGOING
    status: DocumentStatus = DocumentStatus.DRAFT
    point_of_sale_id: Optional[int] = None
    partner_name: Optional[str] = None
    issue_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = None

class CommercialDocumentCreate(CommercialDocumentBase):
    items: List[DocumentItemCreate] = []

class CommercialDocumentUpdate(BaseModel):
    partner_name: Optional[str] = None
    point_of_sale_id: Optional[int] = None
    direction: Optional[DocumentDirection] = None
    issue_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[DocumentStatus] = None
    items: Optional[List[DocumentItemCreate]] = None

class CommercialDocumentStatusUpdate(BaseModel):
    status: DocumentStatus

class CommercialDocumentResponse(CommercialDocumentBase):
    id: int
    parent_document_id: Optional[int] = None
    parent_document_reference: Optional[str] = None
    total_amount: float
    created_at: datetime
    updated_at: datetime
    point_of_sale_name: Optional[str] = None
    items: List[DocumentItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
