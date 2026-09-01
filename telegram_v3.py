"""
telegram_v3.py – V3.5 Telegram Formatter
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
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V3.5 – RESEARCH SCAN")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים")
        lines.append("")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    # Filter candidates with trade potential
    trade_candidates = [c for c in candidates if c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']]
    watch_candidates = [c for c in candidates if c.get('trade_type') == 'WATCH']

    # Top 5 by composite score
    candidates_sorted = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)
    top5 = candidates_sorted[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    for i, c in enumerate(top5, 1):
        score = c.get('composite_score', 0)
        trade_type = c.get('trade_type', 'WATCH')
        icon = "🟢" if "INTRADAY" in trade_type else "🟣" if "SWING" in trade_type else "🟡"
        lines.append(f"{i}️⃣ {c['ticker']} — {score:.0f}/100")
        lines.append(f"{icon} {trade_type}")
        lines.append("")

    # Best Intraday
    intraday_best = next((c for c in trade_candidates if c.get('trade_type') in ['INTRADAY', 'BOTH']), None)
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
        lines.append(f"Risk:  ${intraday_best.get('risk_per_share', 0):.2f}/share")
        lines.append(f"Shares: {intraday_best.get('position_size', 0)}")
        lines.append("")

    # Best Swing
    swing_best = next((c for c in trade_candidates if c.get('trade_type') in ['SWING_1_3D', 'BOTH']), None)
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
        lines.append(f"Trend: {'🟢' if swing_data.get('above_20') else '🔴'} Above 20 EMA")
        lines.append(f"RS vs SPY: {swing_data.get('rs_vs_spy', 0):.1f}%")
        lines.append(f"Structure: {swing_data.get('structure', 'N/A')}")
        lines.append("")

    # Watchlist
    if watch_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟡 WATCHLIST")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for c in watch_candidates[:3]:
            lines.append(f"• {c['ticker']} – {c.get('composite_score', 0):.0f}/100")
        lines.append("")

    # Decision
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
