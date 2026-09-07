import requests
from datetime import datetime
import pytz
ET = pytz.timezone("America/New_York")

def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id: return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for parse_mode in ["HTML", None]:
        try:
            payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
            if parse_mode: payload["parse_mode"] = parse_mode
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200: return True
        except: continue
    return False

def _state_icon(state: str) -> str:
    icons = {
        "ACCUMULATION": "🔄",
        "PRESSURE": "⏳",
        "BREAKOUT": "🚀",
        "MOMENTUM": "⚡",
        "EXHAUSTION": "🔻",
        "FADE": "📉",
        "UNKNOWN": "❓",
    }
    return icons.get(state, "❓")

def _action_icon(trade_type: str, data_status: str) -> str:
    if data_status == "NO_TRADE":
        return "🔴 NO TRADE"
    if data_status == "WATCH":
        return "👀 WATCH"
    if trade_type in ["INTRADAY", "BOTH"]:
        return "✅ TRADE CANDIDATE"
    if trade_type == "SWING_1_3D":
        return "🟣 SWING CANDIDATE"
    return "👀 WATCH"

def format_research_report(candidates: list, now_et: datetime) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V5.0 – EARLY MOVE RESEARCH")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if not candidates:
        lines.append("😴 לא נמצאו מועמדים למסחר")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    top5 = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)[:5]
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 חמשת המועמדים המובילים")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    for i, c in enumerate(top5, 1):
        early_state = c.get('early_state', 'UNKNOWN')
        state_icon = _state_icon(early_state)
        day_trade = c.get('day_trade_score', 0)
        swing = c.get('swing_score', 0)
        trade_type = c.get('trade_type', 'WATCH')
        action = _action_icon(trade_type, c.get('data_status', 'NO_TRADE'))

        lines.append(f"{i}️⃣ {c['ticker']} — {state_icon} {early_state}")
        lines.append(f"  Early Move: {c.get('early_score', 0):.0f}/100")
        lines.append(f"  Day Trade:  {day_trade:.0f}/100  |  Swing 1-3D: {swing:.0f}/100")
        lines.append(f"  Action: {action}")
        lines.append(f"  Gap: {c.get('gap_pct', 0):+.1f}%  |  Price: ${c.get('price', 0):.2f}")
        lines.append(f"  PM Volume: {c.get('pm_volume', 0):,}")
        # Behavioral tags (if available)
        comps = c.get('early_components', {})
        tags = []
        if comps.get('pullback_buying', 0) > 60: tags.append("✅ Pullbacks Bought")
        if comps.get('pmh_pressure', 0) > 60: tags.append("✅ PMH Pressure")
        if comps.get('volume_acceleration', 0) > 60: tags.append("✅ Vol Accelerating")
        if comps.get('price_acceleration', 0) > 60: tags.append("✅ Price Accel")
        if comps.get('vwap_control', 0) > 60: tags.append("✅ Above VWAP")
        if tags:
            lines.append("  Behavior: " + " | ".join(tags[:3]))
        lines.append("  Catalyst: " + c.get('catalyst_type', 'UNAVAILABLE'))
        lines.append("  Float: " + (f"{c.get('float', 0):,.0f}" if c.get('float') else "N/A"))
        lines.append("  Short: " + (f"{c.get('short_interest', 0)*100:.1f}%" if c.get('short_interest') else "N/A"))
        sec = c.get('sec_risk_level', 'LOW')
        sec_map = {"LOW":"✅ Low","MEDIUM":"🟡 Medium","HIGH":"🔴 High","CRITICAL":"🚨 Critical"}
        lines.append(f"  SEC Risk: {sec_map.get(sec, sec)}")
        if c.get('plan_valid', False):
            lines.append(f"  Entry: ${c.get('entry', 0):.2f} | Stop: ${c.get('stop', 0):.2f}")
            lines.append(f"  T1: ${c.get('target_1', 0):.2f} | T2: ${c.get('target_2', 0):.2f}")
        else:
            lines.append(f"  ⚠️ {c.get('plan_error', 'No trade plan')}")
        lines.append("")

    # Best by Early Move
    top_early = sorted(candidates, key=lambda x: x.get('early_score', 0), reverse=True)[0] if candidates else None
    if top_early and top_early.get('early_score', 0) >= 60:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚨 EARLY ALERT")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{top_early['ticker']} — {_state_icon(top_early.get('early_state', 'UNKNOWN'))} {top_early.get('early_state', 'UNKNOWN')}")
        lines.append(f"Early Move: {top_early.get('early_score', 0):.0f}/100")
        if top_early.get('early_state') in ["PRESSURE", "BREAKOUT"]:
            lines.append("⏳ Watch PMH for breakout confirmation.")
        elif top_early.get('early_state') == "ACCUMULATION":
            lines.append("🔄 Accumulation detected – monitor for pressure build.")
        elif top_early.get('early_state') == "MOMENTUM":
            lines.append("⚡ Momentum building – watch for continuation.")
        lines.append("")

    # Decision summary
    actionable = [c for c in candidates if c.get('data_status') == 'ACTIONABLE' and c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']]
    if actionable:
        best = actionable[0]
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ TRADE CANDIDATE")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{best['ticker']} | Day Trade: {best.get('day_trade_score', 0):.0f} | Swing: {best.get('swing_score', 0):.0f}")
        if best.get('plan_valid'):
            lines.append(f"Entry: ${best.get('entry', 0):.2f} | Stop: ${best.get('stop', 0):.2f}")
        lines.append("⚠️ Manual execution only")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 NO TRADE CANDIDATE TODAY")
        lines.append("Top 5 are research candidates – check Early Alert for potential setups.")

    lines.append("")
    lines.append("⏳ Next scan: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ BOT DOES NOT EXECUTE ORDERS")
    return "\n".join(lines)

def format_lesson_for_telegram(lesson: dict) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📚 DAYS-BOT V5.0 – לקח יומי")
    lines.append(f"📅 {lesson['date']} | {lesson['trading_day']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    funnel = lesson.get("funnel", {})
    lines.append("")
    lines.append("🔎 משפך הגילוי:")
    lines.append(f"  יקום (Universe):        {funnel.get('universe', 0)}")
    lines.append(f"  סנאפשוטים:              {funnel.get('snapshots_received', 0)}")
    lines.append(f"  מועמדים קפדניים:        {funnel.get('strict_candidates', 0)}")
    lines.append(f"  נפסלו: גאפ              {funnel.get('rejected_gap', 0)}")
    lines.append(f"  נפסלו: נפח              {funnel.get('rejected_volume', 0)}")
    top5 = lesson.get("top5", [])
    lines.append("")
    lines.append("🏆 חמשת המובילים:")
    for i, t in enumerate(top5, 1):
        type_hebrew = {"INTRADAY":"יומי","SWING_1_3D":"Swing","BOTH":"שניהם","WATCH":"מעקב"}.get(t.get('trade_type','WATCH'), t.get('trade_type','WATCH'))
        lines.append(f"  {i}. {t['ticker']:6s} | Early={t.get('early_score', 0):.0f} | Day={t.get('day_trade_score', 0):.0f} | Swing={t.get('swing_score', 0):.0f} | {type_hebrew}")
    recommendations = lesson.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("💡 המלצות לשיפור:")
        for rec in recommendations[:3]: lines.append(f"  • {rec}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – למידה יומית")
    return "\n".join(lines)
