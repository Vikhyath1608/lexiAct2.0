"""
app/services/groq_service.py
─────────────────────────────
Groq LLaMA 3.3-70B chat completion with:
- Sliding conversation context window
- asyncio.wait_for() timeout enforcement
- tenacity exponential backoff retry on 429/5xx
- AI email draft generation
"""
from __future__ import annotations
import asyncio
import json
from typing import List, Optional

from groq import AsyncGroq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are LexiAct, an intelligent AI personal assistant.
You are helpful, concise, and friendly. Use markdown when it helps clarity.
When automation commands are detected (timers, alarms, email), acknowledge them clearly."""


def _get_client() -> AsyncGroq:
    return AsyncGroq(api_key=settings.groq_api_key)


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _call_groq(messages: list[dict]) -> str:
    """Groq API call with tenacity retry on transient failures."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=settings.groq_max_tokens,
        temperature=settings.groq_temperature,
        messages=messages,
    )
    return response.choices[0].message.content.strip()


async def get_groq_response(
    user_message: str,
    history: Optional[List[dict]] = None,
) -> str:
    """
    Send message to Groq with context history.
    Wrapped in asyncio.wait_for() — raises TimeoutError after groq_timeout_seconds.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-(settings.conversation_context_window):])
    messages.append({"role": "user", "content": user_message})

    try:
        return await asyncio.wait_for(
            _call_groq(messages),
            timeout=settings.groq_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("Groq API timeout", timeout=settings.groq_timeout_seconds)
        raise
    except Exception as e:
        logger.error("Groq API error", error=str(e))
        raise


async def generate_email_draft(
    instruction: str,
    recipient_name: str,
    recipient_email: str,
) -> dict:
    """Generate email subject + body via Groq. Returns parsed JSON dict."""
    prompt = (
        f'Generate a professional email based on this instruction: "{instruction}"\n'
        f"Recipient: {recipient_name} ({recipient_email})\n"
        f'Respond ONLY with a JSON object (no markdown): {{"subject": "...", "body": "..."}}'
    )
    client = _get_client()
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=512,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}],
        ),
        timeout=settings.groq_timeout_seconds,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
