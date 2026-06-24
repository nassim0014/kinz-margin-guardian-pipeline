"""Seed the database with real KINZ products and estimated COGS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from src.config import DATABASE_URL

# Real KINZ product catalog (scraped from kinzoils.com)
# COGS estimated at 30-45% of retail price (standard for Tunisian cosmetics)
PRODUCTS = [
    # (name, category, cogs, b2b_price, b2c_price)
    ("Huile Pépins de Figue de Barbarie", "Vegetable Oils", 23.600, 50.150, 59.000),
    ("Crème Hydratante Visage 100gr", "Skincare", 19.600, 41.650, 49.000),
    ("Crème Contour des Yeux", "Skincare", 14.800, 25.500, 30.000),
    ("Sérum Éclat Vitamine C", "Skincare", 12.000, 25.500, 30.000),
    ("Huile d'Amande Douce 30ml", "Vegetable Oils", 6.000, 12.750, 15.000),
    ("Huile de Nigelle", "Vegetable Oils", 8.000, 16.150, 19.000),
    ("Huile de Sésame", "Vegetable Oils", 7.200, 14.450, 17.000),
    ("Huile de Cresson", "Vegetable Oils", 7.600, 15.300, 18.000),
    ("Lait de Corps Monoi", "Body Care", 8.400, 17.000, 20.000),
    ("Huile Sèche Jasmin", "Body Care", 14.000, 29.750, 35.000),
    ("Gel Nettoyant", "Body Care", 9.200, 18.700, 22.000),
    ("Pack Anti-Âge & Éclat Naturel", "Gift Sets", 62.800, 133.450, 157.000),
    ("Pack l'Essentiel Anti-âge", "Gift Sets", 49.600, 105.400, 124.000),
    ("Pack Hydratation & Anti-Tâches", "Gift Sets", 39.600, 84.150, 99.000),
    ("Trousse Rose Clair", "Accessories", 7.960, 16.915, 19.900),
    ("Trousse Verte", "Accessories", 7.960, 16.915, 19.900),
    ("Trousse Blanc-Cassé", "Accessories", 7.960, 16.915, 19.900),
    ("Trio Floral Jasmin", "Gift Sets", 20.000, 42.500, 50.000),
    ("Trio Fruité Framboise", "Gift Sets", 20.000, 42.500, 50.000),
    ("Trio Fresh & Tonique Bergamote", "Gift Sets", 20.000, 42.500, 50.000),
    ("Duo Fresh & Tonique Bergamote", "Gift Sets", 13.200, 28.050, 33.000),
    ("Duo Fruité Framboise", "Gift Sets", 13.200, 28.050, 33.000),
    ("Brume Parfumée Bergamote", "Fragrance", 9.600, 20.400, 24.000),
    ("Gel Douche Bergamote", "Body Care", 8.000, 17.000, 20.000),
    ("Lait de Corps Bergamote", "Body Care", 8.000, 17.000, 20.000),
    ("Huile Sèche Pailletée Bergamote", "Body Care", 14.000, 29.750, 35.000),
    ("Brume Parfumée Jasmin", "Fragrance", 9.600, 20.400, 24.000),
    ("Gel Douche Jasmin", "Body Care", 8.000, 17.000, 20.000),
    ("Lait de Corps Jasmin", "Body Care", 8.000, 17.000, 20.000),
    ("Pack Jasmin + Trousse offerte", "Gift Sets", 39.600, 84.150, 99.000),
]


def main():
    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        # Clear existing products (for idempotent re-run)
        conn.execute(text("DELETE FROM products"))

        for name, category, cogs, b2b, b2c in PRODUCTS:
            conn.execute(text("""
                INSERT INTO products (name, category, cogs_tnd, b2b_price_tnd, b2c_price_tnd, alert_threshold_pct, active)
                VALUES (:name, :cat, :cogs, :b2b, :b2c, 40.00, true)
            """), {"name": name, "cat": category, "cogs": cogs, "b2b": b2b, "b2c": b2c})

    print(f"✅ Seeded {len(PRODUCTS)} KINZ products into the database.")


if __name__ == "__main__":
    main()
