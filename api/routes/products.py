"""Product CRUD routes — manage KINZ products and COGS."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import ProductCreate, ProductUpdate, ProductResponse, MarginResponse

router = APIRouter()


def _naive_utcnow() -> datetime:
    """Current UTC time as a NAIVE datetime.

    Replaces datetime.utcnow() (deprecated, scheduled for removal). The
    updated_at column stores naive UTC, so we compute in UTC explicitly and
    drop the tzinfo rather than writing an aware datetime that would mix
    representations in one column.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """List all products with COGS and prices."""
    result = db.execute(text(
        "SELECT id, name, category, cogs_tnd, b2b_price_tnd, b2c_price_tnd, "
        "alert_threshold_pct, active, created_at, updated_at FROM products ORDER BY id"
    ))
    return [dict(row._mapping) for row in result.fetchall()]


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(prod: ProductCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Create a new product with COGS."""
    result = db.execute(text("""
        INSERT INTO products (name, category, cogs_tnd, b2b_price_tnd, b2c_price_tnd, alert_threshold_pct, active)
        VALUES (:name, :cat, :cogs, :b2b, :b2c, :thr, true)
        RETURNING id, name, category, cogs_tnd, b2b_price_tnd, b2c_price_tnd, alert_threshold_pct, active, created_at, updated_at
    """), {"name": prod.name, "cat": prod.category, "cogs": prod.cogs_tnd,
           "b2b": prod.b2b_price_tnd, "b2c": prod.b2c_price_tnd, "thr": prod.alert_threshold_pct})
    # Fetch the RETURNING row BEFORE committing — SQLite requires the cursor
    # to be consumed before commit, and it's better practice for PostgreSQL too.
    row = result.fetchone()
    db.commit()
    return dict(row._mapping)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, prod: ProductUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Update a product's COGS, prices, or threshold."""
    # Build dynamic UPDATE
    fields = []
    params = {"pid": product_id}
    for field in ["name", "category", "cogs_tnd", "b2b_price_tnd", "b2c_price_tnd", "alert_threshold_pct", "active"]:
        val = getattr(prod, field, None)
        if val is not None:
            fields.append(f"{field} = :{field}")
            params[field] = val
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields.append("updated_at = :now")
    params["now"] = _naive_utcnow()

    db.execute(text(f"UPDATE products SET {', '.join(fields)} WHERE id = :pid"), params)
    db.commit()

    result = db.execute(text(
        "SELECT id, name, category, cogs_tnd, b2b_price_tnd, b2c_price_tnd, "
        "alert_threshold_pct, active, created_at, updated_at FROM products WHERE id = :pid"
    ), {"pid": product_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict(row._mapping)


@router.delete("/{product_id}")
def deactivate_product(product_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Deactivate a product (soft delete)."""
    db.execute(text("UPDATE products SET active = false, updated_at = :now WHERE id = :pid"),
               {"pid": product_id, "now": _naive_utcnow()})
    db.commit()
    return {"status": "deactivated", "product_id": product_id}


@router.get("/margins/latest", response_model=list[MarginResponse])
def get_latest_margins(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Get the latest margins for all products."""
    result = db.execute(text("""
        SELECT mh.product_id, p.name as product_name, CAST(mh.calc_date AS TEXT),
               mh.b2c_margin_pct, mh.b2b_margin_pct, mh.b2c_price_tnd,
               mh.b2b_price_tnd, mh.cogs_tnd
        FROM margin_history mh
        JOIN products p ON mh.product_id = p.id
        WHERE mh.calc_date = (SELECT MAX(calc_date) FROM margin_history)
        ORDER BY mh.b2c_margin_pct ASC
    """))
    return [dict(row._mapping) for row in result.fetchall()]
