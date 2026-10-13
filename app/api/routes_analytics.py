from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import random

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.models.product import Product
from app.models.point_of_sale import PointOfSale
from app.models.stock_movement import StockMovement
from app.models.commercial_document import (
    CommercialDocument,
    DocumentItem,
    DocumentType,
    DocumentDirection,
    DocumentStatus
)
from app.schemas.commercial_document import CommercialDocumentResponse
from app.api.routes_documents import to_document_response

router = APIRouter(prefix="/analytics", tags=["Analytics & Réapprovisionnement"])

class ReorderSuggestionItem(BaseModel):
    product_id: int
    product_name: str
    product_sku: str
    current_stock: int
    min_stock_alert: int
    suggested_order_quantity: int
    unit_cost_price: float
    total_estimated_cost: float
    category_name: Optional[str] = None

class ReorderOverviewResponse(BaseModel):
    total_products_in_alert: int
    total_units_to_order: int
    total_estimated_budget: float
    suggestions: List[ReorderSuggestionItem]

class FinancialOverviewResponse(BaseModel):
    inventory_sale_value: float
    inventory_cost_value: float
    potential_gross_margin: float
    margin_percentage: float
    total_products: int
    total_stock_units: int

@router.get("/reorder-suggestions", response_model=ReorderOverviewResponse)
def get_reorder_suggestions(
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    depleted_products = db.query(Product).options(
        joinedload(Product.category)
    ).filter(
        Product.tenant_id == tenant_id,
        Product.quantity <= Product.min_stock_alert
    ).order_by(Product.quantity.asc()).all()

    suggestions = []
    total_units = 0
    total_budget = 0.0

    for p in depleted_products:
        target_stock = max(p.min_stock_alert * 2, 10)
        needed = max(target_stock - p.quantity, 1)
        item_cost = round(needed * p.cost_price, 2)

        total_units += needed
        total_budget += item_cost

        suggestions.append(ReorderSuggestionItem(
            product_id=p.id,
            product_name=p.name,
            product_sku=p.sku,
            current_stock=p.quantity,
            min_stock_alert=p.min_stock_alert,
            suggested_order_quantity=needed,
            unit_cost_price=p.cost_price,
            total_estimated_cost=item_cost,
            category_name=p.category.name if p.category else None
        ))

    return ReorderOverviewResponse(
        total_products_in_alert=len(suggestions),
        total_units_to_order=total_units,
        total_estimated_budget=round(total_budget, 2),
        suggestions=suggestions
    )

class AutoOrderRequest(BaseModel):
    supplier_name: Optional[str] = "Fournisseur Général"
    point_of_sale_id: Optional[int] = None
    notes: Optional[str] = "Commande générée automatiquement par calcul des ruptures"

@router.post("/auto-order", response_model=CommercialDocumentResponse, status_code=status.HTTP_201_CREATED)
def generate_auto_reorder_document(
    payload: AutoOrderRequest,
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    depleted_products = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.quantity <= Product.min_stock_alert
    ).all()
    if not depleted_products:
        raise HTTPException(status_code=400, detail="Aucun produit en rupture ou alerte de stock bas.")

    date_str = datetime.now().strftime("%Y%m%d")
    random_suffix = random.randint(100, 999)
    ref = f"BC-AUTO-{date_str}-{random_suffix}"

    total_amount = 0.0
    doc_items = []

    for p in depleted_products:
        target_stock = max(p.min_stock_alert * 2, 10)
        needed = max(target_stock - p.quantity, 1)
        line_cost = round(needed * p.cost_price, 2)
        total_amount += line_cost

        doc_item = DocumentItem(
            product_id=p.id,
            quantity=needed,
            unit_price=p.cost_price,
            total_price=line_cost
        )
        doc_items.append(doc_item)

    doc = CommercialDocument(
        tenant_id=tenant_id,
        reference_number=ref,
        doc_type=DocumentType.ORDER,
        direction=DocumentDirection.INCOMING,
        status=DocumentStatus.VALIDATED,
        point_of_sale_id=payload.point_of_sale_id,
        partner_name=payload.supplier_name or "Fournisseur Réapprovisionnement",
        total_amount=round(total_amount, 2),
        notes=payload.notes,
        issue_date=datetime.now(timezone.utc)
    )
    doc.items = doc_items

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return to_document_response(doc)

@router.get("/financials", response_model=FinancialOverviewResponse)
def get_financial_overview(
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    stock_summary = db.query(
        func.coalesce(func.sum(Product.quantity), 0).label("total_units"),
        func.coalesce(func.sum(Product.quantity * Product.price), 0.0).label("sale_val"),
        func.coalesce(func.sum(Product.quantity * Product.cost_price), 0.0).label("cost_val"),
        func.count(Product.id).label("total_prods")
    ).filter(Product.tenant_id == tenant_id).first()

    sale_val = round(float(stock_summary.sale_val), 2) if stock_summary else 0.0
    cost_val = round(float(stock_summary.cost_val), 2) if stock_summary else 0.0
    margin = round(sale_val - cost_val, 2)
    margin_pct = round((margin / sale_val) * 100, 1) if sale_val > 0 else 0.0

    return FinancialOverviewResponse(
        inventory_sale_value=sale_val,
        inventory_cost_value=cost_val,
        potential_gross_margin=margin,
        margin_percentage=margin_pct,
        total_products=int(stock_summary.total_prods) if stock_summary else 0,
        total_stock_units=int(stock_summary.total_units) if stock_summary else 0
    )


class ProductProfitItem(BaseModel):
    product_id: int
    product_name: str
    product_sku: str
    category_name: Optional[str] = None
    current_stock: int
    quantity_sold: int
    avg_sale_price: float
    unit_cost_price: float
    total_revenue: float
    total_cost: float
    total_profit: float
    margin_percentage: float
    sales_count: int


class DailyProfitItem(BaseModel):
    date: str
    revenue: float
    cost: float
    profit: float
    units_sold: int


class ProfitSummary(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_revenue: float
    total_cost: float
    total_profit: float
    margin_percentage: float
    total_units_sold: int
    total_sales_count: int
    top_profitable_product: Optional[str] = None


class ProfitByProductResponse(BaseModel):
    summary: ProfitSummary
    products: List[ProductProfitItem]
    daily_breakdown: List[DailyProfitItem]


def parse_date_boundary(date_str: Optional[str], is_end: bool = False) -> Optional[datetime]:
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    try:
        if "T" in cleaned:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(cleaned, "%Y-%m-%d")
            if is_end:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@router.get("/profit-by-product", response_model=ProfitByProductResponse)
def get_profit_by_product(
    start_date: Optional[str] = Query(None, description="Date de début (YYYY-MM-DD ou ISO)"),
    end_date: Optional[str] = Query(None, description="Date de fin (YYYY-MM-DD ou ISO)"),
    point_of_sale_id: Optional[int] = Query(None, description="Filtre par point de vente"),
    category_id: Optional[int] = Query(None, description="Filtre par catégorie"),
    search: Optional[str] = Query(None, description="Recherche nom ou référence"),
    sort_by: str = Query("profit_desc", description="Tri: profit_desc, profit_asc, revenue_desc, quantity_desc, name_asc"),
    include_unsold: bool = Query(False, description="Inclure les produits du stock sans vente sur la période"),
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    s_date = start_date if isinstance(start_date, str) else None
    e_date = end_date if isinstance(end_date, str) else None
    pos_id = point_of_sale_id if isinstance(point_of_sale_id, int) else None
    cat_id = category_id if isinstance(category_id, int) else None
    s_term = search if isinstance(search, str) else None
    s_by = sort_by if isinstance(sort_by, str) else "profit_desc"
    inc_unsold = include_unsold if isinstance(include_unsold, bool) else False

    start_dt = parse_date_boundary(s_date, is_end=False)
    end_dt = parse_date_boundary(e_date, is_end=True)

    date_col = func.coalesce(CommercialDocument.delivery_date, CommercialDocument.issue_date, CommercialDocument.created_at)

    query = db.query(
        DocumentItem,
        CommercialDocument,
        Product
    ).join(
        CommercialDocument, DocumentItem.document_id == CommercialDocument.id
    ).join(
        Product, DocumentItem.product_id == Product.id
    ).options(
        joinedload(Product.category)
    ).filter(
        CommercialDocument.tenant_id == tenant_id,
        Product.tenant_id == tenant_id,
        CommercialDocument.direction == DocumentDirection.OUTGOING,
        CommercialDocument.status == DocumentStatus.DELIVERED
    )

    if start_dt:
        query = query.filter(date_col >= start_dt)
    if end_dt:
        query = query.filter(date_col <= end_dt)
    if pos_id:
        query = query.filter(CommercialDocument.point_of_sale_id == pos_id)
    if cat_id:
        query = query.filter(Product.category_id == cat_id)
    if s_term:
        term_filter = f"%{s_term.strip()}%"
        query = query.filter((Product.name.ilike(term_filter)) | (Product.sku.ilike(term_filter)))

    sold_records = query.all()

    product_stats = {}
    daily_stats = {}
    distinct_doc_ids = set()

    for item, doc, prod in sold_records:
        distinct_doc_ids.add(doc.id)

        qty = item.quantity
        line_rev = item.total_price if (item.total_price and item.total_price > 0) else round(qty * item.unit_price, 2)
        cost_unit = item.cost_price if (item.cost_price and item.cost_price > 0) else (prod.cost_price or 0.0)
        line_cost = round(qty * cost_unit, 2)
        line_profit = round(line_rev - line_cost, 2)

        doc_dt = doc.delivery_date or doc.issue_date or doc.created_at
        day_key = doc_dt.strftime("%Y-%m-%d") if doc_dt else datetime.now().strftime("%Y-%m-%d")

        if day_key not in daily_stats:
            daily_stats[day_key] = {
                "revenue": 0.0,
                "cost": 0.0,
                "profit": 0.0,
                "units_sold": 0
            }
        daily_stats[day_key]["revenue"] += line_rev
        daily_stats[day_key]["cost"] += line_cost
        daily_stats[day_key]["profit"] += line_profit
        daily_stats[day_key]["units_sold"] += qty

        pid = prod.id
        if pid not in product_stats:
            product_stats[pid] = {
                "product": prod,
                "quantity_sold": 0,
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "sales_count": 0,
                "doc_ids": set()
            }

        product_stats[pid]["quantity_sold"] += qty
        product_stats[pid]["total_revenue"] += line_rev
        product_stats[pid]["total_cost"] += line_cost
        product_stats[pid]["total_profit"] += line_profit
        if doc.id not in product_stats[pid]["doc_ids"]:
            product_stats[pid]["doc_ids"].add(doc.id)
            product_stats[pid]["sales_count"] += 1

    if inc_unsold:
        prod_query = db.query(Product).options(joinedload(Product.category)).filter(Product.tenant_id == tenant_id)
        if cat_id:
            prod_query = prod_query.filter(Product.category_id == cat_id)
        if s_term:
            term_f = f"%{s_term.strip()}%"
            prod_query = prod_query.filter((Product.name.ilike(term_f)) | (Product.sku.ilike(term_f)))

        all_matching_products = prod_query.all()
        for p in all_matching_products:
            if p.id not in product_stats:
                product_stats[p.id] = {
                    "product": p,
                    "quantity_sold": 0,
                    "total_revenue": 0.0,
                    "total_cost": 0.0,
                    "total_profit": 0.0,
                    "sales_count": 0,
                    "doc_ids": set()
                }

    products_response = []
    tot_revenue = 0.0
    tot_cost = 0.0
    tot_units = 0

    for pid, data in product_stats.items():
        p: Product = data["product"]
        q_sold = data["quantity_sold"]
        p_rev = round(data["total_revenue"], 2)
        p_cost = round(data["total_cost"], 2)
        p_profit = round(p_rev - p_cost, 2)
        margin_pct = round((p_profit / p_rev) * 100, 1) if p_rev > 0 else 0.0
        avg_price = round(p_rev / q_sold, 2) if q_sold > 0 else p.price

        tot_revenue += p_rev
        tot_cost += p_cost
        tot_units += q_sold

        cat_name = p.category.name if p.category else None

        products_response.append(ProductProfitItem(
            product_id=p.id,
            product_name=p.name,
            product_sku=p.sku,
            category_name=cat_name,
            current_stock=p.quantity,
            quantity_sold=q_sold,
            avg_sale_price=avg_price,
            unit_cost_price=p.cost_price,
            total_revenue=p_rev,
            total_cost=p_cost,
            total_profit=p_profit,
            margin_percentage=margin_pct,
            sales_count=data["sales_count"]
        ))

    if s_by == "profit_desc":
        products_response.sort(key=lambda x: x.total_profit, reverse=True)
    elif s_by == "profit_asc":
        products_response.sort(key=lambda x: x.total_profit)
    elif s_by == "revenue_desc":
        products_response.sort(key=lambda x: x.total_revenue, reverse=True)
    elif s_by == "quantity_desc":
        products_response.sort(key=lambda x: x.quantity_sold, reverse=True)
    elif s_by == "name_asc":
        products_response.sort(key=lambda x: x.product_name.lower())
    else:
        products_response.sort(key=lambda x: x.total_profit, reverse=True)

    daily_breakdown = []
    for day_str in sorted(daily_stats.keys()):
        d_val = daily_stats[day_str]
        daily_breakdown.append(DailyProfitItem(
            date=day_str,
            revenue=round(d_val["revenue"], 2),
            cost=round(d_val["cost"], 2),
            profit=round(d_val["profit"], 2),
            units_sold=d_val["units_sold"]
        ))

    tot_revenue = round(tot_revenue, 2)
    tot_cost = round(tot_cost, 2)
    tot_profit = round(tot_revenue - tot_cost, 2)
    tot_margin_pct = round((tot_profit / tot_revenue) * 100, 1) if tot_revenue > 0 else 0.0
    top_product = products_response[0].product_name if (products_response and products_response[0].total_profit > 0) else None

    summary = ProfitSummary(
        start_date=s_date,
        end_date=e_date,
        total_revenue=tot_revenue,
        total_cost=tot_cost,
        total_profit=tot_profit,
        margin_percentage=tot_margin_pct,
        total_units_sold=tot_units,
        total_sales_count=len(distinct_doc_ids),
        top_profitable_product=top_product
    )

    return ProfitByProductResponse(
        summary=summary,
        products=products_response,
        daily_breakdown=daily_breakdown
    )

@router.get("/comprehensive-dashboard")
def get_comprehensive_dashboard(
    tenant_id: int = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Stock & Inventory summary
    stock_sum = db.query(
        func.coalesce(func.sum(Product.quantity), 0).label("total_units"),
        func.coalesce(func.sum(Product.quantity * Product.price), 0.0).label("sale_val"),
        func.coalesce(func.sum(Product.quantity * Product.cost_price), 0.0).label("cost_val"),
        func.count(Product.id).label("total_prods")
    ).filter(Product.tenant_id == tenant_id).first()

    # 2. Low stock products
    low_stock_query = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.quantity <= Product.min_stock_alert
    ).order_by(Product.quantity.asc())
    low_stock_count = low_stock_query.count()
    low_stock_sample = [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "quantity": p.quantity,
            "min_stock_alert": p.min_stock_alert,
            "price": p.price
        } for p in low_stock_query.limit(10).all()
    ]

    # 3. All delivered sales documents
    docs = db.query(CommercialDocument).filter(
        CommercialDocument.tenant_id == tenant_id,
        CommercialDocument.direction == DocumentDirection.OUTGOING,
        CommercialDocument.status == DocumentStatus.DELIVERED
    ).all()

    total_revenue = 0.0
    total_commissions = 0.0
    payment_methods_map = {"CASH": 0.0, "CARD": 0.0, "CREDIT": 0.0}
    payment_counts = {"CASH": 0, "CARD": 0, "CREDIT": 0}

    today_rev = 0.0
    seven_days_rev = 0.0
    month_rev = 0.0
    year_rev = 0.0

    today_orders = 0
    seven_days_orders = 0
    month_orders = 0
    year_orders = 0

    daily_trend_map = {}
    for i in range(13, -1, -1):
        d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_trend_map[d_str] = {"revenue": 0.0, "orders": 0, "cost": 0.0, "profit": 0.0}

    for d in docs:
        amount = d.total_amount or 0.0
        total_revenue += amount
        total_commissions += (d.commission_amount or 0.0)

        doc_date = d.delivery_date or d.issue_date or d.created_at
        if doc_date:
            if doc_date.tzinfo is None:
                doc_date = doc_date.replace(tzinfo=timezone.utc)

            if doc_date >= today_start:
                today_rev += amount
                today_orders += 1
            if doc_date >= seven_days_ago:
                seven_days_rev += amount
                seven_days_orders += 1
            if doc_date >= this_month_start:
                month_rev += amount
                month_orders += 1
            if doc_date >= this_year_start:
                year_rev += amount
                year_orders += 1

            d_str = doc_date.strftime("%Y-%m-%d")
            if d_str in daily_trend_map:
                daily_trend_map[d_str]["revenue"] += amount
                daily_trend_map[d_str]["orders"] += 1

        notes_str = (d.notes or "").upper()
        if "CARD" in notes_str or "CARTE" in notes_str:
            pm = "CARD"
        elif "CREDIT" in notes_str or "CRÉDIT" in notes_str:
            pm = "CREDIT"
        else:
            pm = "CASH"
        payment_methods_map[pm] = payment_methods_map.get(pm, 0.0) + amount
        payment_counts[pm] = payment_counts.get(pm, 0) + 1

    # 4. Total Cost & Profit from DocumentItems
    doc_items = db.query(DocumentItem).join(
        CommercialDocument, DocumentItem.document_id == CommercialDocument.id
    ).filter(
        CommercialDocument.tenant_id == tenant_id,
        CommercialDocument.direction == DocumentDirection.OUTGOING,
        CommercialDocument.status == DocumentStatus.DELIVERED
    ).all()

    total_cost = 0.0
    product_performance = {}

    for it in doc_items:
        c_price = it.cost_price or 0.0
        line_cost = it.quantity * c_price
        total_cost += line_cost

        pid = it.product_id or 0
        if pid not in product_performance:
            product_performance[pid] = {
                "id": pid,
                "name": it.product.name if it.product else f"Produit #{pid}",
                "sku": it.product.sku if it.product else "",
                "quantity": 0,
                "revenue": 0.0,
                "cost": 0.0,
                "profit": 0.0,
            }
        product_performance[pid]["quantity"] += it.quantity
        product_performance[pid]["revenue"] += it.total_price
        product_performance[pid]["cost"] += line_cost
        product_performance[pid]["profit"] += (it.total_price - line_cost)

        if it.document:
            d_date = it.document.delivery_date or it.document.issue_date or it.document.created_at
            if d_date:
                d_str = d_date.strftime("%Y-%m-%d")
                if d_str in daily_trend_map:
                    daily_trend_map[d_str]["cost"] += line_cost
                    daily_trend_map[d_str]["profit"] = daily_trend_map[d_str]["revenue"] - daily_trend_map[d_str]["cost"]

    top_products_profit = sorted(
        product_performance.values(),
        key=lambda x: x["profit"],
        reverse=True
    )[:8]

    top_products_volume = sorted(
        product_performance.values(),
        key=lambda x: x["quantity"],
        reverse=True
    )[:8]

    # 5. Sellers
    from app.models.user import User, UserRole, DEFAULT_SELLER_PERMISSIONS
    sellers = db.query(User).filter(
        User.tenant_id == tenant_id,
        (User.role.in_([UserRole.SELLER, UserRole.CASHIER])) | (User.commission_rate > 0)
    ).all()

    sellers_stats = []
    active_sellers_count = sum(1 for s in sellers if s.is_active)
    for s in sellers:
        s_docs = [d for d in docs if d.seller_id == s.id]
        s_turnover = sum(d.total_amount for d in s_docs)
        s_commissions = sum(d.commission_amount or 0.0 for d in s_docs)
        sellers_stats.append({
            "id": s.id,
            "username": s.username,
            "full_name": s.full_name or s.username,
            "phone": s.phone,
            "commission_rate": s.commission_rate,
            "is_active": s.is_active,
            "sales_count": len(s_docs),
            "turnover": round(s_turnover, 2),
            "commissions": round(s_commissions, 2),
            "permissions": s.permissions or DEFAULT_SELLER_PERMISSIONS
        })
    sellers_stats.sort(key=lambda x: x["turnover"], reverse=True)

    # 6. Sales by Point of Sale
    pos_list = db.query(PointOfSale).filter(PointOfSale.tenant_id == tenant_id).all()
    pos_stats = []
    for pos in pos_list:
        pos_docs = [d for d in docs if d.point_of_sale_id == pos.id]
        pos_turnover = sum(d.total_amount for d in pos_docs)
        pos_stats.append({
            "id": pos.id,
            "name": pos.name,
            "city": pos.city,
            "sales_count": len(pos_docs),
            "turnover": round(pos_turnover, 2)
        })
    pos_stats.sort(key=lambda x: x["turnover"], reverse=True)

    total_profit = round(total_revenue - total_cost, 2)
    margin_pct = round((total_profit / total_revenue) * 100, 1) if total_revenue > 0 else 0.0

    return {
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "total_profit": total_profit,
            "margin_percentage": margin_pct,
            "total_orders": len(docs),
            "inventory_sale_value": round(float(stock_sum.sale_val if stock_sum else 0), 2),
            "inventory_cost_value": round(float(stock_sum.cost_val if stock_sum else 0), 2),
            "total_stock_units": int(stock_sum.total_units if stock_sum else 0),
            "total_products_count": int(stock_sum.total_prods if stock_sum else 0),
            "low_stock_count": low_stock_count,
            "active_sellers_count": active_sellers_count,
            "total_sellers_count": len(sellers),
            "total_commissions_earned": round(total_commissions, 2),
        },
        "periods": {
            "today": {"revenue": round(today_rev, 2), "orders": today_orders},
            "last_7_days": {"revenue": round(seven_days_rev, 2), "orders": seven_days_orders},
            "this_month": {"revenue": round(month_rev, 2), "orders": month_orders},
            "this_year": {"revenue": round(year_rev, 2), "orders": year_orders},
        },
        "daily_trend": [
            {
                "date": k,
                "revenue": round(v["revenue"], 2),
                "cost": round(v["cost"], 2),
                "profit": round(v["profit"], 2),
                "orders": v["orders"],
            } for k, v in sorted(daily_trend_map.items())
        ],
        "payment_methods": {
            k: {
                "amount": round(payment_methods_map[k], 2),
                "count": payment_counts[k],
                "percentage": round((payment_methods_map[k] / total_revenue) * 100, 1) if total_revenue > 0 else 0.0
            } for k in payment_methods_map
        },
        "top_sellers": sellers_stats[:8],
        "all_sellers": sellers_stats,
        "top_products_profit": top_products_profit,
        "top_products_volume": top_products_volume,
        "sales_by_pos": pos_stats,
        "low_stock_items": low_stock_sample,
    }
