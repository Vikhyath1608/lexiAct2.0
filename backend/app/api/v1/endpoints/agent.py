"""
app/api/v1/endpoints/agent.py
──────────────────────────────
POST   /agent/run            — start browser agent (SSE stream)
POST   /agent/input/{id}     — human input to waiting agent
GET    /agent/status/{id}    — session status
DELETE /agent/session/{id}   — terminate session
"""
from __future__ import annotations
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.agent import HumanInputRequest, RunRequest, AgentStatusResponse
from app.services import agent_service

router = APIRouter(prefix="/agent", tags=["Browser Agent"])
logger = get_logger(__name__)


@router.post("/run")
async def run_agent(
    body: RunRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        session_id, agent = await agent_service.start_agent_session(
            website=body.website,
            goal=body.goal,
            session_id=body.session_id,
        )
    except ImportError:
        raise HTTPException(503, "Browser agent requires: playwright install chromium")

    return StreamingResponse(
        _stream(agent, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-ID": session_id,
        },
    )


@router.post("/input/{session_id}")
async def provide_input(
    session_id: str,
    body: HumanInputRequest,
    current_user: User = Depends(get_current_user),
):
    agent = await agent_service.get_agent(session_id)
    if not agent:
        raise HTTPException(404, f"Session '{session_id}' not found")
    if agent.state.status != "waiting_for_human":
        raise HTTPException(400, f"Session not waiting for input")
    agent.provide_human_answer(body.answer)
    return {"ok": True, "session_id": session_id}


@router.get("/status/{session_id}", response_model=AgentStatusResponse)
async def get_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    agent = await agent_service.get_agent(session_id)
    if not agent:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return AgentStatusResponse(
        session_id=session_id,
        status=agent.state.status,
        current_step=agent.state.current_step,
        total_plan_steps=len(agent.state.plan),
        pending_question=agent.state.pending_human_question,
        visited_urls=agent.state.visited_urls,
        extracted_data=agent.state.extracted_data,
    )


@router.delete("/session/{session_id}", status_code=204)
async def terminate(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    await agent_service.remove_agent(session_id)


async def _stream(agent, session_id: str):
    try:
        async for event in asyncio.wait_for(
            _generate(agent),
            timeout=settings.agent_timeout_seconds,
        ):
            yield event
    except asyncio.TimeoutError:
        yield f'data: {{"event":"error","message":"Agent timed out"}}\n\n'.encode()
    finally:
        await agent_service.remove_agent(session_id)


async def _generate(agent):
    async for event in agent.run():
        payload = event.model_dump()
        yield f"data: {json.dumps(payload)}\n\n".encode()
        await asyncio.sleep(0)
        if event.event.value in ("done", "error"):
            break
    yield b'data: {"event":"stream_end"}\n\n'
