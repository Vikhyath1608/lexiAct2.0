"""
app/services/oauth_service.py
──────────────────────────────
Google and GitHub OAuth 2.0 authorization code flow.
Uses httpx for token exchange — no heavy authlib dependency.

Flow:
1. GET /auth/oauth/{provider}/login  → redirect to provider
2. Provider redirects to /auth/oauth/{provider}/callback?code=...&state=...
3. Backend exchanges code for access token
4. Backend fetches user profile
5. Creates/links account, issues JWT + refresh token
"""
from __future__ import annotations
import secrets
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import store_oauth_state, verify_oauth_state

logger = get_logger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"


# ── Google ────────────────────────────────────────────────────────────────────

async def get_google_login_url() -> str:
    state = secrets.token_urlsafe(32)
    await store_oauth_state(state, "google")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def handle_google_callback(code: str, state: str) -> Optional[dict]:
    """Exchange code for profile. Returns user dict or None."""
    provider = await verify_oauth_state(state)
    if provider != "google":
        logger.warning("Invalid OAuth state for Google callback")
        return None

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # Fetch user profile
        profile_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_resp.raise_for_status()
        profile = profile_resp.json()

    return {
        "provider": "google",
        "sub": profile["id"],
        "email": profile["email"],
        "full_name": profile.get("name", ""),
        "username": profile["email"].split("@")[0],
    }


# ── GitHub ────────────────────────────────────────────────────────────────────

async def get_github_login_url() -> str:
    state = secrets.token_urlsafe(32)
    await store_oauth_state(state, "github")
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTH_URL}?{query}"


async def handle_github_callback(code: str, state: str) -> Optional[dict]:
    """Exchange code for profile. Returns user dict or None."""
    provider = await verify_oauth_state(state)
    if provider != "github":
        logger.warning("Invalid OAuth state for GitHub callback")
        return None

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        # Fetch user profile
        profile_resp = await client.get(GITHUB_USERINFO_URL, headers=headers)
        profile_resp.raise_for_status()
        profile = profile_resp.json()

        # GitHub may not expose email publicly — fetch from emails endpoint
        email = profile.get("email")
        if not email:
            emails_resp = await client.get(GITHUB_EMAIL_URL, headers=headers)
            emails_resp.raise_for_status()
            primary = next(
                (e for e in emails_resp.json() if e.get("primary") and e.get("verified")),
                None,
            )
            email = primary["email"] if primary else None

    if not email:
        return None

    return {
        "provider": "github",
        "sub": str(profile["id"]),
        "email": email,
        "full_name": profile.get("name") or profile.get("login", ""),
        "username": profile.get("login", email.split("@")[0]),
    }
