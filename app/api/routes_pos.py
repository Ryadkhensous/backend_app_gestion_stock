from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import time

from app.core.database import get_db
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
from app.schemas.commercial_document import CommercialDocumentResponse
from app.api.routes_documents import to_document_response

router = APIRouter(prefix="/pos", tags=["Caisse Enregistreuse (POS)"])

class PosCheckoutItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantité (doit être > 0)")
    # Note : unit_price est accepté pour référence affichage uniquement,
    # le prix réel est TOUJOURS récupéré depuis la base de données.
    unit_price: Optional[float] = None

class PosCheckoutRequest(BaseModel):
    items: List[PosCheckoutItem]
    point_of_sale_id: Optional[int] = None
    customer_name: Optional[str] = "Client Comptoir"
    payment_method: str = "CASH"  # CASH, CARD, CREDIT
    amount_tendered: Optional[float] = None
    notes: Optional[str] = None

class PosCheckoutResponse(BaseModel):
    document: CommercialDocumentResponse
    payment_method: str
    amount_tendered: float
    change_due: float
    total_items: int

def _generate_ticket_ref() -> str:
    """Génère une référence unique basée sur le timestamp en millisecondes."""
    date_str = datetime.now().strftime("%Y%m%d")
    ts_suffix = int(time.time() * 1000) % 10_000_000
    return f"TICKET-{date_str}-{ts_suffix:07d}"

@router.post("/checkout", response_model=PosCheckoutResponse, status_code=status.HTTP_201_CREATED)
def pos_checkout(payload: PosCheckoutRequest, db: Session = Depends(get_db)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Le panier est vide.")

    # 1. Vérifier le point de vente si précisé
    pos_id = payload.point_of_sale_id
    if pos_id:
        pos = db.query(PointOfSale).filter(PointOfSale.id == pos_id).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Point de vente sélectionné introuvable.")

    # 2. Générer une référence ticket de caisse unique (timestamp ms)
    ref = _generate_ticket_ref()

    # 3. Calculer le total et valider le stock avec verrouillage pessimiste
    total_amount = 0.0
    total_items = 0
    doc_items = []
    movements_to_add = []

    for item_data in payload.items:
        # with_for_update() : verrouillage pessimiste pour éviter les race conditions (Bug 1.3)
        product = db.query(Product).filter(Product.id == item_data.product_id).with_for_update().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Produit ID {item_data.product_id} introuvable.")

        if product.quantity < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuffisant pour '{product.name}'. En stock : {product.quantity}, Requis : {item_data.quantity}"
            )

        # SÉCURITÉ (Bug 1.2) : on utilise TOUJOURS le prix officiel de la base de données,
        # jamais le prix transmis par le client.
        official_unit_price = product.price
        line_total = round(item_data.quantity * official_unit_price, 2)
        total_amount += line_total
        total_items += item_data.quantity

        # Décrémenter le stock
        product.quantity -= item_data.quantity

        # Ligne de document avec le prix officiel
        doc_item = DocumentItem(
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=official_unit_price,
            cost_price=product.cost_price,
            total_price=line_total
        )
        doc_items.append(doc_item)

        # Mouvement de sortie
        movement = StockMovement(
            product_id=product.id,
            point_of_sale_id=pos_id,
            movement_type=MovementType.OUT,
            quantity=item_data.quantity,
            reference=ref,
            note=f"Vente Caisse POS ({payload.payment_method}) - {payload.customer_name}"
        )
        movements_to_add.append(movement)

    # 4. Créer le document commercial de type DELIVERY (Bon de sortie / Caisse)
    doc = CommercialDocument(
        reference_number=ref,
        doc_type=DocumentType.DELIVERY,
        direction=DocumentDirection.OUTGOING,
        status=DocumentStatus.DELIVERED,
        point_of_sale_id=pos_id,
        partner_name=payload.customer_name or "Client Comptoir",
        total_amount=round(total_amount, 2),
        notes=f"Paiement: {payload.payment_method}. {payload.notes or ''}".strip(),
        issue_date=datetime.now(timezone.utc),
        delivery_date=datetime.now(timezone.utc)
    )
    doc.items = doc_items

    db.add(doc)
    for m in movements_to_add:
        db.add(m)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Collision de référence (très rare) : on réessaie avec une nouvelle référence
        ref = _generate_ticket_ref()
        doc.reference_number = ref
        for m in movements_to_add:
            m.reference = ref
        db.add(doc)
        for m in movements_to_add:
            db.add(m)
        db.commit()

    db.refresh(doc)

    # Calcul du rendu de monnaie
    tendered = payload.amount_tendered if payload.amount_tendered is not None else total_amount
    change = max(0.0, round(tendered - total_amount, 2))

    return PosCheckoutResponse(
        document=to_document_response(doc),
        payment_method=payload.payment_method,
        amount_tendered=tendered,
        change_due=change,
        total_items=total_items
    )
