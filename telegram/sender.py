"""
telegram/sender.py
------------------
Watchlist בוקר + Final Alerts עם דירוג AI
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
    if f == 0:               return "?"
    if f < 5_000_000:        return f"{f/1_000_000:.1f}M 🔥"
    if f < 10_000_000:       return f"{f/1_000_000:.1f}M ✅"
    if f < 20_000_000:       return f"{f/1_000_000:.1f}M"
    return                          f"{f/1_000_000:.0f}M ⚠️"


def _grade_emoji(grade: str) -> str:
    return {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴"}.get(grade, "⚪")


def _risk_label(score: float, gap: float, float_shares: int) -> str:
    risk = 0
    if gap > 30:                                      risk += 1
    if 0 < float_shares < 3_000_000:                 risk += 1
    if score < 70:                                    risk += 1
    return ["🟢 נמוך", "🟡 בינוני", "🔴 גבוה"][min(risk, 2)]


def format_watchlist(candidates: list[dict], date: str) -> str:
    """Watchlist בוקר — תמציתי וברור."""
    lines = [
        f"👀 <b>DAYS-BOT — Watchlist בוקר</b>",
        f"📅 {date}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    for i, row in enumerate(candidates[:15], 1):
        ticker  = row["ticker"]
        gap     = row.get("gap_pct", 0)
        rvol    = row.get("vol_ratio", 0)
        score   = row.get("score", 0)
        grade   = row.get("ai_grade", "?")
        float_s = _float_label(int(row.get("float", 0)))
        emoji   = _grade_emoji(grade)
        catalyst = row.get("catalyst", "")
        cat_str  = f"  📰{catalyst}" if catalyst and catalyst != "—" else ""

        lines.append(
            f"{i}. <b>{ticker}</b>  +{gap:.1f}%  "
            f"RVOL:{rvol:.1f}x  Float:{float_s}  "
            f"{emoji}AI:{grade}  ⭐{score:.0f}"
            f"{cat_str}"
        )

    lines += [
        f"━━━━━━━━━━━━━━━━━━",
        f"⏰ Final Alerts בפתיחה",
    ]
    return "\n".join(lines)


def format_alert(row: dict) -> str:
    """התראת מסחר מלאה לפתיחה."""
    ticker     = row["ticker"]
    price      = row.get("price", 0)
    gap        = row.get("gap_pct", 0)
    rvol       = row.get("vol_ratio", 0)
    score      = row.get("score", 0)
    grade      = row.get("ai_grade", "?")
    ai_reason  = row.get("ai_reason", "")
    catalyst   = row.get("catalyst", "—")
    float_s    = _float_label(int(row.get("float", 0)))
    risk       = _risk_label(score, gap, int(row.get("float", 0)))
    dvol       = row.get("dollar_volume", 0)
    dvol_str   = f"${dvol/1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol:,.0f}"
    grade_e    = _grade_emoji(grade)

    is_leader     = row.get("is_leader", False)
    leader_ticker = row.get("leader", "")
    if is_leader:
        leader_line = "👑 <b>Sector Leader</b>\n"
    elif leader_ticker:
        leader_line = f"🔗 <b>Sympathy:</b> {leader_ticker}\n"
    else:
        leader_line = ""

    ai_line = ""
    if grade != "?" and ai_reason:
        ai_line = f"{grade_e} <b>AI:</b>       {grade} — {ai_reason}\n"
    elif grade != "?":
        ai_line = f"{grade_e} <b>AI:</b>       {grade}\n"

    return (
        f"🚀 <b>DAYS-BOT — התראת מסחר</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>מניה:</b>      {ticker}\n"
        f"💰 <b>מחיר:</b>      ${price:.2f}\n"
        f"📈 <b>גאפ:</b>       +{gap:.1f}%\n"
        f"📊 <b>RVOL:</b>      {rvol:.1f}x\n"
        f"💵 <b>$ Volume:</b>  {dvol_str}\n"
        f"🏷️ <b>Float:</b>     {float_s}\n"
        f"📰 <b>Catalyst:</b>  {catalyst}\n"
        f"{leader_line}"
        f"{ai_line}"
        f"⭐ <b>ציון:</b>      {score:.0f}/100\n"
        f"⚠️ <b>סיכון:</b>    {risk}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    return (
        f"🤖 <b>DAYS-BOT — דוח יומי</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>תאריך:</b> {date}\n"
        f"🔍 <b>מניות שנסרקו:</b> {universe_size}\n"
        f"😴 <b>תוצאה:</b> לא נמצאו מועמדות שעברו את הסף היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ הסריקה הבאה מחר בפתיחה"
    )
