"""Alert threshold configuration routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import ThresholdUpdate

router = APIRouter()


@router.get("")
def list_thresholds(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """List alert thresholds for all products."""
    result = db.execute(text(
        "SELECT id, name, alert_threshold_pct FROM products WHERE active = true ORDER BY name"
    ))
    return [dict(row._mapping) for row in result.fetchall()]


@router.put("/{product_id}")
def update_threshold(product_id: int, thr: ThresholdUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Update the alert threshold for a specific product."""
    db.execute(text(
        "UPDATE products SET alert_threshold_pct = :thr WHERE id = :pid"
    ), {"thr": thr.alert_threshold_pct, "pid": product_id})
    db.commit()
    return {"status": "updated", "product_id": product_id, "threshold_pct": thr.alert_threshold_pct}
