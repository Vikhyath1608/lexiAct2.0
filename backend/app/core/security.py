"""
app/core/security.py
────────────────────
JWT access + refresh token creation/verification.
bcrypt password hashing.
Secure token generation for OTP and password reset.
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Access token ──────────────────────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# ── Refresh token ─────────────────────────────────────────────────────────────

def create_refresh_token() -> str:
    """Generate a cryptographically secure random refresh token."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Store only the hash of the refresh token in Redis — never the raw value."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── OTP ───────────────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """6-digit numeric OTP."""
    return str(secrets.randbelow(900000) + 100000)


# ── Password reset token ──────────────────────────────────────────────────────

def generate_reset_token() -> str:
    """URL-safe 32-byte token for password reset links."""
    return secrets.token_urlsafe(32)
