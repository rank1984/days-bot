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
    reason = row.get("reason", "מומנטום")
    return (
        f"🚀 <b>DAYS-BOT — התראת מסחר</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>מניה:</b>     {row['ticker']}\n"
        f"💰 <b>מחיר:</b>     ${row['price']:.2f}\n"
        f"📈 <b>גאפ:</b>      +{row['gap_pct']:.1f}%\n"
        f"📊 <b>נפח:</b>      {row['vol_ratio']:.1f}x ממוצע\n"
        f"🏭 <b>תעשייה:</b>   {row.get('industry', 'לא ידוע')}\n"
        f"⭐ <b>ציון:</b>     {row['score']:.0f} / 100\n"
        f"💡 <b>סיבה:</b>     {reason}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ לא המלצת השקעה — לצרכי מידע בלבד"
    )


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    return (
        f"🤖 <b>DAYS-BOT — דוח יומי</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>תאריך:</b> {date}\n"
        f"🔍 <b>מניות שנסרקו:</b> {universe_size}\n"
        f"😴 <b>תוצאה:</b> לא נמצאו מועמדות\n"
        f"     שעברו את הסף היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ הסריקה הבאה מחר בפתיחה"
    )
