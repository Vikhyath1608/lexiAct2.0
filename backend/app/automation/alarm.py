import re
from datetime import datetime
def calc_sleep_seconds(prompt: str) -> float:
    m = re.search(r'(\d{1,2})[:\.]?(\d{0,2})\s*(am|pm)?', prompt, re.IGNORECASE)
    if not m: return 0
    hour, minute = int(m.group(1)), int(m.group(2)) if m.group(2) else 0
    period = m.group(3)
    if period:
        if period.lower() == "pm" and hour != 12: hour += 12
        elif period.lower() == "am" and hour == 12: hour = 0
    now = datetime.now()
    alarm = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    diff = (alarm - now).total_seconds()
    return diff if diff > 0 else diff + 86400

def parse_alarm_display(prompt: str) -> str:
    m = re.search(r'(\d{1,2})[:\.]?(\d{0,2})\s*(am|pm)?', prompt, re.IGNORECASE)
    if not m: return "unknown"
    return f"{m.group(1)}:{(m.group(2) or '00').zfill(2)} {(m.group(3) or '').upper()}".strip()
