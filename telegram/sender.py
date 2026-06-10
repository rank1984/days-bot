import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def _grade_emoji(grade: str) -> str:
    return {"A+": "🔥", "A": "✅", "B": "👀", "C": "💤"}.get(grade, "—")


def _float_label(f: int) -> str:
    if f <= 0:          return "❓"
    if f < 20_000_000:  return f"🟢 {f/1_000_000:.1f}M"
    if f < 50_000_000:  return f"🟡 {f/1_000_000:.1f}M"
    if f < 100_000_000: ret
