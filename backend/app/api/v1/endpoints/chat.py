"""
app/api/v1/endpoints/chat.py
─────────────────────────────
POST   /chat/message          — send message → automation or Groq
GET    /chat/history          — paginated conversation history
DELETE /chat/history          — clear session history
GET    /chat/sessions         — paginated list of session IDs
"""
from __future__ import annotations
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, distinct

from app.core.dependencies import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.models.conversation import Conversation
from app.schemas.chat import (
    ChatRequest, ChatResponse,
    ConversationEntry, HistoryResponse, SessionsResponse,
)
from app.automation.dispatcher import dispatch
from app.services.groq_service import get_groq_response

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = get_logger(__name__)

_email_states: dict[str, dict] = {}


def _ekey(user_id: int, session_id: str) -> str:
    return f"{user_id}:{session_id}"


@router.post("/message", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = body.message.strip()
    session_id = body.session_id
    ekey = _ekey(current_user.id, session_id)

    # ── Email multi-turn state machine ────────────────────────────────────────
    email_ctx = _email_states.get(ekey)
    if email_ctx and email_ctx.get("active"):
        response_text = await _handle_email_followup(ekey, prompt, email_ctx)
        await _save_turn(db, current_user.id, session_id, prompt, response_text)
        return ChatResponse(response=response_text, session_id=session_id,
                            automation_triggered=True, automation_type="email")

    # ── Email trigger ─────────────────────────────────────────────────────────
    if any(prompt.lower().startswith(t) for t in ("send email to", "email to")):
        response_text = await _start_email_workflow(ekey, prompt)
        await _save_turn(db, current_user.id, session_id, prompt, response_text)
        return ChatResponse(response=response_text, session_id=session_id,
                            automation_triggered=True, automation_type="email")

    # ── Automation dispatcher ─────────────────────────────────────────────────
    result = dispatch(prompt, current_user.id)
    if result.matched and result.response:
        await _save_turn(db, current_user.id, session_id, prompt, result.response)
        logger.info("automation_triggered", type=result.automation_type, user_id=current_user.id)
        return ChatResponse(
            response=result.response,
            session_id=session_id,
            automation_triggered=True,
            automation_type=result.automation_type,
        )

    # ── Groq AI fallback ──────────────────────────────────────────────────────
    history = await _get_history_for_context(db, current_user.id, session_id)
    try:
        ai_response = await get_groq_response(prompt, history)
    except asyncio.TimeoutError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "AI response timed out. Please try again.")
    except Exception as e:
        logger.error("groq_error", error=str(e), user_id=current_user.id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI service temporarily unavailable.")

    await _save_turn(db, current_user.id, session_id, prompt, ai_response)
    return ChatResponse(response=ai_response, session_id=session_id)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    session_id: str = "default",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Total count
    total_result = await db.execute(
        select(func.count()).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
        )
    )
    total = total_result.scalar_one()

    # Paginated results
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id, Conversation.session_id == session_id)
        .order_by(Conversation.created_at)
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()

    return HistoryResponse(
        session_id=session_id,
        messages=[ConversationEntry.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    session_id: str = "default",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        delete(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
        )
    )


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Total distinct sessions
    total_result = await db.execute(
        select(func.count(distinct(Conversation.session_id)))
        .where(Conversation.user_id == current_user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(distinct(Conversation.session_id))
        .where(Conversation.user_id == current_user.id)
        .limit(limit)
        .offset(offset)
    )
    sessions = [row[0] for row in result.all()]

    return SessionsResponse(sessions=sessions, total=total, limit=limit, offset=offset)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _save_turn(db, user_id, session_id, user_msg, assistant_msg):
    db.add(Conversation(user_id=user_id, session_id=session_id, role="user", content=user_msg))
    db.add(Conversation(user_id=user_id, session_id=session_id, role="assistant", content=assistant_msg))


async def _get_history_for_context(db, user_id, session_id) -> list[dict]:
    from app.core.config import settings
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.session_id == session_id)
        .order_by(Conversation.created_at.desc())
        .limit(settings.conversation_context_window)
    )
    rows = result.scalars().all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


async def _start_email_workflow(ekey: str, prompt: str) -> str:
    from app.automation.contacts import get_contacts
    from app.services.groq_service import generate_email_draft
    contacts = get_contacts()
    recipient_name = recipient_email = ""
    for name, email_addr in contacts.items():
        if name.lower() in prompt.lower():
            recipient_name, recipient_email = name, email_addr
            break
    if not recipient_email:
        return "⚠️ Recipient not found in contacts. Add them with 'add contact <name> <email>'"
    draft = await generate_email_draft(prompt, recipient_name, recipient_email)
    _email_states[ekey] = {
        "active": True, "expecting_change": False,
        "subject": draft["subject"], "body": draft["body"],
        "to_email": recipient_email, "recipient_name": recipient_name,
    }
    return (
        f"✉️ Draft ready:\n\n**To:** {recipient_name} ({recipient_email})\n"
        f"**Subject:** {draft['subject']}\n\n{draft['body']}\n\n"
        f"Reply **yes** to send, **no** to cancel, or **change** to edit."
    )


async def _handle_email_followup(ekey: str, prompt: str, ctx: dict) -> str:
    from app.services.groq_service import generate_email_draft
    p = prompt.strip().lower()
    if ctx.get("expecting_change"):
        ctx["expecting_change"] = False
        draft = await generate_email_draft(prompt, ctx["recipient_name"], ctx["to_email"])
        ctx["subject"], ctx["body"] = draft["subject"], draft["body"]
        return (
            f"🔁 Updated:\n\n**Subject:** {ctx['subject']}\n\n{ctx['body']}\n\n"
            f"Reply **yes** / **no** / **change**."
        )
    if p == "yes":
        from app.workers.celery_app import send_email_task
        send_email_task.apply_async(args=[ctx["to_email"], ctx["subject"], ctx["body"]])
        _email_states.pop(ekey, None)
        return f"✅ Email queued to {ctx['to_email']}"
    elif p == "no":
        _email_states.pop(ekey, None)
        return "❌ Email cancelled."
    elif p == "change":
        ctx["expecting_change"] = True
        return "✏️ What would you like to change?"
    return "Please reply **yes**, **no**, or **change**."
