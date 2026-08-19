"""FastAPI entrypoint for the Kinz Margin Guardian backend."""
from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

from api.auth import create_access_token, authenticate_user
from api.models import Token, TokenRequest
from api.routes import products, thresholds, alerts

app = FastAPI(
    title="Kinz Margin Guardian API",
    description="Backend for managing KINZ product COGS, alert thresholds, and viewing margin alerts.",
    version="1.0.0",
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS (allow Streamlit dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "Kinz Margin Guardian API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/token", response_model=Token)
def login(req: TokenRequest):
    """Authenticate and return a JWT access token."""
    if not authenticate_user(req.email, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(
        data={"sub": req.email, "role": "admin"},
        expires_delta=timedelta(minutes=60),
    )
    return Token(access_token=token)


# Mount route modules
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(thresholds.router, prefix="/thresholds", tags=["thresholds"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
