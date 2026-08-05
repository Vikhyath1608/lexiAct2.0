"""
app/automation/dispatcher.py
─────────────────────────────
Strategy-pattern automation dispatcher.
Each handler registered with @register(name, keywords, patterns, priority).
dispatch() iterates registry in priority order, returns on first match.
Adding new automation = one decorated function, zero changes elsewhere.

Local-machine commands (volume, app launch) are queued in Redis and picked
up by the LexiAct Local Agent running on the user's machine.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class AutomationResult:
    matched: bool = False
    response: str = ""
    automation_type: str = ""


@dataclass
class _Handler:
    name: str
    keywords: list
    patterns: list
    fn: Callable
    priority: int = 0


_registry: list[_Handler] = []


def register(name: str, keywords=None, patterns=None, priority: int = 0):
    """Decorator to register an automation handler."""
    def decorator(fn: Callable):
        _registry.append(_Handler(
            name=name,
            keywords=keywords or [],
            patterns=patterns or [],
            fn=fn,
            priority=priority,
        ))
        _registry.sort(key=lambda h: -h.priority)
        return fn
    return decorator


def dispatch(prompt: str, user_id: int = 0) -> AutomationResult:
    """Route prompt to first matching handler. Returns unmatched if none found."""
    p = prompt.lower().strip()
    for handler in _registry:
        for pat in handler.patterns:
            if re.search(pat, p):
                response = handler.fn(prompt, user_id)
                if response:
                    return AutomationResult(True, response, handler.name)
        for kw in handler.keywords:
            if kw in p:
                response = handler.fn(prompt, user_id)
                if response:
                    return AutomationResult(True, response, handler.name)
    return AutomationResult(matched=False)


# ── Handlers ──────────────────────────────────────────────────────────────────

@register("date_time", patterns=[r'\bdate\b'], priority=5)
def handle_date(prompt: str, user_id: int) -> str:
    from app.automation.date_time import announce_date_time
    return announce_date_time("date")


@register("time", patterns=[r'(?<!\w)time(?!\w)(?!r)'], priority=5)
def handle_time(prompt: str, user_id: int) -> str:
    if re.search(r'\btimer\b', prompt.lower()):
        return ""
    from app.automation.date_time import announce_date_time
    return announce_date_time("time")


@register("timer", patterns=[r'\btimer\b'], priority=10)
def handle_timer(prompt: str, user_id: int) -> str:
    from app.automation.timer import parse_seconds
    from app.workers.celery_app import run_timer_task
    seconds = parse_seconds(prompt)
    run_timer_task.apply_async(args=[seconds, user_id, "Timer"])
    mins, secs = divmod(seconds, 60)
    label = f"{mins}m {secs}s" if mins else f"{secs}s"
    return (
        f"⏲️ Timer set for **{label}**. "
        f"I'll send you an email notification when it's done!"
    )


@register("alarm", keywords=["alarm"], priority=10)
def handle_alarm(prompt: str, user_id: int) -> str:
    from app.automation.alarm import calc_sleep_seconds, parse_alarm_display
    from app.workers.celery_app import run_alarm_task
    sleep_secs = calc_sleep_seconds(prompt)
    display = parse_alarm_display(prompt)
    run_alarm_task.apply_async(args=[sleep_secs, user_id, display])
    return f"⏰ Alarm set for **{display}**. I'll send you an email when it fires!"


@register("volume", keywords=["volume"], priority=5)
def handle_volume(prompt: str, user_id: int) -> str:
    from app.automation.volume import volume_control
    return volume_control(prompt.lower())


@register("launch_app", keywords=["launch", "open", "start"], priority=3)
def handle_launch(prompt: str, user_id: int) -> str:
    # Skip if it's "open the" (file open, not app)
    if "open the" in prompt.lower():
        return ""
    from app.automation.app_launcher import run_open_app
    return run_open_app(prompt.lower())


@register("news", keywords=["news"], priority=5)
def handle_news(prompt: str, user_id: int) -> str:
    from app.automation.news import search_google_news
    return search_google_news(prompt.lower())


@register("contacts", keywords=["contact", "add contact", "change contact", "change email"], priority=6)
def handle_contacts(prompt: str, user_id: int) -> str:
    from app.automation.contacts import handle_contact_command
    return handle_contact_command(prompt.lower())
