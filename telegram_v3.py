"""
telegram_v3.py – V4.3 Telegram Formatter
Displays ALL fields with proper formatting, including UNAVAILABLE indicators.
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for parse_mode in ["HTML", None]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return True
        except:
            continue
    return False


def format_research_report(candidates: list, now_et: datetime) -> str:
    """
    Full research report with all fields displayed.
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V4.3 – RESEARCH SCAN")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים")
        lines.append("")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    # Top 5
    candidates_sorted = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)
    top5 = candidates_sorted[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        trade_type = c.get('trade_type', 'WATCH')
        icon = "🟢" if "INTRADAY" in trade_type else "🟣" if "SWING" in trade_type else "🟡"
        intraday_score = c.get('composite_score', 0)
        swing_score = c.get('swing_score', 0)

        lines.append(f"{i}️⃣ {c['ticker']}")
        lines.append(f"  Intraday: {intraday_score:.0f}/100 | Swing: {swing_score:.0f}/100")
        lines.append(f"  Type: {icon} {trade_type}")

        # Price & Gap
        lines.append(f"  Price: ${c.get('price', 0):.2f} | Gap: {c.get('gap_pct', 0):+.1f}%")
        lines.append(f"  PM Volume: {c.get('pm_volume', 0):,}")

        # PM Data Quality
        pm_quality = c.get('pm_data_quality', 'UNKNOWN')
        if pm_quality == 'UNKNOWN_PM_DATA':
            pm_quality = '⚠️ UNKNOWN'
        lines.append(f"  PM Data: {pm_quality}")

        # RVOL
        rvol = c.get('rvol')
        rvol_status = c.get('rvol_status', 'UNAVAILABLE')
        if rvol is not None:
            lines.append(f"  RVOL: {rvol:.2f}x ({rvol_status})")
        else:
            lines.append(f"  RVOL: UNAVAILABLE")

        # Spread
        spread = c.get('spread_pct')
        if spread is not None and spread != 'UNAVAILABLE':
            lines.append(f"  Spread: {spread:.2f}%")
        else:
            lines.append(f"  Spread: UNAVAILABLE")

        # Catalyst
        catalyst_type = c.get('catalyst_type', 'UNAVAILABLE')
        catalyst_score = c.get('catalyst_score', 0)
        if catalyst_type != 'UNAVAILABLE':
            lines.append(f"  Catalyst: {catalyst_type} (Score: {catalyst_score}/10)")
        else:
            lines.append(f"  Catalyst: UNAVAILABLE")

        # Short & Float (if available)
        float_val = c.get('float')
        short = c.get('short_interest')
        if float_val:
            lines.append(f"  Float: {float_val:,.0f}")
        if short:
            lines.append(f"  Short Interest: {short*100:.1f}%")

        # SEC Risk
        sec_level = c.get('sec_risk_level', 'LOW')
        lines.append(f"  SEC Risk: {sec_level}")

        # Trade Plan (if valid)
        if c.get('plan_valid', False):
            lines.append(f"  Entry: ${c.get('entry', 0):.2f} | Stop: ${c.get('stop', 0):.2f}")
            lines.append(f"  T1: ${c.get('target_1', 0):.2f} | T2: ${c.get('target_2', 0):.2f}")
            lines.append(f"  Shares: {c.get('position_size', 0)} | Max Loss: ${c.get('max_loss', 0):.2f}")
        else:
            plan_error = c.get('plan_error', 'No valid trade plan')
            lines.append(f"  ⚠️ {plan_error}")

        lines.append("")

    # Best Intraday
    intraday_best = next((c for c in top5 if c.get('trade_type') in ['INTRADAY', 'BOTH']), None)
    if intraday_best:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟢 BEST INTRADAY")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{intraday_best['ticker']}")
        lines.append(f"Score: {intraday_best.get('composite_score', 0):.0f}/100")
        lines.append(f"Entry: ${intraday_best.get('entry', 0):.2f}")
        lines.append(f"Stop:  ${intraday_best.get('stop', 0):.2f}")
        lines.append(f"T1:    ${intraday_best.get('target_1', 0):.2f}")
        lines.append(f"T2:    ${intraday_best.get('target_2', 0):.2f}")
        lines.append("")

    # Best Swing
    swing_best = next((c for c in top5 if c.get('trade_type') in ['SWING_1_3D', 'BOTH']), None)
    if swing_best:
        swing_data = swing_best.get('swing_data', {})
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟣 BEST SWING (1–3 DAYS)")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{swing_best['ticker']}")
        lines.append(f"Swing Score: {swing_best.get('swing_score', 0):.0f}/100")
        lines.append(f"Entry: ${swing_best.get('entry', 0):.2f}")
        lines.append(f"Stop:  ${swing_best.get('stop', 0):.2f}")
        lines.append(f"T1:    ${swing_best.get('target_1', 0):.2f}")
        lines.append(f"T2:    ${swing_best.get('target_2', 0):.2f}")
        lines.append("")

    # Watchlist
    watch_candidates = [c for c in top5 if c.get('trade_type') == 'WATCH']
    if watch_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟡 WATCHLIST")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for c in watch_candidates[:3]:
            lines.append(f"• {c['ticker']} – {c.get('composite_score', 0):.0f}/100")
        lines.append("")

    # Decision
    trade_candidates = [c for c in top5 if c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']]
    if trade_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ DECISION: TRADE OPPORTUNITIES FOUND")
        lines.append("Check the best Intraday and Swing above.")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 DECISION: NO TRADE TODAY")
        lines.append("No setup met the trade threshold.")
        lines.append("The Top 5 are the strongest discoveries.")

    lines.append("")
    lines.append("⏳ Next scan: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)


def format_lesson_for_telegram(lesson: dict) -> str:
    """Format lesson as Telegram message"""
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📚 DAYS-BOT V4.3 – לקח יומי")
    lines.append(f"📅 {lesson['date']} | {lesson['trading_day']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    funnel = lesson.get("funnel", {})
    lines.append("")
    lines.append("🔎 משפך הגילוי:")
    lines.append(f"  Universe:        {funnel.get('universe', 0)}")
    lines.append(f"  Snapshots:       {funnel.get('snapshots_received', 0)}")
    lines.append(f"  מועמדים קפדניים:  {funnel.get('strict_candidates', 0)}")
    lines.append(f"  נפסלו: גאפ       {funnel.get('rejected_gap', 0)}")
    lines.append(f"  נפסלו: נפח       {funnel.get('rejected_volume', 0)}")

    top5 = lesson.get("top5", [])
    lines.append("")
    lines.append("🏆 TOP 5:")
    for i, t in enumerate(top5, 1):
        lines.append(f"  {i}. {t['ticker']:6s} | Intraday={t['intraday_score']:.0f} | Swing={t['swing_score']:.0f} | {t['trade_type']}")

    changes = lesson.get("changes_vs_yesterday", {})
    if changes:
        lines.append("")
        lines.append("📈 שינויים מאתמול:")
        for key, val in list(changes.items())[:4]:
            arrow = "🔼" if val['direction'] == "up" else "🔽"
            lines.append(f"  {key}: {val['previous']} → {val['current']} {arrow}")

    recommendations = lesson.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("💡 המלצות:")
        for rec in recommendations[:3]:
            lines.append(f"  • {rec}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – למידה יומית")
    return "\n".join(lines)