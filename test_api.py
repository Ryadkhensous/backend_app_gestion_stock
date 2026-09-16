import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models import Product, PointOfSale, StockMovement, Category

class TestStockApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_01_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")

    def test_02_dashboard_stats(self):
        response = self.client.get("/api/dashboard/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_products", data)
        self.assertIn("total_points_of_sale", data)
        self.assertGreaterEqual(data["total_products"], 1)

    def test_03_points_of_sale_and_gps(self):
        # 1. Lister les points de vente
        res_list = self.client.get("/api/points-of-sale/")
        self.assertEqual(res_list.status_code, 200)
        points = res_list.json()
        self.assertGreaterEqual(len(points), 1)

        # 2. Créer un nouveau point de vente avec coordonnées GPS
        new_pos = {
            "name": "Nouveau Point de Vente Test",
            "address": "15 Rue Principale",
            "city": "Alger",
            "latitude": 36.7525,
            "longitude": 3.0420,
            "phone": "+213 550 12 34 56",
            "manager_name": "Test Manager",
            "is_active": True
        }
        res_create = self.client.post("/api/points-of-sale/", json=new_pos)
        self.assertEqual(res_create.status_code, 201)
        created = res_create.json()
        pos_id = created["id"]
        self.assertEqual(created["latitude"], 36.7525)

        # 3. Test de proximité GPS
        res_nearby = self.client.get(f"/api/points-of-sale/nearby?lat=36.7500&lng=3.0400&radius_km=10")
        self.assertEqual(res_nearby.status_code, 200)
        nearby_ids = [p["id"] for p in res_nearby.json()]
        self.assertIn(pos_id, nearby_ids)

        # 4. Suppression
        res_del = self.client.delete(f"/api/points-of-sale/{pos_id}")
        self.assertEqual(res_del.status_code, 204)

    def test_04_products_and_stock_movements(self):
        # 1. Créer un produit
        product_data = {
            "name": "Produit Test Unitaire",
            "sku": "SKU-UNIT-001",
            "description": "Description produit test",
            "price": 5000.0,
            "cost_price": 3000.0,
            "quantity": 10,
            "min_stock_alert": 5
        }
        res_prod = self.client.post("/api/products/", json=product_data)
        self.assertEqual(res_prod.status_code, 201)
        prod = res_prod.json()
        prod_id = prod["id"]
        self.assertEqual(prod["quantity"], 10)

        # 2. Enregistrer une sortie de stock de 8 unités (quantité restante: 2 -> passe en alerte stock bas !)
        mov_out = {
            "product_id": prod_id,
            "movement_type": "OUT",
            "quantity": 8,
            "reference": "FAC-TEST-01",
            "note": "Vente test"
        }
        res_mov = self.client.post("/api/stock-movements/", json=mov_out)
        self.assertEqual(res_mov.status_code, 201)

        # 3. Vérifier que la quantité a été mise à jour à 2 et que is_low_stock est True
        res_get = self.client.get(f"/api/products/{prod_id}")
        self.assertEqual(res_get.status_code, 200)
        updated_prod = res_get.json()
        self.assertEqual(updated_prod["quantity"], 2)
        self.assertTrue(updated_prod["is_low_stock"])

        # 4. Tenter une sortie supérieure au stock restant (doit échouer avec code 400)
        mov_invalid = {
            "product_id": prod_id,
            "movement_type": "OUT",
            "quantity": 100
        }
        res_invalid = self.client.post("/api/stock-movements/", json=mov_invalid)
        self.assertEqual(res_invalid.status_code, 400)

        # 5. Nettoyer
        self.client.delete(f"/api/products/{prod_id}")

if __name__ == "__main__":
    unittest.main()
