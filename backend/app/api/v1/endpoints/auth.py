"""
app/api/v1/endpoints/auth.py
─────────────────────────────
Complete authentication system:
  POST /register              — create account (is_active=False)
  POST /verify-otp            — activate account with OTP
  POST /resend-otp            — resend OTP email
  POST /login                 — password login → JWT + refresh token cookie
  POST /refresh               — rotate refresh token → new access token
  POST /logout                — invalidate refresh token
  POST /logout-all            — invalidate all refresh tokens (all devices)
  POST /forgot-password       — send reset email
  POST /reset-password        — apply new password using reset token
  POST /change-password       — change password (authenticated)
  GET  /me                    — current user profile
  GET  /oauth/google/login    — redirect to Google
  GET  /oauth/google/callback — handle Google callback
  GET  /oauth/github/login    — redirect to GitHub
  GET  /oauth/github/callback — handle GitHub callback
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.logging import get_logger
from app.core.redis import (
    delete_all_refresh_tokens,
    delete_otp,
    delete_refresh_token,
    delete_reset_token,
    get_otp,
    get_reset_token_user,
    refresh_token_exists,
    store_otp,
    store_refresh_token,
    store_reset_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_otp,
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserPublic,
    VerifyOTPRequest,
)
from app.services.oauth_service import (
    get_github_login_url,
    get_google_login_url,
    handle_github_callback,
    handle_google_callback,
)
from app.workers.celery_app import send_otp_email_task, send_reset_email_task

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)

REFRESH_COOKIE = "refresh_token"
COOKIE_OPTS = dict(
    httponly=True,
    secure=False,       # set True in production (HTTPS)
    samesite="lax",
    max_age=settings.refresh_token_expire_days * 86400,
    path="/api/v1/auth",
)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(REFRESH_COOKIE, token, **COOKIE_OPTS)


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check uniqueness
    dup_user = await db.execute(select(User).where(User.username == body.username))
    if dup_user.scalar_one_or_none():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")

    dup_email = await db.execute(select(User).where(User.email == body.email))
    if dup_email.scalar_one_or_none():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        is_active=False,   # inactive until OTP verified
    )
    db.add(user)
    await db.flush()  # get ID without committing

    # Generate OTP and store in Redis
    otp = generate_otp()
    await store_otp(user.id, otp)

    # Dispatch OTP email asynchronously via Celery
    send_otp_email_task.apply_async(
        args=[user.email, otp, user.full_name],
        countdown=0,
    )

    logger.info("user_registered", user_id=user.id, email=user.email)
    return {
        "message": "Registration successful. Check your email for the verification code.",
        "user_id": user.id,
    }


# ── Verify OTP ────────────────────────────────────────────────────────────────

@router.post("/verify-otp")
async def verify_otp(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Account already verified")

    stored_otp = await get_otp(body.user_id)
    if not stored_otp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired. Request a new one.")
    if stored_otp != body.otp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OTP")

    user.is_active = True
    await delete_otp(body.user_id)
    logger.info("user_verified", user_id=user.id)
    return {"message": "Account verified successfully. You can now log in."}


# ── Resend OTP ────────────────────────────────────────────────────────────────

@router.post("/resend-otp")
async def resend_otp(body: ResendOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        # Don't reveal whether email exists
        return {"message": "If that email exists, a new code has been sent."}
    if user.is_active:
        return {"message": "Account already verified."}

    otp = generate_otp()
    await store_otp(user.id, otp)
    send_otp_email_task.apply_async(args=[user.email, otp, user.full_name])
    return {"message": "New verification code sent."}


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Account not verified. Check your email for the OTP.",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    token_hash = hash_token(refresh_token)
    await store_refresh_token(user.id, token_hash)

    _set_refresh_cookie(response, refresh_token)
    logger.info("user_login", user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        username=user.username,
        full_name=user.full_name,
        user_id=user.id,
    )


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token provided")

    # Decode the access token to get user_id — we carry user_id in refresh key
    # Actually we scan: refresh token is opaque, so we need to check all users
    # Better: embed user_id in a separate cookie or use a different mechanism
    # We'll use a lightweight approach: try to find the token across possible users
    # In production use a separate user_id cookie or embed in signed cookie
    token_hash = hash_token(refresh_token)

    # Find user by scanning refresh keys — we use a dedicated lookup cookie
    user_id = await _find_user_by_refresh_hash(token_hash)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # Rotate: delete old, issue new
    await delete_refresh_token(user.id, token_hash)
    new_refresh = create_refresh_token()
    new_hash = hash_token(new_refresh)
    await store_refresh_token(user.id, new_hash)
    new_access = create_access_token(user.id)

    _set_refresh_cookie(response, new_refresh)
    logger.info("token_refreshed", user_id=user.id)

    return TokenResponse(
        access_token=new_access,
        username=user.username,
        full_name=user.full_name,
        user_id=user.id,
    )


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if refresh_token:
        token_hash = hash_token(refresh_token)
        await delete_refresh_token(current_user.id, token_hash)
    _clear_refresh_cookie(response)
    logger.info("user_logout", user_id=current_user.id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Invalidate all refresh tokens for this user (logout from all devices)."""
    await delete_all_refresh_tokens(current_user.id)
    _clear_refresh_cookie(response)
    logger.info("user_logout_all_devices", user_id=current_user.id)


# ── Forgot password ───────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always return same message — don't reveal if email exists
    if user and user.is_active:
        token = generate_reset_token()
        await store_reset_token(token, user.id)
        send_reset_email_task.apply_async(args=[user.email, token, user.full_name])

    return {"message": "If that email is registered, a reset link has been sent."}


# ── Reset password ────────────────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_reset_token_user(body.token)
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.hashed_password = hash_password(body.new_password)
    # Invalidate token immediately after use
    await delete_reset_token(body.token)
    # Invalidate all active sessions
    await delete_all_refresh_tokens(user.id)

    logger.info("password_reset", user_id=user.id)
    return {"message": "Password reset successful. Please log in again."}


# ── Change password (authenticated) ──────────────────────────────────────────

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    if not current_user.hashed_password or not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    current_user.hashed_password = hash_password(body.new_password)
    await delete_all_refresh_tokens(current_user.id)
    logger.info("password_changed", user_id=current_user.id)
    return {"message": "Password changed successfully. Please log in again."}


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/oauth/google/login")
async def google_login():
    url = await get_google_login_url()
    return RedirectResponse(url)


@router.get("/oauth/google/callback")
async def google_callback(
    code: str,
    state: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    profile = await handle_google_callback(code, state)
    if not profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google OAuth failed — invalid state")
    return await _oauth_login_or_register(profile, response, db)


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

@router.get("/oauth/github/login")
async def github_login():
    url = await get_github_login_url()
    return RedirectResponse(url)


@router.get("/oauth/github/callback")
async def github_callback(
    code: str,
    state: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    profile = await handle_github_callback(code, state)
    if not profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub OAuth failed — invalid state or no email")
    return await _oauth_login_or_register(profile, response, db)


# ── OAuth shared login/register logic ─────────────────────────────────────────

async def _oauth_login_or_register(
    profile: dict,
    response: Response,
    db: AsyncSession,
) -> TokenResponse:
    """
    Find existing user by email or oauth_sub.
    If found: link OAuth provider if not already linked, log in.
    If not found: create new verified account.
    """
    email = profile["email"]
    provider = profile["provider"]
    sub = profile["sub"]

    # Try find by oauth sub first (most specific)
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_sub == sub)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Try find by email (account linking)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Link OAuth to existing account
            user.oauth_provider = provider
            user.oauth_sub = sub
            user.is_active = True  # email verified by OAuth provider
        else:
            # Create new OAuth account — no password, already verified
            username = await _unique_username(profile["username"], db)
            user = User(
                username=username,
                email=email,
                full_name=profile["full_name"],
                hashed_password=None,
                is_active=True,
                oauth_provider=provider,
                oauth_sub=sub,
            )
            db.add(user)
            await db.flush()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    await store_refresh_token(user.id, hash_token(refresh_token))
    _set_refresh_cookie(response, refresh_token)

    logger.info("oauth_login", user_id=user.id, provider=provider)
    return TokenResponse(
        access_token=access_token,
        username=user.username,
        full_name=user.full_name,
        user_id=user.id,
    )


async def _unique_username(base: str, db: AsyncSession) -> str:
    """Ensure username is unique by appending a counter if needed."""
    import re
    base = re.sub(r"[^a-zA-Z0-9_]", "", base)[:50] or "user"
    username = base
    counter = 1
    while True:
        result = await db.execute(select(User).where(User.username == username))
        if not result.scalar_one_or_none():
            return username
        username = f"{base}{counter}"
        counter += 1


async def _find_user_by_refresh_hash(token_hash: str) -> int | None:
    """
    Find which user owns this refresh token hash.
    Uses a Redis scan — in production store user_id alongside the token.
    """
    from app.core.redis import get_redis
    r = await get_redis()
    # Pattern: refresh:{user_id}:{token_hash}
    keys = await r.keys(f"refresh:*:{token_hash}")
    if not keys:
        return None
    # Extract user_id from key: refresh:{user_id}:{hash}
    parts = keys[0].split(":")
    if len(parts) >= 3:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None
