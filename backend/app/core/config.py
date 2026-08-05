"""
app/core/config.py
──────────────────
Single source of truth for all configuration.
Every value read from environment / .env — zero hardcoded secrets.
"""
from __future__ import annotations
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "LexiAct"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15          # short-lived
    refresh_token_expire_days: int = 7             # long-lived

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://lexiact:lexiact_pass@localhost:5432/lexiact_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    rate_limit_requests: int = 60
    rate_limit_window: int = 60

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── OTP ───────────────────────────────────────────────────────────────────
    otp_expire_seconds: int = 600          # 10 minutes
    password_reset_expire_seconds: int = 900  # 15 minutes

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 1024
    groq_temperature: float = 0.7
    conversation_context_window: int = 20
    groq_timeout_seconds: float = 30.0

    # ── Email ─────────────────────────────────────────────────────────────────
    from_email: str = ""
    from_password: str = ""
    your_name: str = "LexiAct"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # ── GitHub OAuth ──────────────────────────────────────────────────────────
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    # ── Frontend ──────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Automation ────────────────────────────────────────────────────────────
    app_paths_file: str = "./app/automation/app_paths.json"

    # ── Browser agent ─────────────────────────────────────────────────────────
    lam_headless: bool = True
    lam_max_steps: int = 60
    lam_human_timeout: int = 600
    agent_timeout_seconds: float = 60.0

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:80",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
