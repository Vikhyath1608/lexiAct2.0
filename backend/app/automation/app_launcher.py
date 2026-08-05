"""
app/automation/app_launcher.py
───────────────────────────────
App launcher — executes on the user's LOCAL machine via the LexiAct Local Agent.
The server queues the launch command in Redis.
The local agent running on the user's machine picks it up and opens the app.
"""
import json
import re


# Well-known app names → what to tell the local agent to open
APP_MAP = {
    "notepad": {"windows": "notepad.exe", "mac": "TextEdit", "linux": "gedit"},
    "calculator": {"windows": "calc.exe", "mac": "Calculator", "linux": "gnome-calculator"},
    "chrome": {"windows": "chrome", "mac": "Google Chrome", "linux": "google-chrome"},
    "firefox": {"windows": "firefox", "mac": "Firefox", "linux": "firefox"},
    "edge": {"windows": "msedge", "mac": "Microsoft Edge", "linux": "microsoft-edge"},
    "vs code": {"windows": "code", "mac": "Visual Studio Code", "linux": "code"},
    "vscode": {"windows": "code", "mac": "Visual Studio Code", "linux": "code"},
    "spotify": {"windows": "spotify", "mac": "Spotify", "linux": "spotify"},
    "terminal": {"windows": "cmd.exe", "mac": "Terminal", "linux": "gnome-terminal"},
    "cmd": {"windows": "cmd.exe", "mac": "Terminal", "linux": "bash"},
    "file explorer": {"windows": "explorer.exe", "mac": "Finder", "linux": "nautilus"},
    "finder": {"windows": "explorer.exe", "mac": "Finder", "linux": "nautilus"},
    "paint": {"windows": "mspaint.exe", "mac": "Preview", "linux": "gimp"},
    "word": {"windows": "winword.exe", "mac": "Microsoft Word", "linux": "libreoffice --writer"},
    "excel": {"windows": "excel.exe", "mac": "Microsoft Excel", "linux": "libreoffice --calc"},
    "task manager": {"windows": "taskmgr.exe", "mac": "Activity Monitor", "linux": "gnome-system-monitor"},
}


def _extract_app_name(prompt: str) -> str:
    m = re.search(r'(?:launch|start|open)\s+(.+)', prompt, re.IGNORECASE)
    return m.group(1).strip().lower() if m else ""


def run_open_app(prompt: str) -> str:
    """
    Queue app launch command for local agent execution.
    The LexiAct Local Agent running on the user's machine opens the app.
    """
    app_name = _extract_app_name(prompt)
    if not app_name:
        return "⚠️ Could not identify which app to launch. Try: 'launch chrome' or 'open notepad'"

    # Find matching app in our map
    matched_key = None
    for key in APP_MAP:
        if key in app_name:
            matched_key = key
            break

    if not matched_key:
        # Still queue it — local agent will try its best
        matched_key = app_name

    try:
        import redis
        from app.core.config import settings
        r = redis.from_url(settings.redis_url)
        r.lpush("local_agent:commands", json.dumps({
            "type": "launch_app",
            "app_name": matched_key,
            "app_map": APP_MAP.get(matched_key, {}),
            "raw": app_name,
        }))
        return f"🚀 Launch command for **{matched_key}** sent to your local machine."

    except Exception:
        # Local agent not running — give helpful instructions
        app_display = matched_key or app_name
        return (
            f"🚀 **Launch {app_display}** — the LexiAct Local Agent needs to be running on your machine "
            f"to open apps remotely.\n\n"
            f"Run this in a terminal on your computer:\n"
            f"```\npython local_agent.py\n```"
        )
