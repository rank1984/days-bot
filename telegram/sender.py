"""
telegram/sender.py — שדרוגים #9 + #10
---------------------------------------
#9:  הודעה משודרגת עם Float, News, Leader, Risk
#10: Watchlist בבוקר + Final Alerts בפתיחה
"""

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
        print(f"[Telegram] Error: {e}")
        return False


def _float_label(f: int) -> str:
    if f == 0:            return "לא ידוע"
    if f < 5_000_000:     return f"{f/1_000_000:.1f}M 🔥"
    if f < 10_000_000:    return f"{f/1_000_000:.1f}M ✅"
    if f < 20_000_000:    return f"{f/1_000_000:.1f}M"
    return f"{f/1_000_000:.0f}M ⚠️"


def _risk_label(score: float, gap: float, float_shares: int) -> str:
    """הערכת סיכון פשוטה."""
    risk = 0
    if gap > 30:           risk += 1
    if float_shares < 3_000_000 and float_shares > 0: risk += 1
    if score < 70:         risk += 1

    if risk == 0:   return "🟢 נמוך"
    if risk == 1:   return "🟡 בינוני"
    return          "🔴 גבוה"


def format_alert(row: dict) -> str:
    """שדרוג #9 — הודעת התראה מלאה."""
    float_label   = _float_label(int(row.get("float", 0)))
    catalyst      = row.get("catalyst", "—")
    is_leader     = row.get("is_leader", False)
    leader_ticker = row.get("leader", "")
    risk          = _risk_label(row.get("score", 0), row.get("gap_pct", 0), int(row.get("float", 0)))
    dollar_vol    = row.get("dollar_volume", 0)
    dvol_str      = f"${dollar_vol/1_000_000:.1f}M" if dollar_vol >= 1_000_000 else f"${dollar_vol:,.0f}"

    leader_line = ""
    if is_leader:
        leader_line = "👑 <b>Sector Leader</b>\n"
    elif leader_ticker:
        leader_line = f"🔗 <b>Sympathy:</b> {leader_ticker}\n"

    return (
        f"🚀 <b>DAYS-BOT — התראת מסחר</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>מניה:</b>      {row['ticker']}\n"
        f"💰 <b>מחיר:</b>      ${row['price']:.2f}\n"
        f"📈 <b>גאפ:</b>       +{row['gap_pct']:.1f}%\n"
        f"📊 <b>RVOL:</b>      {row.get('vol_ratio', 0):.1f}x\n"
        f"💵 <b>$ Volume:</b>  {dvol_str}\n"
        f"🏷️ <b>Float:</b>     {float_label}\n"
        f"📰 <b>Catalyst:</b>  {catalyst}\n"
        f"{leader_line}"
        f"🏭 <b>תעשייה:</b>   {row.get('industry', 'לא ידוע')}\n"
        f"⭐ <b>ציון:</b>      {row.get('score', 0):.0f} / 100\n"
        f"⚠️ <b>סיכון:</b>    {risk}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )


def format_watchlist(candidates: list[dict], date: str) -> str:
    """שדרוג #10 — Morning Watchlist (Phase 1)."""
    lines = [
        f"👀 <b>DAYS-BOT — Watchlist בוקר</b>",
        f"📅 {date}",
        f"━━━━━━━━━━━━━━━━━━",
    ]
    for i, row in enumerate(candidates[:15], 1):
        float_m = int(row.get("float", 0)) / 1_000_000
        float_s = f"{float_m:.1f}M" if float_m > 0 else "?"
        lines.append(
            f"{i}. <b>{row['ticker']}</b>  "
            f"+{row['gap_pct']:.1f}%  "
            f"RVOL:{row.get('vol_ratio', 0):.1f}x  "
            f"Float:{float_s}  "
            f"⭐{row.get('score', 0):.0f}"
        )
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏰ Final Alerts בפתיחה")
    return "\n".join(lines)


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
