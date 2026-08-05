"""
app/automation/volume.py
─────────────────────────
Volume control — executes on the user's LOCAL machine via the LexiAct Local Agent.
The server queues the command in Redis. The local agent polls Redis and runs it.
Falls back to a descriptive message if local agent is not running.
"""
import re
import json
import asyncio


def _parse_volume_command(prompt: str) -> dict:
    """Parse the volume command into a structured action."""
    if "mute" in prompt:
        return {"action": "mute"}
    if "unmute" in prompt:
        return {"action": "unmute"}
    if any(w in prompt for w in ["up", "increase", "raise"]):
        return {"action": "increase", "amount": 10}
    if any(w in prompt for w in ["down", "decrease", "lower"]):
        return {"action": "decrease", "amount": 10}
    m = re.search(r'(\d+)', prompt)
    if m:
        return {"action": "set", "level": int(m.group(1))}
    return {"action": "increase", "amount": 10}


def volume_control(prompt: str) -> str:
    """
    Queue volume command for local agent execution.
    The LexiAct Local Agent running on the user's machine picks this up and
    executes it using pycaw (Windows) or pactl/amixer (Linux/Mac).
    """
    command = _parse_volume_command(prompt)

    # Queue command in Redis for local agent to pick up
    try:
        import redis
        from app.core.config import settings
        r = redis.from_url(settings.redis_url)
        r.lpush("local_agent:commands", json.dumps({
            "type": "volume",
            **command,
        }))

        action = command["action"]
        if action == "mute":
            return "🔇 Volume mute command sent to your local machine."
        elif action == "unmute":
            return "🔊 Volume unmute command sent to your local machine."
        elif action == "increase":
            return f"🔊 Volume increase command sent to your local machine."
        elif action == "decrease":
            return f"🔉 Volume decrease command sent to your local machine."
        elif action == "set":
            return f"🔊 Volume set to {command['level']}% command sent to your local machine."

    except Exception:
        # Local agent not running or Redis not reachable from context
        action = command.get("action", "change")
        if action == "mute":
            return "🔇 **Volume Mute** — run the LexiAct Local Agent on your machine to control volume remotely."
        elif action == "increase":
            return "🔊 **Volume Up** — run the LexiAct Local Agent on your machine to control volume remotely."
        elif action == "decrease":
            return "🔉 **Volume Down** — run the LexiAct Local Agent on your machine to control volume remotely."
        return "🔊 **Volume control** — run the LexiAct Local Agent on your machine to control volume remotely."

    return "🔊 Volume command queued."
