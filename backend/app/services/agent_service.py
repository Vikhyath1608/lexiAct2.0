"""app/services/agent_service.py — Browser agent session registry."""
from __future__ import annotations
import asyncio
import uuid
from typing import Dict

_sessions: Dict[str, object] = {}
_lock = asyncio.Lock()


async def start_agent_session(website: str, goal: str, session_id: str | None = None):
    try:
        from lam.agent.loop import AgentLoop
        from lam.models.schemas import RunRequest
        from app.core.config import settings
    except ImportError:
        raise ImportError("Browser agent requires lam package and playwright install chromium")

    sid = session_id or str(uuid.uuid4())
    request = RunRequest(website=website, goal=goal, session_id=sid)
    agent = AgentLoop(request, sid, headless=settings.lam_headless)
    async with _lock:
        _sessions[sid] = agent
    return sid, agent


async def get_agent(session_id: str):
    async with _lock:
        return _sessions.get(session_id)


async def remove_agent(session_id: str) -> None:
    async with _lock:
        agent = _sessions.pop(session_id, None)
    if agent:
        try:
            await agent.driver.stop()
        except Exception:
            pass


def active_session_count() -> int:
    return len(_sessions)
