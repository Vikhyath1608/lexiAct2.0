"""
tests/integration/test_api.py
──────────────────────────────
Integration tests for auth, chat, and health endpoints.
Uses SQLite in-memory DB — no PostgreSQL needed.
Mocks Redis and Celery so no external services required.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.db.database import Base
from app.core.dependencies import get_db

# ── Test DB setup ─────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session
        await session.commit()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _register_and_activate(client, username="testuser", email="test@example.com", password="pass1234"):
    """Register a user and bypass OTP to activate them directly."""
    # Mock Redis store_otp and Celery task
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        })
        assert r.status_code == 201
        user_id = r.json()["user_id"]

    # Activate user — mock Redis get_otp to return the correct OTP
    with patch("app.api.v1.endpoints.auth.get_otp", new_callable=AsyncMock, return_value="123456"), \
         patch("app.api.v1.endpoints.auth.delete_otp", new_callable=AsyncMock):
        r = await client.post("/api/v1/auth/verify-otp", json={
            "user_id": user_id,
            "otp": "123456",
        })
        assert r.status_code == 200

    return user_id


async def _login(client, username="testuser", password="pass1234"):
    """Login and return (access_token, refresh_cookie)."""
    with patch("app.api.v1.endpoints.auth.store_refresh_token", new_callable=AsyncMock):
        r = await client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password,
        })
        assert r.status_code == 200
        return r.json()["access_token"], r.cookies.get("refresh_token")


# ── Health tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_liveness(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_readiness_structure(client):
    with patch("app.main.redis_ping", new_callable=AsyncMock, return_value=True):
        r = await client.get("/health/ready")
        data = r.json()
        assert "dependencies" in data
        assert "postgres" in data["dependencies"]
        assert "redis" in data["dependencies"]


# ── Register tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client):
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        })
    assert r.status_code == 201
    assert "user_id" in r.json()
    assert "message" in r.json()


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await _register_and_activate(client)
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "different@example.com",
            "password": "pass1234",
        })
    assert r.status_code == 400
    assert "Username" in r.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await _register_and_activate(client)
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": "differentuser",
            "email": "test@example.com",
            "password": "pass1234",
        })
    assert r.status_code == 400
    assert "Email" in r.json()["detail"]


# ── OTP verification tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_otp_wrong_code(client):
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": "otpuser", "email": "otp@example.com", "password": "pass1234",
        })
        user_id = r.json()["user_id"]

    with patch("app.api.v1.endpoints.auth.get_otp", new_callable=AsyncMock, return_value="999999"):
        r = await client.post("/api/v1/auth/verify-otp", json={"user_id": user_id, "otp": "123456"})
    assert r.status_code == 400
    assert "Invalid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_verify_otp_expired(client):
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        r = await client.post("/api/v1/auth/register", json={
            "username": "expiredotp", "email": "expired@example.com", "password": "pass1234",
        })
        user_id = r.json()["user_id"]

    # Redis returns None = OTP expired
    with patch("app.api.v1.endpoints.auth.get_otp", new_callable=AsyncMock, return_value=None):
        r = await client.post("/api/v1/auth/verify-otp", json={"user_id": user_id, "otp": "123456"})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


# ── Login tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client):
    await _register_and_activate(client)
    token, cookie = await _login(client)
    assert token is not None
    assert len(token) > 20


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await _register_and_activate(client)
    r = await client.post("/api/v1/auth/login", json={"username": "testuser", "password": "wrongpass"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unverified_account(client):
    """Login should fail if account is not OTP-verified."""
    with patch("app.api.v1.endpoints.auth.store_otp", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.auth.send_otp_email_task") as mock_task:
        mock_task.apply_async = MagicMock()
        await client.post("/api/v1/auth/register", json={
            "username": "unverified", "email": "unverified@example.com", "password": "pass1234",
        })

    r = await client.post("/api/v1/auth/login", json={"username": "unverified", "password": "pass1234"})
    assert r.status_code == 403
    assert "verified" in r.json()["detail"].lower()


# ── Protected endpoint tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    await _register_and_activate(client)
    token, _ = await _login(client)
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "testuser"
    assert r.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert r.status_code == 403


# ── Chat endpoint tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_requires_auth(client):
    r = await client.post("/api/v1/chat/message", json={"message": "hello", "session_id": "default"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_chat_automation_datetime(client):
    """Date/time automation should work without calling Groq."""
    await _register_and_activate(client)
    token, _ = await _login(client)
    r = await client.post(
        "/api/v1/chat/message",
        json={"message": "what time is it", "session_id": "default"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["automation_triggered"] is True
    assert data["automation_type"] == "time"


@pytest.mark.asyncio
async def test_chat_history_pagination(client):
    """History endpoint returns pagination fields."""
    await _register_and_activate(client)
    token, _ = await _login(client)

    # Send a message to create history
    with patch("app.api.v1.endpoints.chat.get_groq_response", new_callable=AsyncMock, return_value="Hi!"):
        await client.post(
            "/api/v1/chat/message",
            json={"message": "hello groq", "session_id": "default"},
            headers={"Authorization": f"Bearer {token}"},
        )

    r = await client.get(
        "/api/v1/chat/history?session_id=default&limit=10&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 10
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_chat_sessions_pagination(client):
    """Sessions endpoint returns pagination fields."""
    await _register_and_activate(client)
    token, _ = await _login(client)
    r = await client.get(
        "/api/v1/chat/sessions?limit=5&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert "total" in data
    assert data["limit"] == 5


# ── Password reset tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_always_returns_200(client):
    """Should not reveal whether email exists."""
    r = await client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert r.status_code == 200
    assert "message" in r.json()


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client):
    with patch("app.api.v1.endpoints.auth.get_reset_token_user", new_callable=AsyncMock, return_value=None):
        r = await client.post("/api/v1/auth/reset-password", json={
            "token": "invalidtoken",
            "new_password": "newpass123",
        })
    assert r.status_code == 400


# ── Refresh token tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_no_cookie(client):
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    await _register_and_activate(client)
    token, _ = await _login(client)
    with patch("app.api.v1.endpoints.auth.delete_refresh_token", new_callable=AsyncMock):
        r = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 204
