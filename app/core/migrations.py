import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("stock_app")

def run_tenant_migrations(engine: Engine):
    """
    Applique les migrations de schéma requises pour le mode multi-tenant :
    - Ajout de la colonne tenant_id si absente sur les tables existantes
    - Remplacement des contraintes/index uniques globaux (ex: SKU unique) par des index composites (tenant_id, sku)
    - Création des index de performance par magasin
    - Rétrocompatibilité : affectation de toutes les données orphelines existantes au Magasin 1
    """
    logger.info("Exécution des migrations de schéma multi-tenant...")
    is_postgres = "postgres" in engine.dialect.name

    with engine.begin() as conn:
        tables = ["products", "categories", "points_of_sale", "stock_movements", "commercial_documents"]

        # 1. Ajout de la colonne tenant_id
        for table in tables:
            if is_postgres:
                conn.execute(text(f"""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='{table}' AND column_name='tenant_id'
                        ) THEN 
                            ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1;
                        END IF;
                    END $$;
                """))
            else:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1;"))
                except Exception:
                    pass

        # 2. Backfill des lignes orphelines
        for table in tables:
            try:
                conn.execute(text(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL;"))
            except Exception as e:
                logger.warning(f"Backfill {table} : {e}")

        # 3. Remplacement des index uniques globaux par des index composites tenant_id
        if is_postgres:
            try:
                # SKU unique par tenant
                conn.execute(text("DROP INDEX IF EXISTS ix_products_sku;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_products_tenant_sku ON products(tenant_id, sku);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_tenant_category ON products(tenant_id, category_id);"))

                # Catégorie unique par tenant
                conn.execute(text("DROP INDEX IF EXISTS ix_categories_name;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_tenant_name ON categories(tenant_id, name);"))

                # Référence document unique par tenant
                conn.execute(text("DROP INDEX IF EXISTS ix_commercial_documents_reference_number;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_tenant_ref ON commercial_documents(tenant_id, reference_number);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_tenant_date ON commercial_documents(tenant_id, issue_date);"))

                # Points de vente et mouvements
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pos_tenant_active ON points_of_sale(tenant_id, is_active);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_movements_tenant_created ON stock_movements(tenant_id, created_at);"))

                # Synchronisation des séquences d'identifiants PostgreSQL (évite collision sur NEXTVAL après insertion explicite)
                for tbl in ["tenants", "users", "products", "categories", "points_of_sale", "stock_movements", "commercial_documents", "document_items"]:
                    try:
                        conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 1));"))
                    except Exception:
                        pass

                logger.info("Index composites et contraintes de séparation multi-tenant appliqués avec succès.")
            except Exception as e:
                logger.error(f"Erreur lors de la configuration des index PostgreSQL : {e}")
