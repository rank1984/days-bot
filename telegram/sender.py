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
    if f < 100_000_000: return f"🟠 {f/1_000_000:.0f}M"
    return                     f"🔴 {f/1_000_000:.0f}M"


def _dvol_str(dv: float) -> str:
    if dv >= 1_000_000: return f"${dv/1_000_000:.1f}M"
    if dv >= 1_000:     return f"${dv/1_000:.0f}K"
    return f"${dv:.0f}"


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:    """
    הודעה ראשית — רשימה לפני פתיחה.
    מציגה TOP 5 עם כל הנתונים הרלוונטיים.
    """
    now_et   = datetime.now(ET)
    time_str = now_et.strftime("%H:%M ET")

    lines = [
        f"⚠️ <b>ציון נמוך — בדוק בזהירות</b>" if low_quality else "",
        f"📅 {date}  |  🕐 {time_str}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    for i, r in enumerate(candidates[:5], 1):
        grade    = r.get("grade", "B")
        emoji    = _grade_emoji(grade)
        catalyst = r.get("catalyst", "—")
        pm_rvol  = r.get("pm_rvol", r.get("vol_ratio", 0))
        pm_vol   = r.get("pm_volume", 0)
        dvol     = r.get("dollar_volume", 0)

        lines.append(
            f"\n{emoji} <b>{i}. {r['ticker']}</b>  "
            f"${r['price']:.2f}  "
            f"+{r['gap_pct']:.1f}%  "
            f"[{grade}]"
        )
        lines.append(f"   📰 {catalyst}")
        lines.append(
            f"   🏷️ Float: {_float_label(int(r.get('float', 0)))}  "
            f"| RVOL: {pm_rvol:.1f}x"
        )
        lines.append(
            f"   📦 PM Vol: {pm_vol:,}  "
            f"| 💵 {_dvol_str(dvol)}"
        )

    lines += [
        f"\n━━━━━━━━━━━━━━━━━━",
        f"⚠️ בדוק כל מניה לפני כניסה",
        f"🚫 לא המלצת השקעה",
    ]
    return "\n".join(lines)


def format_alert(row: dict) -> str:
    """התראה על מניה בודדת — Grade A/A+ בלבד."""
    grade      = row.get("grade", "B")
    emoji      = _grade_emoji(grade)
    catalyst   = row.get("catalyst", "—")
    pm_high    = row.get("pm_high", 0)
    pm_dist    = row.get("pm_high_dist", 0)
    daily_rvol = row.get("daily_rvol", 0)
    pm_rvol    = row.get("pm_rvol", row.get("vol_ratio", 0))
    is_leader  = row.get("is_leader", False)
    leader     = row.get("leader", "")

    pm_line  = ""
    sym_line = ""

    if pm_high > 0:
        dist_str = "🔺 קרוב לפריצה!" if abs(pm_dist) < 2 else f"{pm_dist:+.1f}% מהשיא"
        pm_line  = f"📊 <b>PM High:</b>    ${pm_high:.2f}  {dist_str}\n"

    if is_leader:
        sym_line = "👑 <b>Sector Leader</b>\n"
    elif leader:
        sym_line = f"🔗 <b>Sympathy:</b>   {leader}\n"

    return (
        f"{emoji} <b>DAYS-BOT [{grade}] — {row['ticker']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>מחיר:</b>     ${row['price']:.2f}  "
        f"(אתמול: ${row.get('prev_close', 0):.2f})\n"
        f"📈 <b>גאפ:</b>      +{row['gap_pct']:.1f}%\n"
        f"{pm_line}"
        f"📰 <b>Catalyst:</b> {catalyst}\n"
        f"🏷️ <b>Float:</b>    {_float_label(int(row.get('float', 0)))}\n"
        f"📦 <b>PM Vol:</b>   {row.get('pm_volume', 0):,}\n"
        f"⚡ <b>PM RVOL:</b>  {pm_rvol:.1f}x  "
        f"(יומי: {daily_rvol:.1f}x)\n"
        f"💵 <b>$ Vol:</b>    {_dvol_str(row.get('dollar_volume', 0))}\n"
        f"{sym_line}"
        f"⭐ <b>ציון:</b>     {row.get('score', 0):.0f}/100  [{grade}]\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )


def format_watchlist(candidates: list, date: str, phase: str = "watchlist") -> str:
    return format_preopen_list(candidates, date)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    now_et   = datetime.now(ET)
    time_str = now_et.strftime("%H:%M ET")
    return (
        f"🤖 <b>DAYS-BOT — לפני פתיחה</b>\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדות היום\n"
        f"   (Gap>8%, PM Vol>100K, Float<150M)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ מחר ב-14:30"
    )
