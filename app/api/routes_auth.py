import re
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user, require_roles
from app.models.tenant import Tenant, SubscriptionPlan
from app.models.user import User, UserRole
from app.schemas.auth import (
    TenantRegister,
    TenantOut,
    UserCreate,
    UserOut,
    LoginRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentification & Magasins"])

def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)

@router.post("/register-tenant", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_tenant(data: TenantRegister, db: Session = Depends(get_db)):
    """
    Inscrit un nouveau magasin client (Tenant) et crée son compte administrateur.
    Retourne immédiatement le token JWT pour connecter le gérant.
    """
    slug = data.slug or _slugify(data.name)
    
    # Vérifie l'unicité du slug
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing_tenant:
        # Ajoute un suffixe aléatoire si le slug existe déjà
        slug = f"{slug}-{secrets.token_hex(2)}"

    # Création du magasin
    tenant = Tenant(
        name=data.name,
        slug=slug,
        license_key=f"LIC-{secrets.token_hex(6).upper()}",
        subscription_plan=data.subscription_plan,
        is_active=True,
    )
    db.add(tenant)
    db.flush() # Récupère l'ID du tenant généré

    # Création du compte administrateur du magasin
    admin_user = User(
        tenant_id=tenant.id,
        username=data.admin_username.strip().lower(),
        email=data.admin_email.strip() if data.admin_email else None,
        full_name=data.admin_full_name,
        hashed_password=hash_password(data.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(tenant)
    db.refresh(admin_user)

    # Génération du token JWT
    access_token = create_access_token(
        data={
            "sub": str(admin_user.id),
            "tenant_id": tenant.id,
            "role": admin_user.role.value,
            "username": admin_user.username,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(admin_user),
        tenant=TenantOut.model_validate(tenant),
    )

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Connexion d'un utilisateur (gérant, caissier, etc.).
    Retourne le token JWT contenant le tenant_id pour isoler toutes les futures requêtes.
    """
    username = data.username.strip().lower()
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur a été désactivé",
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le compte de ce magasin est suspendu ou inactif. Veuillez contacter le support.",
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": tenant.id,
            "role": user.role.value,
            "username": user.username,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant),
    )

@router.get("/me", response_model=TokenResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne le profil de l'utilisateur connecté et de son magasin."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "tenant_id": current_user.tenant_id,
            "role": current_user.role.value,
            "username": current_user.username,
        }
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        tenant=TenantOut.model_validate(tenant),
    )

@router.get("/users", response_model=List[UserOut])
def list_tenant_users(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Liste tous les utilisateurs/employés du magasin connecté."""
    return db.query(User).filter(User.tenant_id == current_user.tenant_id).all()

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_tenant_user(
    data: UserCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """
    Crée un nouvel employé (caissier, gestionnaire) pour le magasin.
    Vérifie la limite de comptes du forfait d'abonnement.
    """
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Magasin introuvable")

    user_count = db.query(User).filter(User.tenant_id == current_user.tenant_id).count()
    if user_count >= tenant.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limite de {tenant.max_users} utilisateurs atteinte pour votre forfait.",
        )

    username = data.username.strip().lower()
    existing = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        User.username == username,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet identifiant existe déjà dans votre magasin.",
        )

    new_user = User(
        tenant_id=current_user.tenant_id,
        username=username,
        email=data.email.strip() if data.email else None,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        point_of_sale_id=data.point_of_sale_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
