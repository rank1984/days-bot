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


def _grade_emoji(grade: str) -> str:
    return {"A+": "🔥", "A": "✅", "B": "👀", "C": "💤"}.get(grade, "—")


def _float_label(f: int) -> str:
    if f <= 0:          return "❓ לא ידוע"
    if f < 20_000_000:  return f"🟢 {f/1_000_000:.1f}M"
    if f < 50_000_000:  return f"🟡 {f/1_000_000:.1f}M"
    if f < 100_000_000: return f"🟠 {f/1_000_000:.0f}M"
    return                     f"🔴 {f/1_000_000:.0f}M"


def _dvol_str(dv: float) -> str:
    if dv >= 1_000_000: return f"${dv/1_000_000:.1f}M"
    if dv >= 1_000:     return f"${dv/1_000:.0f}K"
    return f"${dv:.0f}"


def format_alert(row: dict) -> str:
    grade      = row.get("grade", "B")
    emoji      = _grade_emoji(grade)
    catalyst   = row.get("catalyst", "—")
    is_leader  = row.get("is_leader", False)
    leader     = row.get("leader", "")
    pm_high    = row.get("pm_high", 0)
    pm_dist    = row.get("pm_high_dist", 0)
    daily_rvol = row.get("daily_rvol", 0)
    pm_rvol    = row.get("pm_rvol", row.get("vol_ratio", 0))

    if pm_high > 0:
        dist_str = "🔺 קרוב לפריצה!" if abs(pm_dist) < 2 else f"{pm_dist:+.1f}%"
        pm_line  = f"📊 <b>PM High:</b>    ${pm_high:.2f}  {dist_str}\n"
    else:
        pm_line = ""

    if is_leader:
        sym_line = "👑 <b>Sector Leader</b>\n"
    elif leader:
        sym_line = f"🔗 <b>Sympathy:</b>   {leader}\n"
    else:
        sym_line = ""

    return (
        f"{emoji} <b>DAYS-BOT [{grade}] — {row['ticker']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>מחיר:</b>      ${row['price']:.2f}  "
        f"(אתמול: ${row.get('prev_close', 0):.2f})\n"
        f"📈 <b>גאפ:</b>       +{row['gap_pct']:.1f}%\n"
        f"{pm_line}"
        f"📦 <b>PM Volume:</b>  {row.get('pm_volume', 0):,}\n"
        f"⚡ <b>PM RVOL:</b>   {pm_rvol:.1f}x  "
        f"(יומי: {daily_rvol:.1f}x)\n"
        f"💵 <b>$ Volume:</b>  {_dvol_str(row.get('dollar_volume', 0))}\n"
        f"🏷️ <b>Float:</b>     {_float_label(int(row.get('float', 0)))}\n"
        f"📰 <b>Catalyst:</b>  {catalyst}\n"
        f"{sym_line}"
        f"⭐ <b>ציון:</b>      {row.get('score', 0):.0f}/100  "
        f"[{grade}]\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )


def format_watchlist(candidates: list, date: str, phase: str = "watchlist") -> str:
    title = "Watchlist בוקר" if phase == "watchlist" else "סריקה שוטפת"    top    = [r for r in candidates if r.get("grade") in ("A+", "A")][:5]
    others = [r for r in candidates if r.get("grade") not in ("A+", "A")][:5]

    lines = [
        f"👀 <b>DAYS-BOT — {title}</b>",        f"📅 {date}",
        f"━━━━━━━━━━━━━━━━━━",
        f"🔥 <b>TOP WATCH</b>",
    ]
    for i, r in enumerate(top, 1):
        lines.append(
            f"{_grade_emoji(r.get('grade','B'))} {i}. <b>{r['ticker']}</b>  "
            f"${r['price']:.2f}  +{r['gap_pct']:.1f}%  "
            f"RVOL:{r.get('pm_rvol', r.get('vol_ratio',0)):.1f}x  "
            f"Float:{_float_label(int(r.get('float',0)))}  "
            f"[{r.get('grade','?')}]"
        )
    if others:
        lines.append(f"\n📋 <b>Extended Watch</b>")
        for i, r in enumerate(others, 1):
            lines.append(
                f"  {i}. {r['ticker']}  "
                f"${r['price']:.2f}  +{r['gap_pct']:.1f}%  "
                f"[{r.get('grade','?')}]"
            )
    lines += [f"━━━━━━━━━━━━━━━━━━", f"⏰ Final Alerts בפתיחה"]
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    return (
        f"🤖 <b>DAYS-BOT — דוח יומי</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>תאריך:</b>      {date}\n"
        f"🔍 <b>מניות שנסרקו:</b> {universe_size}\n"
        f"😴 <b>תוצאה:</b>      לא נמצאו מועמדות\n"
        f"                  (Gap>8%, PM Vol>100K, Float<150M)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ הסריקה הבאה מחר בפתיחה"
    )
