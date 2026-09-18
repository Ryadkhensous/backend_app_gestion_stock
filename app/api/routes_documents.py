from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timezone
import time

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.models.commercial_document import (
    CommercialDocument,
    DocumentItem,
    DocumentType,
    DocumentDirection,
    DocumentStatus
)
from app.models.product import Product
from app.models.point_of_sale import PointOfSale
from app.models.stock_movement import StockMovement, MovementType
from app.schemas.commercial_document import (
    CommercialDocumentCreate,
    CommercialDocumentResponse,
    CommercialDocumentUpdate,
    CommercialDocumentStatusUpdate,
    DocumentItemResponse
)

router = APIRouter(prefix="/documents", tags=["Bons & Documents Commerciaux"])

def generate_reference(doc_type: DocumentType, db: Session, tenant_id: int) -> str:
    prefix = "BC" if doc_type == DocumentType.ORDER else "BL"
    date_str = datetime.now().strftime("%Y%m%d")
    ts_suffix = int(time.time() * 1000) % 10_000_000
    return f"{prefix}-{date_str}-{ts_suffix:07d}"

def to_document_response(doc: CommercialDocument) -> CommercialDocumentResponse:
    item_responses = []
    for item in doc.items:
        it = DocumentItemResponse.model_validate(item)
        if item.product:
            it.product_name = item.product.name
            it.product_sku = item.product.sku
        else:
            it.product_name = "Produit supprimé"
            it.product_sku = ""
        item_responses.append(it)

    res = CommercialDocumentResponse.model_validate(doc)
    res.items = item_responses
    res.point_of_sale_name = doc.point_of_sale.name if doc.point_of_sale else None
    if doc.parent_document:
        res.parent_document_reference = doc.parent_document.reference_number
    return res

def apply_delivery_stock_movements(doc: CommercialDocument, db: Session):
    """
    Applique l'impact physique d'une livraison sur le stock et génère les mouvements de stock.
    Utilise with_for_update() pour éviter les race conditions (Bug 1.3).
    """
    for item in doc.items:
        if item.product_id is None:
            continue
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.tenant_id == doc.tenant_id
        ).with_for_update().first()
        if not product:
            continue

        if doc.direction == DocumentDirection.OUTGOING:
            if product.quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuffisant pour '{product.name}'. Disponible : {product.quantity}, Requis : {item.quantity}"
                )
            product.quantity -= item.quantity
            mv_type = MovementType.TRANSFER if doc.point_of_sale_id else MovementType.OUT
            movement = StockMovement(
                tenant_id=doc.tenant_id,
                product_id=product.id,
                point_of_sale_id=doc.point_of_sale_id,
                movement_type=mv_type,
                quantity=item.quantity,
                reference=doc.reference_number,
                note=f"Bon de livraison {doc.reference_number} vers {doc.partner_name or (doc.point_of_sale.name if doc.point_of_sale else 'Client')}"
            )
            db.add(movement)

        elif doc.direction == DocumentDirection.INCOMING:
            product.quantity += item.quantity
            movement = StockMovement(
                tenant_id=doc.tenant_id,
                product_id=product.id,
                point_of_sale_id=doc.point_of_sale_id,
                movement_type=MovementType.IN,
                quantity=item.quantity,
                reference=doc.reference_number,
                note=f"Réception fournisseur {doc.reference_number} de {doc.partner_name or 'Fournisseur'}"
            )
            db.add(movement)

def revert_delivery_stock_movements(doc: CommercialDocument, db: Session):
    """
    Annule l'impact d'une livraison sur le stock lors d'une annulation ou d'une modification.
    Utilise with_for_update() pour éviter les race conditions (Bug 1.3).
    """
    for item in doc.items:
        if item.product_id is None:
            continue
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.tenant_id == doc.tenant_id
        ).with_for_update().first()
        if not product:
            continue
        if doc.direction == DocumentDirection.OUTGOING:
            product.quantity += item.quantity
            movement = StockMovement(
                tenant_id=doc.tenant_id,
                product_id=product.id,
                point_of_sale_id=doc.point_of_sale_id,
                movement_type=MovementType.IN,
                quantity=item.quantity,
                reference=f"ANNUL-{doc.reference_number}",
                note=f"Annulation Bon de livraison {doc.reference_number}"
            )
            db.add(movement)
        elif doc.direction == DocumentDirection.INCOMING:
            product.quantity = max(0, product.quantity - item.quantity)
            movement = StockMovement(
                tenant_id=doc.tenant_id,
                product_id=product.id,
                point_of_sale_id=doc.point_of_sale_id,
                movement_type=MovementType.OUT,
                quantity=item.quantity,
                reference=f"ANNUL-{doc.reference_number}",
                note=f"Annulation Réception {doc.reference_number}"
            )
            db.add(movement)

@router.get("/", response_model=List[CommercialDocumentResponse])
def list_documents(
    doc_type: Optional[DocumentType] = Query(None),
    status: Optional[DocumentStatus] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=200),
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    query = db.query(CommercialDocument).options(
        joinedload(CommercialDocument.point_of_sale),
        joinedload(CommercialDocument.parent_document),
        selectinload(CommercialDocument.items).joinedload(DocumentItem.product)
    ).filter(CommercialDocument.tenant_id == tenant_id)

    if doc_type:
        query = query.filter(CommercialDocument.doc_type == doc_type)
    if status:
        query = query.filter(CommercialDocument.status == status)
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (CommercialDocument.reference_number.ilike(search_filter)) |
            (CommercialDocument.partner_name.ilike(search_filter)) |
            (CommercialDocument.notes.ilike(search_filter))
        )
    docs = query.order_by(CommercialDocument.created_at.desc()).limit(limit).all()
    return [to_document_response(d) for d in docs]

@router.get("/{document_id}", response_model=CommercialDocumentResponse)
def get_document(
    document_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    doc = db.query(CommercialDocument).options(
        joinedload(CommercialDocument.point_of_sale),
        joinedload(CommercialDocument.parent_document),
        selectinload(CommercialDocument.items).joinedload(DocumentItem.product)
    ).filter(
        CommercialDocument.id == document_id,
        CommercialDocument.tenant_id == tenant_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return to_document_response(doc)

@router.post("/", response_model=CommercialDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: CommercialDocumentCreate,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    ref = payload.reference_number.strip() if payload.reference_number else ""
    if not ref:
        ref = generate_reference(payload.doc_type, db, tenant_id)
    else:
        existing = db.query(CommercialDocument).filter(
            CommercialDocument.tenant_id == tenant_id,
            CommercialDocument.reference_number == ref
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Un document avec la référence '{ref}' existe déjà.")

    # Vérifier le point de vente
    if payload.point_of_sale_id:
        pos = db.query(PointOfSale).filter(
            PointOfSale.id == payload.point_of_sale_id,
            PointOfSale.tenant_id == tenant_id
        ).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Point de vente introuvable.")

    total_amount = 0.0
    doc_items = []
    
    for it in payload.items:
        product = db.query(Product).filter(
            Product.id == it.product_id,
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Produit ID {it.product_id} introuvable.")
        
        line_total = round(it.quantity * it.unit_price, 2)
        total_amount += line_total
        
        cost_p = it.cost_price if (it.cost_price and it.cost_price > 0) else product.cost_price
        doc_items.append(DocumentItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            cost_price=cost_p,
            total_price=line_total
        ))

    doc = CommercialDocument(
        tenant_id=tenant_id,
        reference_number=ref,
        doc_type=payload.doc_type,
        direction=payload.direction,
        status=payload.status,
        point_of_sale_id=payload.point_of_sale_id,
        partner_name=payload.partner_name,
        issue_date=payload.issue_date or datetime.now(timezone.utc),
        delivery_date=payload.delivery_date,
        total_amount=round(total_amount, 2),
        notes=payload.notes,
        items=doc_items
    )

    if doc.doc_type == DocumentType.DELIVERY and doc.status == DocumentStatus.DELIVERED:
        apply_delivery_stock_movements(doc, db)

    db.add(doc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Référence déjà utilisée. Veuillez en générer une nouvelle.")
    db.refresh(doc)
    return to_document_response(doc)

@router.put("/{document_id}", response_model=CommercialDocumentResponse)
@router.patch("/{document_id}", response_model=CommercialDocumentResponse)
def update_document(
    document_id: int,
    payload: CommercialDocumentUpdate,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    doc = db.query(CommercialDocument).options(
        joinedload(CommercialDocument.point_of_sale),
        selectinload(CommercialDocument.items).joinedload(DocumentItem.product)
    ).filter(
        CommercialDocument.id == document_id,
        CommercialDocument.tenant_id == tenant_id
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    was_delivered = (doc.doc_type == DocumentType.DELIVERY and doc.status == DocumentStatus.DELIVERED)
    if was_delivered:
        revert_delivery_stock_movements(doc, db)

    # Mise à jour des métadonnées
    if payload.partner_name is not None:
        doc.partner_name = payload.partner_name
    if payload.point_of_sale_id is not None:
        if payload.point_of_sale_id > 0:
            pos = db.query(PointOfSale).filter(
                PointOfSale.id == payload.point_of_sale_id,
                PointOfSale.tenant_id == tenant_id
            ).first()
            if not pos:
                raise HTTPException(status_code=404, detail="Point de vente introuvable.")
            doc.point_of_sale_id = payload.point_of_sale_id
        else:
            doc.point_of_sale_id = None
    if payload.direction is not None:
        doc.direction = payload.direction
    if payload.issue_date is not None:
        doc.issue_date = payload.issue_date
    if payload.delivery_date is not None:
        doc.delivery_date = payload.delivery_date
    if payload.notes is not None:
        doc.notes = payload.notes
    if payload.status is not None:
        doc.status = payload.status

    # Mise à jour des articles si fournis
    if payload.items is not None:
        for old_item in list(doc.items):
            db.delete(old_item)
        doc.items.clear()

        total_amount = 0.0
        for it in payload.items:
            product = db.query(Product).filter(
                Product.id == it.product_id,
                Product.tenant_id == tenant_id
            ).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"Produit ID {it.product_id} introuvable.")

            line_total = round(it.quantity * it.unit_price, 2)
            total_amount += line_total
            cost_p = it.cost_price if (it.cost_price and it.cost_price > 0) else (product.cost_price or 0.0)

            doc_item = DocumentItem(
                document_id=doc.id,
                product_id=it.product_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                cost_price=cost_p,
                total_price=line_total
            )
            doc.items.append(doc_item)
        doc.total_amount = round(total_amount, 2)

    is_delivered_now = (doc.doc_type == DocumentType.DELIVERY and doc.status == DocumentStatus.DELIVERED)
    if is_delivered_now:
        apply_delivery_stock_movements(doc, db)
        if not doc.delivery_date:
            doc.delivery_date = datetime.now(timezone.utc)

    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return to_document_response(doc)

@router.patch("/{document_id}/status", response_model=CommercialDocumentResponse)
def update_document_status(
    document_id: int,
    payload: CommercialDocumentStatusUpdate,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    doc = db.query(CommercialDocument).options(
        selectinload(CommercialDocument.items).joinedload(DocumentItem.product)
    ).filter(
        CommercialDocument.id == document_id,
        CommercialDocument.tenant_id == tenant_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    old_status = doc.status
    new_status = payload.status

    if old_status == new_status:
        return to_document_response(doc)

    if doc.doc_type == DocumentType.DELIVERY:
        if new_status == DocumentStatus.DELIVERED and old_status != DocumentStatus.DELIVERED:
            apply_delivery_stock_movements(doc, db)
            if not doc.delivery_date:
                doc.delivery_date = datetime.now(timezone.utc)
        elif old_status == DocumentStatus.DELIVERED and new_status != DocumentStatus.DELIVERED:
            revert_delivery_stock_movements(doc, db)

    doc.status = new_status
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return to_document_response(doc)

@router.post("/{document_id}/convert-to-delivery", response_model=CommercialDocumentResponse, status_code=status.HTTP_201_CREATED)
def convert_order_to_delivery(
    document_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    order = db.query(CommercialDocument).options(
        selectinload(CommercialDocument.items).joinedload(DocumentItem.product)
    ).filter(
        CommercialDocument.id == document_id,
        CommercialDocument.tenant_id == tenant_id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Bon de commande introuvable.")
    if order.doc_type != DocumentType.ORDER:
        raise HTTPException(status_code=400, detail="Seul un Bon de Commande peut être converti en Bon de Livraison.")

    existing_delivery = db.query(CommercialDocument).filter(
        CommercialDocument.tenant_id == tenant_id,
        CommercialDocument.parent_document_id == order.id,
        CommercialDocument.doc_type == DocumentType.DELIVERY,
        CommercialDocument.status != DocumentStatus.CANCELLED
    ).first()
    if existing_delivery:
        raise HTTPException(
            status_code=409,
            detail=f"Un bon de livraison actif ({existing_delivery.reference_number}) existe déjà pour cette commande. "
                   f"Annulez-le d'abord si vous souhaitez en créer un nouveau."
        )

    new_ref = generate_reference(DocumentType.DELIVERY, db, tenant_id)
    
    bl_items = []
    for it in order.items:
        cost_p = it.cost_price if (it.cost_price and it.cost_price > 0) else (it.product.cost_price if it.product else 0.0)
        bl_items.append(DocumentItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            cost_price=cost_p,
            total_price=it.total_price
        ))

    bl = CommercialDocument(
        tenant_id=tenant_id,
        reference_number=new_ref,
        doc_type=DocumentType.DELIVERY,
        direction=order.direction,
        status=DocumentStatus.DRAFT,
        point_of_sale_id=order.point_of_sale_id,
        partner_name=order.partner_name,
        parent_document_id=order.id,
        issue_date=datetime.now(timezone.utc),
        total_amount=order.total_amount,
        notes=f"Généré depuis la commande {order.reference_number}. {order.notes or ''}".strip(),
        items=bl_items
    )

    if order.status == DocumentStatus.DRAFT:
        order.status = DocumentStatus.VALIDATED

    db.add(bl)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Référence dupliquée. Veuillez réessayer.")
    db.refresh(bl)
    return to_document_response(bl)

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    doc = db.query(CommercialDocument).filter(
        CommercialDocument.id == document_id,
        CommercialDocument.tenant_id == tenant_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    
    if doc.doc_type == DocumentType.DELIVERY and doc.status == DocumentStatus.DELIVERED:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer directement un bon de livraison déjà livré. Veuillez d'abord l'annuler pour réintégrer les stocks."
        )

    db.delete(doc)
    db.commit()
    return None
