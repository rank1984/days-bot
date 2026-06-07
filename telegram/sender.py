import requests

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
        print(f"[Telegram] Failed to send message: {e}")
        return False


def format_alert(row: dict) -> str:
    reason = row.get("reason", "Momentum Play")
    return (
        f"🚀 <b>DAYS-BOT</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Ticker:   <b>{row['ticker']}</b>\n"
        f"Price:    ${row['price']:.2f}\n"
        f"Gap:      +{row['gap_pct']:.1f}%\n"
        f"Volume:   {row['vol_ratio']:.1f}x avg\n"
        f"Industry: {row.get('industry', 'N/A')}\n"
        f"Score:    <b>{row['score']:.0f}</b>\n"
        f"Reason:   {reason}\n"
        f"━━━━━━━━━━━━━━━"
    )
