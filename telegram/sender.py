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


def _float_label(f: int) -> str:
    if f <= 0:           return "❓"
    if f < 20_000_000:   return f"🟢 {f/1_000_000:.1f}M"
    if f < 50_000_000:   return f"🟡 {f/1_000_000:.1f}M"
    if f < 100_000_000:  return f"🟠 {f/1_000_000:.0f}M"
    return                      f"🔴 {f/1_000_000:.0f}M"


def _dvol(dv: float) -> str:
    if dv >= 1_000_000: return f"${dv/1_000_000:.1f}M"
    if dv >= 1_000:     return f"${dv/1_000:.0f}K"
    return f"${dv:.0f}"


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")

    lines = [
        f"🎯 <b>DAYS-BOT Elite — לפני פתיחה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    if low_quality:
        lines.append("⚠️ <b>ציון נמוך — בדוק בזהירות</b>\n")

    for i, r in enumerate(candidates[:5], 1):
        fresh   = r.get("freshness", 0)
        mom_s   = r.get("momentum_score", 0)
        combined = r.get("combined", 0)
        pm_rvol = r.get("pm_rvol", 0)
        pm_vol  = r.get("pm_volume", 0)
        dvol    = r.get("dollar_volume", 0)

        # PM High
        pm_dist = r.get("pm_high_dist", 0)
        if pm_dist <= 2:    dist_e = "🔺"
        elif pm_dist <= 10: dist_e = "⚡"
        else:               dist_e = "⚠️"

        # PM High Age
        age = r.get("pm_high_age", 999)
        if age <= 5:    age_e = "🟢"
        elif age <= 15: age_e = "🟡"
        elif age < 999: age_e = "🔴"
        else:           age_e = "❓"

        # Momentum
        mom5  = r.get("momentum_5m", 0)
        mom_e = "📈" if mom5 >= 0 else "📉"

        # VWAP
        vd    = r.get("vwap_dist", 0)
        vd_e  = "🟢" if vd >= 0 else "🔴"

        # Vol Accel
        accel = r.get("vol_accel", 1.0)
        if accel >= 2.0:    ac_e = "🚀"
        elif accel >= 1.5:  ac_e = "⚡"
        else:               ac_e = "➡️"

        catalyst = r.get("catalyst", "—")

        lines.append(
            f"\n<b>{i}. {r['ticker']}</b>  "
            f"${r['price']:.2f}  +{r['gap_pct']:.1f}%"
        )
        lines.append(f"   📰 {catalyst}")
        lines.append(
            f"   🏷️ {_float_label(int(r.get('float',0)))}  "
            f"| 📦 {pm_vol:,}  | 💵 {_dvol(dvol)}"
        )
        lines.append(
            f"   {dist_e} PM High: {pm_dist:.1f}%  "
            f"| {age_e} Age: {age}min"
        )
        lines.append(
            f"   {mom_e} 5min: {mom5:+.1f}%  "
            f"| {vd_e} VWAP: {vd:+.1f}%  "
            f"| {ac_e} Accel: {accel:.1f}x"
        )
        lines.append(
            f"   🌊 Fresh: <b>{fresh:.0f}</b>  "
            f"| ⚡ Mom: <b>{mom_s:.0f}</b>  "
            f"| 🎯 Combined: <b>{combined:.0f}</b>"
        )

    lines += [
        "\n━━━━━━━━━━━━━━━━━━",
        "⚠️ בדוק כל מניה לפני כניסה",
        "🚫 לא המלצת השקעה",
    ]
    return "\n".join(lines)


def format_watchlist(candidates: list, date: str, phase: str = "watchlist") -> str:
    return format_preopen_list(candidates, date)


def format_alert(row: dict) -> str:
    pm_high  = row.get("pm_high", 0)
    pm_dist  = row.get("pm_high_dist", 0)
    pm_rvol  = row.get("pm_rvol", row.get("vol_ratio", 0))
    catalyst = row.get("catalyst", "—")
    fresh    = row.get("freshness", 0)
    mom_s    = row.get("momentum_score", 0)
    combined = row.get("combined", 0)

    pm_line = (
        f"📊 <b>PM High:</b> ${pm_high:.2f}  "
        f"{'🔺 פריצה!' if abs(pm_dist) < 2 else f'{pm_dist:+.1f}%'}\n"
    ) if pm_high > 0 else ""

    return (
        f"🎯 <b>DAYS-BOT — {row['ticker']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 ${row['price']:.2f}  📈 +{row['gap_pct']:.1f}%\n"
        f"{pm_line}"
        f"📰 {catalyst}\n"
        f"🏷️ {_float_label(int(row.get('float',0)))}  "
        f"| ⚡ RVOL: {pm_rvol:.1f}x\n"
        f"📦 {row.get('pm_volume',0):,}  "
        f"| 💵 {_dvol(row.get('dollar_volume',0))}\n"
        f"🌊 Fresh: <b>{fresh:.0f}</b>  "
        f"| ⚡ Mom: <b>{mom_s:.0f}</b>  "
        f"| 🎯 <b>{combined:.0f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    return (
        f"🤖 <b>DAYS-BOT — לפני פתיחה</b>\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ מחר ב-14:30"
    )
