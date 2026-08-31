"""
telegram_v3.py – V3.5 Telegram Formatter
Research Report, Trade Card, Debug, No Candidates
"""

import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """
    Send a Telegram message with automatic fallback from HTML to plain text.
    """
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

            print(f"[Telegram] {parse_mode} failed: {resp.status_code}")

        except Exception as e:
            print(f"[Telegram] {parse_mode} error: {e}")

    return False


# ============================================================
# RESEARCH REPORT (V3.5) – FULLY IN HEBREW
# ============================================================

def format_research_report(result: dict, now_et: datetime) -> str:
    """
    Full research report in Hebrew with:
    - Market Regime
    - Discovery Funnel
    - Top 5 Discovery (with details)
    - Near Misses
    - Trade Candidates
    - Decision
    - Recommendations
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 DAYS-BOT V3.5 – דוח מחקר יומי")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # ============================================================
    # MARKET REGIME
    # ============================================================
    regime = result.get('regime', {})
    lines.append("🧭 מצב השוק")
    if regime.get('description') and "Could not" not in regime['description']:
        lines.append(f"  {regime['description']}")
    else:
        lines.append("  ⚠️ לא ניתן לקבל נתוני שוק כרגע (סוף שבוע או מחוץ לשעות המסחר)")
    lines.append("")

    # ============================================================
    # DISCOVERY FUNNEL
    # ============================================================
    funnel = result.get('funnel', {})
    universe = funnel.get('universe', 0)
    discovery = funnel.get('discovery', 0)
    analysis = funnel.get('analysis', 0)
    trade = funnel.get('trade', 0)

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔎 משפך הגילוי")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📌 סה\"כ מניות בסורק:        {universe}")
    lines.append(f"📌 עברו שלב גילוי:          {discovery}")
    lines.append(f"📌 עברו ניתוח מעמיק:        {analysis}")
    lines.append(f"📌 מועמדים למסחר:           {trade}")
    lines.append("")

    # ============================================================
    # TOP 5 DISCOVERY
    # ============================================================
    top5 = result.get('top5', [])
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 חמשת המועמדים המובילים")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if top5:
        for i, c in enumerate(top5, 1):
            a = c.get('analysis', {})
            score = c.get('composite_score', c.get('event_score', 0))
            ticker = c['ticker']
            price = c.get('price', 0)
            gap = c.get('gap_pct', 0)
            pm_vol = c.get('pm_volume', 0)
            pm_high = c.get('pm_high', 0)
            pm_vwap = c.get('pm_vwap', 0)
            rvol = a.get('rvol', 0)
            float_val = a.get('float', 0)
            short = a.get('short_interest', 0)

            lines.append(f"{i}️⃣ {ticker}")
            lines.append(f"   ציון: {score:.0f}/100")
            lines.append(f"   מחיר: ${price:.2f} | Gap: {gap:+.1f}%")
            lines.append(f"   נפח PM: {pm_vol:,}")
            if rvol:
                lines.append(f"   RVOL: {rvol:.1f}x")
            if float_val:
                lines.append(f"   Float: {float_val:,.0f}")
            if short:
                lines.append(f"   Short Interest: {short*100:.1f}%")
            lines.append(f"   PM High: ${pm_high:.2f} | VWAP: ${pm_vwap:.2f}")

            # Final status
            if c.get('plan_valid', False):
                lines.append("   ✅ סופי: מועמד למסחר")
            else:
                reason = "לא עבר את כל המסננים"
                if a.get('personality', {}).get('personality') == "GAP_AND_CRAP":
                    reason = "אופי המניה: GAP_AND_CRAP (נוטה לקרוס)"
                elif a.get('sec_risk', {}).get('has_offering'):
                    reason = "סיכון SEC – הנפקה פעילה"
                elif rvol and rvol < 3:
                    reason = "RVOL נמוך מ-3x"
                elif c.get('pm_dist_signed', 0) < 0:
                    reason = "מחיר מתחת ל-PM High"
                elif gap < 10:
                    reason = "גאפ נמוך מ-10%"
                lines.append(f"   ❌ סופי: לא למסחר – {reason}")
            lines.append("")
    else:
        lines.append("😴 לא נמצאו מועמדים בשלב הגילוי")
        lines.append("")
        lines.append("   סיבות אפשריות:")
        lines.append("   • מחוץ לשעות המסחר (הסריקה פועלת 08:00–09:30 ET)")
        lines.append("   • אין מניות עם גאפ משמעותי היום")
        lines.append("   • יום מסחר חלש או ללא חדשות")
        lines.append("")

    # ============================================================
    # NEAR MISSES
    # ============================================================
    near_misses = result.get('near_misses', [])
    if near_misses:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 כמעט ועברו")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for nm in near_misses:
            lines.append(f"🥇 {nm['ticker']} – ציון: {nm['score']:.0f}/100")
            lines.append(f"   חסר: {nm['reason']}")
            lines.append("")

    # ============================================================
    # TRADE CANDIDATES
    # ============================================================
    trade_candidates = result.get('trade_candidates', [])
    if trade_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ מועמדים למסחר")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for c in trade_candidates[:3]:
            lines.append(f"• {c['ticker']}")
            lines.append(f"  כניסה: ${c.get('entry', 0):.2f} | סטופ: ${c.get('stop', 0):.2f}")
            lines.append(f"  יעד 1: ${c.get('target_1', 0):.2f} | יעד 2: ${c.get('target_2', 0):.2f}")
            lines.append(f"  מניות: {c.get('position_size', 0)}")
            lines.append("")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 החלטה: אין מסחר")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("אף מועמד לא עבר את כל תנאי האישור.")
        lines.append("המועמדים המובילים למעלה הם החזקים ביותר שנמצאו,")
        lines.append("אך חסר להם אישור סופי (VWAP, פריצה, נפח).")
        lines.append("")

    # ============================================================
    # LEARNING INSIGHTS
    # ============================================================
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📖 מה למדנו היום?")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if discovery == 0:
        lines.append("• אין מועמדים – כנראה יום שקט או מחוץ לשעות הפעילות")
        lines.append("• מומלץ לבדוק שוב ב-08:45–09:15 ET")
    elif trade == 0 and discovery > 0:
        lines.append(f"• נמצאו {discovery} מועמדים אך כולם נפסלו")
        lines.append("• הסיבות העיקריות: RVOL נמוך, SEC, או Personality")
        lines.append("• ייתכן שצריך להקל על המסננים בימים שקטים")
    else:
        lines.append(f"• נמצאו {trade} מועמדים למסחר")
        lines.append("• בדוק את הפרטים בטלגרם והחלט על ביצוע")

    lines.append("")
    lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ ביצוע ידני בלבד – הבוט אינו מבצע פקודות")
    return "\n".join(lines)


# ============================================================
# V3.4 TRADE CARD (in Hebrew)
# ============================================================

def format_trade_card_v34(candidate: dict) -> str:
    """
    Detailed trade card for a single candidate in Hebrew.
    """
    a = candidate.get('analysis', {})
    lines = []

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🚀 {candidate['ticker']} – ההמלצה המובילה")
    lines.append(f"ציון: {candidate.get('event_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  VWAP: ${candidate['pm_vwap']:.2f}")
    lines.append(f"📦 נפח PM: {candidate['pm_volume']:,}")
    lines.append("")

    # Fundamentals
    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    rs = a.get('rs', 0)
    if float_val or short or rvol:
        lines.append("📊 נתונים בסיסיים:")
        if float_val:
            lines.append(f"  Float: {float_val:,.0f}")
        if short:
            lines.append(f"  Short Interest: {short*100:.1f}%")
        if rvol:
            lines.append(f"  RVOL: {rvol:.1f}x")
        if rs:
            lines.append(f"  חוזק יחסי: {rs:.2f}")
        lines.append("")

    # Personality
    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append("🧠 אופי המניה:")
        lines.append(f"  סוג: {personality.get('personality', 'NEUTRAL')}")
        lines.append(f"  אחוז כישלון היסטורי: {personality.get('failure_rate', 0):.1f}%")
        lines.append("")

    # Catalyst
    catalyst = a.get('catalyst', {})
    if catalyst.get('type') and catalyst.get('type') != "NO_NEWS":
        lines.append("🔬 קטליזטור:")
        lines.append(f"  סוג: {catalyst.get('type', 'UNKNOWN')}")
        lines.append(f"  איכות: {catalyst.get('score', 0)}/10")
        lines.append(f"  {catalyst.get('summary', '')}")
        lines.append("")

    # Sentiment
    sent = a.get('sentiment', {})
    if sent.get('total_messages', 0) > 0:
        lines.append("💬 סנטימנט:")
        lines.append(f"  שוורי: {sent.get('bull_pct', 0):.0f}%  דובי: {sent.get('bear_pct', 0):.0f}%")
        lines.append(f"  נטו: {sent.get('sentiment_score', 0):.2f}")
        lines.append("")

    # SEC Risk
    sec = a.get('sec_risk', {})
    if sec.get('has_offering'):
        lines.append(f"⚠️ סיכון SEC: {sec.get('risk_level')} – {sec.get('filing_type')}")
        lines.append("")

    # Sympathy Plays
    sympathy = a.get('sympathy', [])
    if sympathy:
        lines.append("🔄 מניות נלוות (אותו סקטור):")
        for s in sympathy[:3]:
            lines.append(f"  • {s['ticker']} – ${s['price']:.2f} (נפח: {s.get('pm_volume', 0):,})")
        lines.append("")

    # Trade Plan
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🎯 תוכנית מסחר")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"סטטוס: {candidate.get('decision', 'WATCH')}")
    lines.append("")
    lines.append(f"כניסה: ${candidate.get('entry', 0):.2f}")
    lines.append(f"סטופ:  ${candidate.get('stop', 0):.2f}")
    lines.append(f"יעד 1: ${candidate.get('target_1', 0):.2f}")
    lines.append(f"יעד 2: ${candidate.get('target_2', 0):.2f}")
    lines.append(f"סיכון למניה: ${candidate.get('risk_per_share', 0):.2f}")
    lines.append(f"מניות מומלצות: {candidate.get('position_size', 0)}")
    lines.append(f"הפסד מקסימלי: ${candidate.get('max_loss', 0):.2f}")
    lines.append("")
    lines.append(f"⏱ זמן החזקה: {candidate.get('hold_type', 'NONE')}")
    lines.append("")
    lines.append("❌ תנאי ביטול:")
    for cond in candidate.get('invalidation_conditions', ['VWAP נשבר', 'פריצה נכשלת']):
        lines.append(f"  • {cond}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ ביצוע ידני בלבד")
    return "\n".join(lines)


# ============================================================
# NO CANDIDATES (Fallback – Hebrew)
# ============================================================

def format_no_candidates_v34(date: str, now_et: datetime, learning_mode: bool, debug: bool) -> str:
    """
    Fallback message when even research engine yields nothing.
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 DAYS-BOT V3.5 – דוח סריקה")
    lines.append(f"📅 {date}  |  🕐 {now_et.strftime('%H:%M:%S')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("😴 לא נמצאו מועמדים למסחר")
    lines.append("")
    lines.append("🔍 סיבות אפשריות:")
    lines.append("  • מחוץ לשעות הפעילות (08:00–09:30 ET)")
    lines.append("  • אין מניות עם גאפ משמעותי")
    lines.append("  • RVOL נמוך מ-3x")
    lines.append("  • Float גדול מ-50M")
    lines.append("  • הנפקה פעילה (SEC)")
    lines.append("  • אופי המניה GAP_AND_CRAP")
    lines.append("")
    if learning_mode:
        lines.append("📖 מצב למידה פעיל – המסננים מוקלים")
    else:
        lines.append("🔒 מסננים מלאים")
        lines.append("  להפעלת Debug: python main.py fullscan_v34 --manual --debug")
    lines.append("")
    lines.append("📁 לוג מלא: data/logs/")
    lines.append("")
    lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – ביצוע ידני בלבד")
    return "\n".join(lines)


# ============================================================
# DEBUG REPORT
# ============================================================

def format_debug_report(candidate: dict) -> str:
    """
    Detailed debug view for a single candidate, showing all fields.
    """
    a = candidate.get('analysis', {})
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🐞 DEBUG – {candidate['ticker']}")
    lines.append(f"ציון: {candidate.get('event_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  VWAP: ${candidate['pm_vwap']:.2f}")
    lines.append(f"📦 נפח PM: {candidate['pm_volume']:,}")
    lines.append("")

    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    lines.append("📊 נתונים בסיסיים:")
    lines.append(f"  Float: {float_val:,.0f}" if float_val else "  Float: N/A")
    lines.append(f"  Short Interest: {short*100:.1f}%" if short else "  Short Interest: N/A")
    lines.append(f"  RVOL: {rvol:.1f}x" if rvol else "  RVOL: N/A")
    lines.append("")

    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append(f"🧠 Personality: {personality.get('personality', 'NEUTRAL')} (Failure: {personality.get('failure_rate', 0):.1f}%)")

    catalyst = a.get('catalyst', {})
    lines.append(f"🔬 Catalyst: {catalyst.get('type', 'UNKNOWN')} (Score: {catalyst.get('score', 0)}/10)")

    sent = a.get('sentiment', {})
    lines.append(f"💬 Sentiment: {sent.get('bull_pct', 0):.0f}% Bull / {sent.get('bear_pct', 0):.0f}% Bear")

    sec = a.get('sec_risk', {})
    lines.append(f"⚠️ SEC Risk: {sec.get('risk_level', 'NONE')} – {sec.get('filing_type', 'No filing')}")
    lines.append("")

    lines.append("🎯 תוכנית מסחר:")
    if candidate.get('entry'):
        lines.append(f"  כניסה: ${candidate['entry']:.2f} | סטופ: ${candidate['stop']:.2f}")
        lines.append(f"  יעד 1: ${candidate['target_1']:.2f} ({candidate.get('risk_reward_1', 0):.1f}R)")
        lines.append(f"  יעד 2: ${candidate['target_2']:.2f} ({candidate.get('risk_reward_2', 0):.1f}R)")
        lines.append(f"  מניות: {candidate.get('position_size', 0)}")
    else:
        lines.append("  ❌ אין תוכנית מסחר תקפה")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ============================================================
# LEGACY FORMATS (V3.0–V3.2 – kept for compatibility)
# ============================================================

def format_decision_card(stock_data: dict, quant_data: dict, ai_decision: dict) -> str:
    """Legacy V3.0 format."""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    ticker = stock_data.get("ticker", "???")
    price = stock_data.get("price", 0)
    gap = stock_data.get("gap_pct", 0)
    decision = ai_decision.get("decision", "HOLD")
    score = ai_decision.get("score", 0)
    reasoning = ai_decision.get("reasoning", "No reasoning provided.")
    regime = quant_data.get("regime", "NEUTRAL")
    entry = quant_data.get("entry", 0)
    stop = quant_data.get("stop", 0)
    tp1 = quant_data.get("tp1", 0)
    tp2 = quant_data.get("tp2", 0)
    lines = [
        "🚀 <b>DAYS-BOT V3.0 – DECISION</b>",
        f"📅 {datetime.now(ET).strftime('%Y-%m-%d')}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
        f"<b>{ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%",
        f"📊 Regime: {regime}",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>DECISION: {decision}</b>",
        f"🏆 Score: {score}/100",
        "━━━━━━━━━━━━━━━━━━",
        "📊 <b>Trade Plan</b>",
        f"Entry: ${entry:.2f}",
        f"Stop:  ${stop:.2f}",
        f"TP1:   ${tp1:.2f}",
        f"TP2:   ${tp2:.2f}",
        "━━━━━━━━━━━━━━━━━━",
        f"🧠 <b>AI Analysis</b>",
        reasoning,
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ <b>MANUAL EXECUTION</b>",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_trade_card_v31(plan: dict) -> str:
    """Legacy V3.1 format."""
    lines = []
    lines.append("🚨 DAYS-BOT V3.1")
    lines.append("")
    lines.append(f"🏆 TOP SETUP")
    lines.append("")
    lines.append(f"{plan['ticker']}")
    lines.append(f"${plan['price']:.2f}")
    lines.append(f"Gap {plan.get('gap_pct', 0):+.1f}%")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📊 SETUP")
    lines.append(f"Score: {plan.get('opportunity_score', 0):.0f}/100")
    lines.append(f"Grade: {plan.get('grade', 'N/A')}")
    lines.append(f"PM Volume: {plan.get('pm_volume', 0):,}")
    lines.append(f"PM High: ${plan.get('pm_high', 0):.2f}")
    lines.append(f"PM VWAP: ${plan.get('pm_vwap', 0):.2f}")
    lines.append(f"PM Data: {plan.get('pm_data_quality', 'UNKNOWN')}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("🎯 TRADE PLAN")
    lines.append("")
    lines.append(f"DECISION: {plan.get('decision_detail', 'N/A')}")
    lines.append("")
    if plan.get('entry') is not None:
        lines.append(f"BUY TRIGGER: ${plan['entry']:.2f}")
        lines.append(f"STOP: ${plan['stop']:.2f}")
        lines.append(f"TARGET 1: ${plan['target_1']:.2f}")
        lines.append(f"TARGET 2: ${plan['target_2']:.2f}")
        lines.append(f"RISK: ${plan['risk_per_share']:.2f}/share")
        lines.append(f"R:R: {plan.get('risk_reward_1', 0):.1f}R / {plan.get('risk_reward_2', 0):.1f}R")
        lines.append("")
        lines.append("💰 POSITION")
        lines.append(f"Account: ${plan.get('account_size', 5000):,.0f}")
        lines.append(f"Risk: {plan.get('risk_pct', 0.5)*100:.1f}%")
        lines.append(f"Max Loss: ${plan.get('risk_dollars', 0):.2f}")
        lines.append(f"Suggested: {plan.get('position_shares', 0)} shares")
        lines.append("")
        lines.append("⏱ HOLD")
        lines.append(f"{plan.get('hold_type', 'NONE')}")
        lines.append(f"{plan.get('hold_min', 0)}–{plan.get('hold_max', 0)} minutes")
        lines.append("OVERNIGHT: ❌ NO")
        lines.append("")
        lines.append("🟢 CONFIRMATION")
        lines.append("✓ Break PM High")
        lines.append("✓ Volume expansion")
        lines.append("✓ Above VWAP")
        lines.append("")
        lines.append("🔴 INVALIDATION")
        for cond in plan.get('invalidation_conditions', []):
            lines.append(f"✗ {cond}")
        lines.append("")
        lines.append("🧠 AI ANALYSIS")
        lines.append("Strong gap-and-go structure. Wait for confirmation.")
        lines.append("")
        lines.append("⚠️ MANUAL EXECUTION")
        lines.append("No automatic order placed.")
    else:
        lines.append("❌ NO TRADE – " + plan.get('decision_detail', ''))
    return "\n".join(lines)
