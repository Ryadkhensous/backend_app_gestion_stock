from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

class SellerCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Identifiant unique pour se connecter")
    password: str = Field(..., min_length=4, description="Mot de passe du vendeur")
    full_name: str = Field(..., min_length=2, max_length=120, description="Nom et prénom du vendeur")
    phone: Optional[str] = Field(None, max_length=30, description="Numéro de téléphone")
    email: Optional[str] = Field(None, max_length=120, description="Adresse email")
    commission_rate: float = Field(0.0, ge=0.0, le=100.0, description="Taux de commission en pourcentage (ex: 5.0 pour 5%)")
    commission_type: str = Field("PERCENTAGE", description="Type de calcul de commission (PERCENTAGE ou FIXED)")
    point_of_sale_id: Optional[int] = Field(None, description="Point de vente ou dépôt de rattachement")
    permissions: Optional[dict] = Field(None, description="Permissions spécifiques accordées au vendeur")
    is_active: bool = True

class SellerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=4, description="Nouveau mot de passe (optionnel)")
    commission_rate: Optional[float] = Field(None, ge=0.0, le=100.0)
    commission_type: Optional[str] = None
    point_of_sale_id: Optional[int] = None
    permissions: Optional[dict] = None
    is_active: Optional[bool] = None

class SellerPermissionsUpdate(BaseModel):
    permissions: dict = Field(..., description="Dictionnaire complet des permissions")

class SellerResponse(BaseModel):
    id: int
    tenant_id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    commission_rate: float = 0.0
    commission_type: str = "PERCENTAGE"
    point_of_sale_id: Optional[int] = None
    point_of_sale_name: Optional[str] = None
    permissions: Optional[dict] = None
    is_active: bool = True
    created_at: datetime
    total_sales_count: int = 0
    total_turnover: float = 0.0
    total_commission: float = 0.0

    model_config = ConfigDict(from_attributes=True)

class SellerSaleItem(BaseModel):
    id: int
    reference_number: str
    total_amount: float
    commission_amount: float
    issue_date: datetime
    status: str
    partner_name: Optional[str] = None
    point_of_sale_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SellerDetailResponse(BaseModel):
    seller: SellerResponse
    recent_sales: List[SellerSaleItem] = []

class SellerOverviewSummary(BaseModel):
    total_sellers: int = 0
    active_sellers: int = 0
    total_sales_count: int = 0
    total_turnover: float = 0.0
    total_commission: float = 0.0
    sellers: List[SellerResponse] = []
