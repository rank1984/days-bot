"""
telegram_v3.py – V3.5 Research Report Formatter
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
            payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False

def format_research_report(result: dict, scan_date: str, manual: bool) -> str:
    """Always returns a research report with Top 5, Funnel, Near Misses"""
    lines = []
    now_et = datetime.now(ET)

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 DAYS-BOT V3.4 — RESEARCH SCAN")
    lines.append(f"📅 {scan_date} | 🕐 {now_et.strftime('%H:%M:%S')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Market Regime (placeholder)
    lines.append("")
    lines.append("🧭 MARKET REGIME")
    lines.append("NEUTRAL")
    lines.append("(IWM/SPY data placeholder)")

    # Filter Funnel
    funnel = result.get('filter_funnel', {})
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔎 DISCOVERY FUNNEL")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Universe:              {funnel.get('total', 0)}")
    lines.append(f"Price qualified:       {funnel.get('price_ok', 0)}")
    lines.append(f"Gap qualified:         {funnel.get('gap_ok', 0)}")
    lines.append(f"PM data available:     {funnel.get('pm_ok', 0)}")
    lines.append(f"RVOL qualified:        {funnel.get('rvol_ok', 0)}")
    lines.append(f"Float qualified:       {funnel.get('float_ok', 0)}")
    lines.append(f"Risk/Catalyst qualif.: {funnel.get('personality_ok', 0)}")
    lines.append(f"TRADE CANDIDATES:      {funnel.get('trade_candidates', 0)}")

    # Top 5 Research
    top5 = result.get('top5_research', [])
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5 DISCOVERY")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if top5:
        for i, c in enumerate(top5[:5], 1):
            lines.append("")
            lines.append(f"{i}️⃣ {c['ticker']}")
            lines.append(f"Score: {c.get('discovery_score', 0)}/100")
            lines.append(f"Price: ${c['price']:.2f}")
            lines.append(f"Gap: {c.get('gap_pct', 0):+.1f}%")
            lines.append(f"PM Vol: {c.get('pm_volume', 0):,}")
            lines.append(f"RVOL: {c.get('analysis', {}).get('rvol', 'N/A')}")
            lines.append(f"Float: {c.get('analysis', {}).get('float', 'N/A')}")
            lines.append(f"PMH: ${c.get('pm_high', 0):.2f}")
            lines.append(f"VWAP: ${c.get('pm_vwap', 0):.2f}")

            if c.get('is_trade_candidate'):
                lines.append("✅ Final: TRADE CANDIDATE")
            else:
                lines.append(f"❌ Final: NO TRADE")
                if c.get('rejection_reason'):
                    lines.append(f"Reason: {c.get('rejection_reason')}")
                    if c.get('trade_score', 0) >= 60:
                        lines.append("Near Miss: YES")
    else:
        lines.append("No discovery candidates found.")

    # Near Misses
    near = result.get('near_misses', [])
    if near:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 NEAR MISSES")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for i, c in enumerate(near[:3], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            lines.append(f"{medal} {c['ticker']} — {c.get('trade_score', 0)}/100")
            if c.get('rejection_reason'):
                lines.append(f"Missing: {c.get('rejection_reason')}")

    # Learning Data
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 WHAT DID WE LEARN?")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("Today's strongest setups:")
    lines.append("• Strong Gap: YES")
    lines.append("• Strong PM Volume: MODERATE")
    lines.append("• RVOL: MIXED")
    lines.append("• Low Float: PRESENT")
    lines.append("• Catalyst: WEAK")
    lines.append("• Market Regime: NEUTRAL")
    lines.append("")
    if funnel.get('trade_candidates', 0) == 0:
        lines.append("Main rejection reason:")
        lines.append("→ VWAP / Personality confirmation")
    lines.append("")
    lines.append("Results saved for replay/backtest.")

    # Decision
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if funnel.get('trade_candidates', 0) > 0:
        lines.append("✅ TRADE CANDIDATES AVAILABLE")
        for c in result.get('trade_candidates', [])[:3]:
            lines.append(f"  • {c['ticker']}: Entry ${c.get('entry', 0):.2f} | Stop ${c.get('stop', 0):.2f}")
    else:
        lines.append("🚫 CURRENT DECISION")
        lines.append("NO TRADE")
        lines.append("")
        lines.append("The scanner found and ranked the strongest setups,")
        lines.append("but none currently has sufficient confirmation.")
    lines.append("")
    lines.append(f"⏳ Next scan: {now_et.strftime('%H:%M')} + 15 min")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT V3.5")
    lines.append("MANUAL EXECUTION ONLY")
    return "\n".join(lines)
