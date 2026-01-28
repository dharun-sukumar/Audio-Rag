import re

def is_date_question(query: str) -> bool:
    date_keywords = [
        "on", "date", "day", "when", "today", "yesterday",
        "last week", "last month", "feb", "jan", "march",
        "april", "may", "june", "july", "aug", "sep",
        "oct", "nov", "dec"
    ]

    q = query.lower()
    return any(word in q for word in date_keywords) or bool(
        re.search(r"\d{4}-\d{2}-\d{2}", q)
    )
