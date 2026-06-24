"""Alert history routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import AlertResponse

router = APIRouter()


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """View alert history (most recent first)."""
    result = db.execute(text("""
        SELECT a.id, a.product_id, a.alert_date, a.alert_type,
               a.margin_pct, a.threshold_pct, a.message, a.notified
        FROM alerts a
        ORDER BY a.alert_date DESC
        LIMIT :limit
    """), {"limit": limit})
    return [dict(row._mapping) for row in result.fetchall()]
