import re
def parse_seconds(prompt: str) -> int:
    total = 0
    for pattern, mult in [(r'(\d+)\s*hour', 3600), (r'(\d+)\s*min', 60), (r'(\d+)\s*sec', 1)]:
        m = re.search(pattern, prompt, re.IGNORECASE)
        if m:
            total += int(m.group(1)) * mult
    return total or 60
