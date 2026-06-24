"""Simulate competitor pricing data for testing the pipeline."""
import sys
import random
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sqlalchemy import create_engine, text
from src.config import DATABASE_URL


def main(days: int = 30):
    """Generate `days` of historical competitor prices for all products."""
    engine = create_engine(DATABASE_URL)
    np.random.seed(42)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, b2c_price_tnd FROM products WHERE active = true"))
        products = result.fetchall()

    if not products:
        print("No active products found. Run seed_products.py first.")
        return

    today = date.today()
    total = 0

    with engine.begin() as conn:
        for days_ago in range(days):
            calc_date = today - timedelta(days=days_ago)
            # Delete existing for this date
            conn.execute(text("DELETE FROM daily_prices WHERE price_date = :d"), {"d": calc_date})

            for prod_id, b2c_price in products:
                base = float(b2c_price) if b2c_price else 30.0
                noise = np.random.uniform(-0.05, 0.05)
                price = round(base * (1 + noise), 3)
                conn.execute(text("""
                    INSERT INTO daily_prices (product_id, price_date, competitor_price_tnd, source)
                    VALUES (:pid, :d, :p, 'simulated')
                """), {"pid": prod_id, "d": calc_date, "p": price})
                total += 1

    print(f"✅ Generated {total} competitor price records ({days} days × {len(products)} products).")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    main(days=args.days)
