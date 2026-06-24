"""Pydantic models for the FastAPI backend."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    cogs_tnd: float = Field(..., gt=0, description="Cost of Goods Sold in TND")
    b2b_price_tnd: Optional[float] = Field(None, gt=0)
    b2c_price_tnd: Optional[float] = Field(None, gt=0)
    alert_threshold_pct: float = Field(40.0, ge=0, le=100)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    cogs_tnd: Optional[float] = Field(None, gt=0)
    b2b_price_tnd: Optional[float] = Field(None, gt=0)
    b2c_price_tnd: Optional[float] = Field(None, gt=0)
    alert_threshold_pct: Optional[float] = Field(None, ge=0, le=100)
    active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThresholdUpdate(BaseModel):
    alert_threshold_pct: float = Field(..., ge=0, le=100)


class AlertResponse(BaseModel):
    id: int
    product_id: int
    alert_date: datetime
    alert_type: str
    margin_pct: float
    threshold_pct: float
    message: str
    notified: bool

    class Config:
        from_attributes = True


class MarginResponse(BaseModel):
    product_id: int
    product_name: str
    calc_date: str
    b2c_margin_pct: float
    b2b_margin_pct: float
    b2c_price_tnd: float
    b2b_price_tnd: float
    cogs_tnd: float

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRequest(BaseModel):
    email: str
    password: str
