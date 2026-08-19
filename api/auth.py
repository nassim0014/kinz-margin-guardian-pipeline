"""JWT authentication for the FastAPI backend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
import os

security = HTTPBearer()

# Demo credentials (in production, use a proper user store)
API_USER = os.getenv("API_USER", "admin@kinzoils.com")
API_PASSWORD = os.getenv("API_PASSWORD", "change_me_in_prod")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify a JWT token and return its claims."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None


def authenticate_user(email: str, password: str) -> bool:
    """Check credentials against env vars (demo mode)."""
    return email == API_USER and password == API_PASSWORD


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency: verify JWT and return user info."""
    payload = verify_token(credentials.credentials)
    return {"email": payload.get("sub"), "role": payload.get("role", "admin")}
