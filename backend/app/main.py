"""
app/main.py
───────────
FastAPI application factory.
- Prometheus metrics via prometheus-fastapi-instrumentator v6
- Structured JSON logging via structlog
- Rate limiting + request logging middleware
- Real health check pinging all dependencies
"""
from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.core.redis import close_redis, get_redis, redis_ping
from app.db.init_db import init_db
from app.api.v1 import api_router
from app.services.agent_service import active_session_count

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.debug)
    await init_db()
    await get_redis()
    logger.info("startup_complete", app=settings.app_name, version=settings.app_version)
    yield
    await close_redis()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "LexiAct — AI-Powered Personal Assistant API. "
            "JWT auth, refresh tokens, OTP, Google/GitHub OAuth, "
            "Groq LLM, Celery background jobs, Strategy pattern automation."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Prometheus metrics ────────────────────────────────────────────────────
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/health", "/health/ready", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except Exception as e:
        logger.warning("prometheus_setup_failed", error=str(e))

    # ── API routes ────────────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Health: liveness ──────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health_liveness():
        """Is the process alive?"""
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    # ── Health: readiness ─────────────────────────────────────────────────────
    @app.get("/health/ready", tags=["Health"])
    async def health_readiness():
        """
        Are all dependencies reachable?
        Returns 503 if any critical dependency is down.
        """
        import asyncio
        from sqlalchemy import text
        from app.db.database import engine
        from fastapi.responses import JSONResponse

        results = {}

        # PostgreSQL
        try:
            async with engine.connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=3.0)
            results["postgres"] = "ok"
        except Exception as e:
            results["postgres"] = f"error: {str(e)[:80]}"

        # Redis
        try:
            results["redis"] = "ok" if await redis_ping() else "error: ping failed"
        except Exception as e:
            results["redis"] = f"error: {str(e)[:80]}"

        # Groq API key check (lightweight)
        results["groq"] = "ok" if settings.groq_api_key else "warning: GROQ_API_KEY not set"

        has_error = any(v.startswith("error") for v in results.values())
        return JSONResponse(
            status_code=503 if has_error else 200,
            content={
                "status": "degraded" if has_error else "ok",
                "dependencies": results,
                "active_agent_sessions": active_session_count(),
            },
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
