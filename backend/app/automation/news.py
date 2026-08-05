"""
app/automation/news.py
────────────────────────
Returns a clickable Google News URL in the chat response.
The user clicks the link in their browser — server never tries to open a browser.
"""
import re
import urllib.parse


def search_google_news(prompt: str) -> str:
    m = re.search(r'news(?:\s+about)?\s+(.*)', prompt, re.IGNORECASE)
    query = m.group(1).strip() if m else ""
    if query:
        url = f"https://news.google.com/search?q={urllib.parse.quote(query)}"
        return f"📰 Here's the latest news about **{query}**:\n[Open Google News → {query}]({url})"
    return "📰 Here's Google News: [Open Google News](https://news.google.com)"
