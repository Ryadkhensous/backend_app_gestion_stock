from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.models.user import UserRole
from app.models.tenant import SubscriptionPlan

class TenantOut(BaseModel):
    id: int
    name: str
    slug: str
    subscription_plan: SubscriptionPlan
    is_active: bool
    max_users: int
    max_products: int
    created_at: datetime

    class Config:
        from_attributes = True

class TenantRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Nom du magasin / entreprise")
    slug: Optional[str] = Field(None, max_length=100, description="Identifiant unique (ex: el-bahdja)")
    subscription_plan: SubscriptionPlan = SubscriptionPlan.PRO
    admin_username: str = Field(..., min_length=3, max_length=50)
    admin_password: str = Field(..., min_length=6)
    admin_email: Optional[str] = None
    admin_full_name: Optional[str] = None

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole = UserRole.CASHIER
    point_of_sale_id: Optional[int] = None

class UserOut(BaseModel):
    id: int
    tenant_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole
    point_of_sale_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    tenant: TenantOut
