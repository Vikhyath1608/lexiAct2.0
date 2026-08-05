"""
app/core/redis.py
─────────────────
Async Redis client.
Handles: caching, rate limiting, OTP storage, refresh tokens,
         password reset tokens, OAuth state tokens.
"""
from __future__ import annotations
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ── Generic cache ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = None) -> None:
    r = await get_redis()
    await r.setex(key, ttl or settings.redis_cache_ttl, json.dumps(value))


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def is_rate_limited(identifier: str) -> bool:
    r = await get_redis()
    key = f"ratelimit:{identifier}"
    current = await r.get(key)
    if current is None:
        await r.setex(key, settings.rate_limit_window, 1)
        return False
    if int(current) >= settings.rate_limit_requests:
        return True
    await r.incr(key)
    return False


# ── OTP storage ───────────────────────────────────────────────────────────────

async def store_otp(user_id: int, otp: str) -> None:
    """Store OTP with TTL. Overwrites any existing OTP for this user."""
    r = await get_redis()
    await r.setex(
        f"otp:verify:{user_id}",
        settings.otp_expire_seconds,
        otp
    )


async def get_otp(user_id: int) -> Optional[str]:
    r = await get_redis()
    return await r.get(f"otp:verify:{user_id}")


async def delete_otp(user_id: int) -> None:
    r = await get_redis()
    await r.delete(f"otp:verify:{user_id}")


# ── Refresh token storage ─────────────────────────────────────────────────────

async def store_refresh_token(user_id: int, token_hash: str) -> None:
    """
    Store hashed refresh token. Key: refresh:{user_id}:{token_hash}
    Only the hash is stored — raw token is never persisted server-side.
    """
    r = await get_redis()
    ttl = settings.refresh_token_expire_days * 86400
    await r.setex(f"refresh:{user_id}:{token_hash}", ttl, "1")


async def refresh_token_exists(user_id: int, token_hash: str) -> bool:
    r = await get_redis()
    val = await r.get(f"refresh:{user_id}:{token_hash}")
    return val is not None


async def delete_refresh_token(user_id: int, token_hash: str) -> None:
    r = await get_redis()
    await r.delete(f"refresh:{user_id}:{token_hash}")


async def delete_all_refresh_tokens(user_id: int) -> None:
    """Logout from all devices — delete every refresh token for this user."""
    r = await get_redis()
    pattern = f"refresh:{user_id}:*"
    keys = await r.keys(pattern)
    if keys:
        await r.delete(*keys)


# ── Password reset token storage ──────────────────────────────────────────────

async def store_reset_token(token: str, user_id: int) -> None:
    r = await get_redis()
    await r.setex(
        f"reset:{token}",
        settings.password_reset_expire_seconds,
        str(user_id)
    )


async def get_reset_token_user(token: str) -> Optional[int]:
    r = await get_redis()
    val = await r.get(f"reset:{token}")
    return int(val) if val else None


async def delete_reset_token(token: str) -> None:
    r = await get_redis()
    await r.delete(f"reset:{token}")


# ── OAuth state token storage (CSRF protection) ───────────────────────────────

async def store_oauth_state(state: str, provider: str) -> None:
    """Store OAuth state token for 10 minutes to prevent CSRF."""
    r = await get_redis()
    await r.setex(f"oauth:state:{state}", 600, provider)


async def verify_oauth_state(state: str) -> Optional[str]:
    """Verify and consume OAuth state — returns provider or None."""
    r = await get_redis()
    provider = await r.get(f"oauth:state:{state}")
    if provider:
        await r.delete(f"oauth:state:{state}")
    return provider


# ── Health check ──────────────────────────────────────────────────────────────

async def redis_ping() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        return False
