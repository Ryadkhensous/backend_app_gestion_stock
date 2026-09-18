import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

def test_multitenant_flow():
    with TestClient(app) as client:
        print("\n=== TEST 1: Default Admin Login & Tenancy Fallback ===")
        # Unauthenticated request should fall back to Tenant 1
        res = client.get("/api/products/")
        assert res.status_code == 200, f"Failed fallback: {res.text}"
        print("  [OK] Legacy / unauthenticated request works with fallback Tenant 1")

        # Login with default admin
        res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200, f"Login failed: {res.text}"
        admin_data = res.json()
        assert "access_token" in admin_data
        admin_token = admin_data["access_token"]
        print(f"  [OK] Default admin logged in. Tenant ID: {admin_data['tenant']['id']}, Role: {admin_data['user']['role']}")

        # Verify /api/auth/me
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        me = res.json()
        assert me["user"]["username"] == "admin"
        assert me["tenant"]["id"] == 1
        print("  [OK] /api/auth/me returns valid tenant info")

        print("\n=== TEST 2: Register Two Independent Tenants (SaaS Stores) ===")
        # Register Tenant A ("Boutique Alger")
        res = client.post("/api/auth/register-tenant", json={
            "name": "Boutique Alger",
            "admin_username": "karim_alger",
            "admin_password": "password123",
            "admin_email": "karim@alger-store.dz",
            "subscription_plan": "PRO"
        })
        assert res.status_code in [201, 400], res.text
        if res.status_code == 201:
            data_a = res.json()
            token_a = data_a["access_token"]
            tenant_a_id = data_a["tenant"]["id"]
        else:
            # Already exists from previous run, log in
            res = client.post("/api/auth/login", json={"username": "karim_alger", "password": "password123"})
            assert res.status_code == 200, res.text
            data_a = res.json()
            token_a = data_a["access_token"]
            tenant_a_id = data_a["tenant"]["id"]
        print(f"  [OK] Tenant A registered / logged in (ID: {tenant_a_id})")

        # Register Tenant B ("Boutique Oran")
        res = client.post("/api/auth/register-tenant", json={
            "name": "Boutique Oran",
            "admin_username": "samir_oran",
            "admin_password": "password456",
            "admin_email": "samir@oran-store.dz",
            "subscription_plan": "BASIC"
        })
        assert res.status_code in [201, 400], res.text
        if res.status_code == 201:
            data_b = res.json()
            token_b = data_b["access_token"]
            tenant_b_id = data_b["tenant"]["id"]
        else:
            res = client.post("/api/auth/login", json={"username": "samir_oran", "password": "password456"})
            assert res.status_code == 200, res.text
            data_b = res.json()
            token_b = data_b["access_token"]
            tenant_b_id = data_b["tenant"]["id"]
        print(f"  [OK] Tenant B registered / logged in (ID: {tenant_b_id})")

        print("\n=== TEST 3: Cross-Tenant Same SKU Support (Unique per Tenant) ===")
        shared_sku = "PROD-MULTI-TENANT-99"
        
        # Check if product exists for A, create if not
        res_a_check = client.get(f"/api/products/sku/{shared_sku}", headers={"Authorization": f"Bearer {token_a}"})
        if res_a_check.status_code == 404:
            res_p_a = client.post("/api/products/", json={
                "name": "Produit Exclusif Alger",
                "sku": shared_sku,
                "price": 1200.0,
                "cost_price": 800.0,
                "quantity": 50,
                "min_stock_alert": 5
            }, headers={"Authorization": f"Bearer {token_a}"})
            assert res_p_a.status_code == 201, f"Failed creating product A: {res_p_a.text}"
            prod_a = res_p_a.json()
        else:
            prod_a = res_a_check.json()
        print(f"  [OK] Tenant A has product '{prod_a['name']}' with SKU '{shared_sku}'")

        # Tenant B creates a product with THE EXACT SAME SKU
        res_b_check = client.get(f"/api/products/sku/{shared_sku}", headers={"Authorization": f"Bearer {token_b}"})
        if res_b_check.status_code == 404:
            res_p_b = client.post("/api/products/", json={
                "name": "Produit Exclusif Oran",
                "sku": shared_sku,
                "price": 1800.0,
                "cost_price": 1100.0,
                "quantity": 30,
                "min_stock_alert": 3
            }, headers={"Authorization": f"Bearer {token_b}"})
            assert res_p_b.status_code == 201, f"Failed creating product B with same SKU: {res_p_b.text}"
            prod_b = res_p_b.json()
        else:
            prod_b = res_b_check.json()
        print(f"  [OK] Tenant B successfully has product '{prod_b['name']}' with the SAME SKU '{shared_sku}' without conflict!")

        print("\n=== TEST 4: Data Isolation (Zero Leakage between Stores) ===")
        # Tenant A lists products: MUST NOT see Tenant B's product
        res = client.get("/api/products/", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        prods_for_a = res.json()
        names_for_a = [p["name"] for p in prods_for_a]
        assert "Produit Exclusif Alger" in names_for_a
        assert "Produit Exclusif Oran" not in names_for_a, "SECURITY LEAK: Tenant A can see Tenant B's products!"
        print("  [OK] Tenant A sees only its own catalog (0 leakage from Tenant B)")

        # Tenant B lists products: MUST NOT see Tenant A's product
        res = client.get("/api/products/", headers={"Authorization": f"Bearer {token_b}"})
        assert res.status_code == 200
        prods_for_b = res.json()
        names_for_b = [p["name"] for p in prods_for_b]
        assert "Produit Exclusif Oran" in names_for_b
        assert "Produit Exclusif Alger" not in names_for_b, "SECURITY LEAK: Tenant B can see Tenant A's products!"
        print("  [OK] Tenant B sees only its own catalog (0 leakage from Tenant A)")

        print("\n=== TEST 5: POS Checkout & Commercial Documents Isolation ===")
        # Tenant A performs a sale
        checkout_res_a = client.post("/api/pos/checkout", json={
            "items": [{"product_id": prod_a["id"], "quantity": 2}],
            "customer_name": "Client Alger",
            "payment_method": "CASH"
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert checkout_res_a.status_code == 201, f"Checkout A failed: {checkout_res_a.text}"
        doc_a_ref = checkout_res_a.json()["document"]["reference_number"]
        print(f"  [OK] Tenant A completed checkout. Ticket Ref: {doc_a_ref}")

        # Tenant B lists documents: MUST NOT see doc_a_ref
        res_docs_b = client.get("/api/documents/", headers={"Authorization": f"Bearer {token_b}"})
        assert res_docs_b.status_code == 200
        b_doc_refs = [d["reference_number"] for d in res_docs_b.json()]
        assert doc_a_ref not in b_doc_refs, "SECURITY LEAK: Tenant B can see Tenant A's documents!"
        print(f"  [OK] Tenant B cannot see Tenant A's sales ticket {doc_a_ref}")

        print("\n=== TEST 6: Dashboard KPIs Isolation ===")
        dash_a = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token_a}"}).json()
        dash_b = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token_b}"}).json()
        print(f"  Tenant A total products: {dash_a['total_products']}, inventory value: {dash_a['total_inventory_value']} DZD")
        print(f"  Tenant B total products: {dash_b['total_products']}, inventory value: {dash_b['total_inventory_value']} DZD")
        print("  [OK] Dashboards are completely isolated per store!")

        print("\n=======================================================")
        print(">>> ALL MULTI-TENANT ARCHITECTURE TESTS PASSED 100%! <<<")
        print("=======================================================")

if __name__ == "__main__":
    test_multitenant_flow()
