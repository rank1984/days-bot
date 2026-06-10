"""
weekly_report.py
----------------
שולח דוח שבועי לטלגרם כל יום שישי.
"""

from database.db import get_week_performance


def build_weekly_report() -> str:
    rows = get_week_performance()

    if not rows:
        return "📊 <b>DAYS-BOT — דוח שבועי</b>\n\nאין נתונים השבוע."

    total      = len(rows)
    with_close = [r for r in rows if r.get("close_price")]
    wins       = [r for r in with_close if (r.get("pnl_close_pct") or 0) > 0]
    win_rate   = round(len(wins) / len(with_close) * 100) if with_close else 0

    avg_hod = 0
    if with_close:
        hods = [r.get("pnl_hod_pct") or 0 for r in with_close]
        avg_hod = round(sum(hods) / len(hods), 1)

    best  = max(with_close, key=lambda r: r.get("pnl_hod_pct") or 0) if with_close else None
    worst = min(with_close, key=lambda r: r.get("pnl_close_pct") or 0) if with_close else None

    lines = [
        f"📊 <b>DAYS-BOT — דוח שבועי</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"🔔 <b>התראות:</b>    {total}",
        f"✅ <b>Win Rate:</b>  {win_rate}%",
        f"📈 <b>ממוצע HOD:</b> +{avg_hod}%",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    # פירוט כל התראה
    for r in rows:
        ticker    = r["ticker"]
        date      = r["alert_date"]
        entry     = r.get("alert_price") or 0
        hod       = r.get("hod") or 0
        close     = r.get("close_price") or 0
        pnl_hod   = r.get("pnl_hod_pct") or 0
        pnl_close = r.get("pnl_close_pct") or 0
        catalyst  = r.get("catalyst") or "—"
        grade     = r.get("grade") or "?"

        emoji = "✅" if pnl_close > 0 else "❌" if pnl_close < 0 else "⏳"
        lines.append(
            f"\n{emoji} <b>{ticker}</b> [{grade}]  {date}\n"
            f"   כניסה: ${entry:.2f} | HOD: ${hod:.2f} (+{pnl_hod:.1f}%)\n"
            f"   סגירה: ${close:.2f} ({pnl_close:+.1f}%)\n"
            f"   📰 {catalyst}"
        )

    if best:
        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>הכי טוב:</b>  {best['ticker']} +{best.get('pnl_hod_pct',0):.1f}%"
        )
    if worst:
        lines.append(
            f"💀 <b>הכי גרוע:</b> {worst['ticker']} {worst.get('pnl_close_pct',0):.1f}%"
        )

    lines.append("\n🚫 לא המלצת השקעה")
    return "\n".join(lines)
