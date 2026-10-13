from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant_id, require_roles
from app.core.security import hash_password
from app.models.user import User, UserRole, DEFAULT_SELLER_PERMISSIONS
from app.models.tenant import Tenant
from app.models.point_of_sale import PointOfSale
from app.models.commercial_document import CommercialDocument, DocumentStatus
from app.schemas.seller import (
    SellerCreate,
    SellerUpdate,
    SellerResponse,
    SellerDetailResponse,
    SellerSaleItem,
    SellerOverviewSummary,
    SellerPermissionsUpdate,
)

router = APIRouter(prefix="/sellers", tags=["Gestion des Vendeurs & Commissions"])

def _build_seller_response(user: User, db: Session) -> SellerResponse:
    # Calcul des statistiques de vente du vendeur
    stats = db.query(
        func.count(CommercialDocument.id).label("sales_count"),
        func.coalesce(func.sum(CommercialDocument.total_amount), 0.0).label("turnover"),
        func.coalesce(func.sum(CommercialDocument.commission_amount), 0.0).label("commission"),
    ).filter(
        CommercialDocument.tenant_id == user.tenant_id,
        CommercialDocument.seller_id == user.id,
        CommercialDocument.status != DocumentStatus.CANCELLED
    ).first()

    sales_count = stats.sales_count if stats else 0
    turnover = round(float(stats.turnover if stats else 0.0), 2)
    commission = round(float(stats.commission if stats else 0.0), 2)

    pos_name = None
    if user.point_of_sale:
        pos_name = user.point_of_sale.name
    elif user.point_of_sale_id:
        pos = db.query(PointOfSale).filter(PointOfSale.id == user.point_of_sale_id).first()
        if pos:
            pos_name = pos.name

    perms = user.permissions if user.permissions is not None else DEFAULT_SELLER_PERMISSIONS

    return SellerResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name or user.username,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        commission_rate=user.commission_rate or 0.0,
        commission_type=user.commission_type or "PERCENTAGE",
        point_of_sale_id=user.point_of_sale_id,
        point_of_sale_name=pos_name,
        permissions=perms,
        is_active=user.is_active,
        created_at=user.created_at,
        total_sales_count=sales_count,
        total_turnover=turnover,
        total_commission=commission,
    )

@router.get("/summary", response_model=SellerOverviewSummary)
def get_sellers_summary(
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retourne la synthèse globale de tous les vendeurs du magasin :
    Total vendeurs, actifs, chiffre d'affaires global et commissions cumulées.
    """
    users = db.query(User).filter(
        User.tenant_id == tenant_id,
        (User.role.in_([UserRole.SELLER, UserRole.CASHIER])) | (User.commission_rate > 0)
    ).order_by(User.created_at.desc()).all()

    seller_responses = [_build_seller_response(u, db) for u in users]

    total_sellers = len(seller_responses)
    active_sellers = sum(1 for s in seller_responses if s.is_active)
    total_sales_count = sum(s.total_sales_count for s in seller_responses)
    total_turnover = round(sum(s.total_turnover for s in seller_responses), 2)
    total_commission = round(sum(s.total_commission for s in seller_responses), 2)

    return SellerOverviewSummary(
        total_sellers=total_sellers,
        active_sellers=active_sellers,
        total_sales_count=total_sales_count,
        total_turnover=total_turnover,
        total_commission=total_commission,
        sellers=seller_responses
    )

@router.get("/", response_model=List[SellerResponse])
def list_sellers(
    active_only: bool = Query(False),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Liste tous les vendeurs du magasin avec leurs statistiques individuelles de vente et commissions.
    """
    query = db.query(User).filter(
        User.tenant_id == tenant_id,
        (User.role.in_([UserRole.SELLER, UserRole.CASHIER])) | (User.commission_rate > 0)
    )

    if active_only:
        query = query.filter(User.is_active == True)

    users = query.order_by(User.created_at.desc()).all()
    return [_build_seller_response(u, db) for u in users]

@router.post("/", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
def create_seller(
    payload: SellerCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Création d'un nouveau vendeur travaillant à son compte / sous commission.
    Vérifie les quotas du forfait et l'unicité de l'identifiant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Magasin introuvable.")

    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if user_count >= tenant.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limite de {tenant.max_users} utilisateurs atteinte pour votre forfait d'abonnement.",
        )

    username_clean = payload.username.strip().lower()
    existing = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.username == username_clean
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"L'identifiant '{payload.username}' est déjà utilisé dans ce magasin.",
        )

    if payload.point_of_sale_id:
        pos = db.query(PointOfSale).filter(
            PointOfSale.id == payload.point_of_sale_id,
            PointOfSale.tenant_id == tenant_id
        ).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Point de vente sélectionné introuvable.")

    new_seller = User(
        tenant_id=tenant_id,
        username=username_clean,
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email.strip().lower() if payload.email else None,
        hashed_password=hash_password(payload.password),
        role=UserRole.SELLER,
        commission_rate=payload.commission_rate,
        commission_type=payload.commission_type or "PERCENTAGE",
        permissions=payload.permissions if payload.permissions is not None else DEFAULT_SELLER_PERMISSIONS,
        point_of_sale_id=payload.point_of_sale_id,
        is_active=payload.is_active,
    )

    db.add(new_seller)
    db.commit()
    db.refresh(new_seller)

    return _build_seller_response(new_seller, db)

@router.get("/permissions/presets")
def get_seller_permission_presets():
    """
    Retourne la liste des profils types d'autorisations pour vendeurs.
    """
    return {
        "RESTRICTED": {
            "name": "Vendeur Restreint",
            "badge": "Sécurisé",
            "description": "Caisse pure. Ne peut ni appliquer de remise, ni modifier les prix, ni voir les marges.",
            "permissions": {
                "can_discount": False,
                "max_discount_percent": 0.0,
                "can_edit_price": False,
                "can_view_margin": False,
                "can_cancel_sale": False,
                "can_give_credit": False,
                "can_manage_stock": False,
                "restricted_to_pos": True,
            }
        },
        "STANDARD": {
            "name": "Vendeur Standard (Recommandé)",
            "badge": "Populaire",
            "description": "Ventes courantes, crédits clients et petites remises autorisées (jusqu'à 5%).",
            "permissions": {
                "can_discount": True,
                "max_discount_percent": 5.0,
                "can_edit_price": False,
                "can_view_margin": False,
                "can_cancel_sale": False,
                "can_give_credit": True,
                "can_manage_stock": False,
                "restricted_to_pos": True,
            }
        },
        "COMMERCIAL": {
            "name": "Commercial Terrain / Autonome",
            "badge": "Avancé",
            "description": "Vendeur indépendant à son compte avec négociation de prix et remises jusqu'à 15%.",
            "permissions": {
                "can_discount": True,
                "max_discount_percent": 15.0,
                "can_edit_price": True,
                "can_view_margin": True,
                "can_cancel_sale": False,
                "can_give_credit": True,
                "can_manage_stock": True,
                "restricted_to_pos": False,
            }
        },
        "MANAGER": {
            "name": "Responsable de Caisse",
            "badge": "Complet",
            "description": "Accès intégral aux fonctions de vente, annulation de tickets et transferts de stock.",
            "permissions": {
                "can_discount": True,
                "max_discount_percent": 30.0,
                "can_edit_price": True,
                "can_view_margin": True,
                "can_cancel_sale": True,
                "can_give_credit": True,
                "can_manage_stock": True,
                "restricted_to_pos": False,
            }
        }
    }

@router.get("/{seller_id}", response_model=SellerDetailResponse)
@router.get("/{seller_id}/stats", response_model=SellerDetailResponse)
def get_seller_detail(
    seller_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retourne la fiche détaillée d'un vendeur avec l'historique de ses 20 dernières ventes.
    """
    seller = db.query(User).filter(
        User.id == seller_id,
        User.tenant_id == tenant_id
    ).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Vendeur introuvable.")

    seller_resp = _build_seller_response(seller, db)

    recent_docs = db.query(CommercialDocument).filter(
        CommercialDocument.tenant_id == tenant_id,
        CommercialDocument.seller_id == seller_id,
    ).order_by(CommercialDocument.created_at.desc()).limit(20).all()

    sales_items = [
        SellerSaleItem(
            id=d.id,
            reference_number=d.reference_number,
            total_amount=d.total_amount,
            commission_amount=d.commission_amount or 0.0,
            issue_date=d.issue_date,
            status=d.status.value if hasattr(d.status, 'value') else str(d.status),
            partner_name=d.partner_name,
            point_of_sale_name=d.point_of_sale.name if d.point_of_sale else None,
        )
        for d in recent_docs
    ]

    return SellerDetailResponse(
        seller=seller_resp,
        recent_sales=sales_items
    )

@router.get("/{seller_id}/permissions")
def get_seller_permissions(
    seller_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db)
):
    seller = db.query(User).filter(User.id == seller_id, User.tenant_id == tenant_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Vendeur introuvable.")
    return seller.permissions or DEFAULT_SELLER_PERMISSIONS

@router.put("/{seller_id}/permissions")
def update_seller_permissions(
    seller_id: int,
    payload: SellerPermissionsUpdate,
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db)
):
    seller = db.query(User).filter(User.id == seller_id, User.tenant_id == tenant_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Vendeur introuvable.")
    seller.permissions = payload.permissions
    db.commit()
    db.refresh(seller)
    return {"message": "Permissions mises à jour avec succès", "permissions": seller.permissions}

@router.put("/{seller_id}", response_model=SellerResponse)
def update_seller(
    seller_id: int,
    payload: SellerUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Mise à jour des informations, du taux de commission ou du mot de passe d'un vendeur.
    """
    seller = db.query(User).filter(
        User.id == seller_id,
        User.tenant_id == tenant_id
    ).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Vendeur introuvable.")

    if payload.full_name is not None:
        seller.full_name = payload.full_name.strip()
    if payload.phone is not None:
        seller.phone = payload.phone.strip() if payload.phone else None
    if payload.email is not None:
        seller.email = payload.email.strip().lower() if payload.email else None
    if payload.commission_rate is not None:
        seller.commission_rate = payload.commission_rate
    if payload.commission_type is not None:
        seller.commission_type = payload.commission_type
    if payload.permissions is not None:
        seller.permissions = payload.permissions
    if payload.is_active is not None:
        seller.is_active = payload.is_active
    if payload.point_of_sale_id is not None:
        if payload.point_of_sale_id > 0:
            pos = db.query(PointOfSale).filter(
                PointOfSale.id == payload.point_of_sale_id,
                PointOfSale.tenant_id == tenant_id
            ).first()
            if not pos:
                raise HTTPException(status_code=404, detail="Point de vente sélectionné introuvable.")
            seller.point_of_sale_id = payload.point_of_sale_id
        else:
            seller.point_of_sale_id = None
    if payload.password and payload.password.strip():
        seller.hashed_password = hash_password(payload.password.strip())

    db.commit()
    db.refresh(seller)
    return _build_seller_response(seller, db)

@router.delete("/{seller_id}")
def delete_or_deactivate_seller(
    seller_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Supprime le vendeur s'il n'a aucune vente enregistrée, ou le désactive pour préserver l'historique comptable.
    """
    seller = db.query(User).filter(
        User.id == seller_id,
        User.tenant_id == tenant_id
    ).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Vendeur introuvable.")

    # Vérifier si le vendeur a déjà des ventes
    sales_count = db.query(CommercialDocument).filter(
        CommercialDocument.seller_id == seller_id
    ).count()

    if sales_count > 0:
        seller.is_active = False
        db.commit()
        return {
            "message": "Le vendeur a un historique de ventes existant. Son compte a été désactivé pour préserver l'historique comptable.",
            "soft_delete": True,
            "id": seller_id
        }
    else:
        db.delete(seller)
        db.commit()
        return {
            "message": "Compte vendeur supprimé définitivement.",
            "soft_delete": False,
            "id": seller_id
        }
