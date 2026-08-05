"""
app/db/init_db.py
─────────────────
Verify DB connection on startup.
Tables are created by Alembic (entrypoint.sh runs alembic upgrade head).
"""
from __future__ import annotations
import logging

from sqlalchemy import text
from app.db.database import engine

logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")
