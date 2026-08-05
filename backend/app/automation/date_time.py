from datetime import datetime
def announce_date_time(query_type: str) -> str:
    now = datetime.now()
    if query_type == "date":
        return f"Today is {now.strftime('%B %d, %Y, %A')}"
    return f"The current time is {now.strftime('%I:%M %p')}"
