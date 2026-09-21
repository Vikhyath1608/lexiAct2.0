"""
app/services/gemini_service.py
───────────────────────────────
Google Gemini AI service.
Model: gemini-2.0-flash (free tier — 1500 requests/day)
Features:
  - Multi-turn conversation with history
  - asyncio.wait_for() timeout
  - tenacity retry with exponential backoff
  - Email draft generation
"""
from __future__ import annotations
import asyncio
import json
from typing import List, Optional

import google.generativeai as genai
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


def _configure():
    """Configure Gemini with API key."""
    genai.configure(api_key=settings.gemini_api_key)


def _get_model() -> genai.GenerativeModel:
    _configure()
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            max_output_tokens=settings.gemini_max_tokens,
            temperature=settings.gemini_temperature,
        ),
    )


def _to_gemini_history(history: List[dict]) -> list:
    """Convert standard role/content history to Gemini format."""
    result = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        result.append({"role": role, "parts": [msg["content"]]})
    return result


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _call_gemini_chat(model: genai.GenerativeModel, history: list, message: str) -> str:
    """Run Gemini chat in thread executor — SDK is synchronous."""
    loop = asyncio.get_event_loop()
    def _run():
        chat = model.start_chat(history=history)
        response = chat.send_message(message)
        return response.text.strip()
    return await loop.run_in_executor(None, _run)


async def get_gemini_response(
    user_message: str,
    history: Optional[List[dict]] = None,
) -> str:
    """
    Send a message to Gemini with optional conversation history.
    Raises asyncio.TimeoutError if response takes too long.
    """
    model = _get_model()
    context = history[-(settings.gemini_context_window):] if history else []
    gemini_history = _to_gemini_history(context)

    try:
        return await asyncio.wait_for(
            _call_gemini_chat(model, gemini_history, user_message),
            timeout=settings.gemini_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("Gemini API timeout", timeout=settings.gemini_timeout_seconds)
        raise
    except Exception as e:
        logger.error("Gemini API error", error=str(e))
        raise


async def generate_email_draft(
    instruction: str,
    recipient_name: str,
    recipient_email: str,
) -> dict:
    """Generate email subject + body via Gemini. Returns {"subject":..., "body":...}"""
    model = _get_model()
    prompt = (
        f'Generate a professional email based on this instruction: "{instruction}"\n'
        f"Recipient name: {recipient_name}, email: {recipient_email}\n"
        f"Respond ONLY with a JSON object — no markdown, no backticks:\n"
        f'{{"subject": "...", "body": "..."}}'
    )

    loop = asyncio.get_event_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: model.generate_content(prompt)),
            timeout=settings.gemini_timeout_seconds,
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.error("Email draft generation failed", error=str(e))
        raise