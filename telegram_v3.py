"""
DAYS-BOT V4.1 – Telegram Formatter
"""

import requests
from datetime import datetime
import pytz


ET = pytz.timezone(
    "America/New_York"
)


def send_message(
    token: str,
    chat_id: str,
    text: str,
) -> bool:

    if not token or not chat_id:
        print(
            "[Telegram] Missing token/chat_id"
        )
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    for parse_mode in [
        "HTML",
        None,
    ]:

        try:

            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }

            if parse_mode:
                payload["parse_mode"] = (
                    parse_mode
                )

            response = requests.post(
                url,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                return True

            print(
                "[Telegram] HTTP "
                f"{response.status_code}"
            )

        except Exception as e:
            print(
                f"[Telegram] Error: {e}"
            )

    return False


def _money(value):
    if value is None:
        return "N/A"

    try:
        value = float(value)

        if value <= 0:
            return "N/A"

        return f"${value:.2f}"

    except Exception:
        return "N/A"


def format_research_report(
    candidates: list,
    now_et: datetime,
) -> str:

    lines = []

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "🚀 DAYS-BOT V4.1 – RESEARCH SCAN"
    )

    lines.append(
        f"📅 {now_et.strftime('%d/%m/%Y')} "
        f"| 🕐 {now_et.strftime('%H:%M')} ET"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if not candidates:

        lines.append(
            "😴 לא נמצאו מועמדים"
        )

        lines.append(
            "⚠️ אין מספיק market data."
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            "⚠️ ביצוע ידני בלבד"
        )

        return "\n".join(lines)

    candidates_sorted = sorted(
        candidates,
        key=lambda x: (
            x.get(
                "composite_score",
                0,
            ),
            x.get(
                "swing_score",
                0,
            ),
        ),
        reverse=True,
    )

    top5 = candidates_sorted[:5]

    # --------------------------------------------------------
    # TOP 5
    # --------------------------------------------------------

    lines.append("")
    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )
    lines.append(
        "🏆 TOP 5 RESEARCH"
    )
    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    for i, candidate in enumerate(
        top5,
        1,
    ):

        ticker = candidate.get(
            "ticker",
            "?",
        )

        score = candidate.get(
            "composite_score",
            0,
        )

        swing_score = candidate.get(
            "swing_score",
            0,
        )

        trade_type = candidate.get(
            "trade_type",
            "WATCH",
        )

        if (
            "INTRADAY"
            in trade_type
        ):
            icon = "🟢"
        elif (
            "SWING"
            in trade_type
        ):
            icon = "🟣"
        else:
            icon = "🟡"

        lines.append(
            f"{i}️⃣ {ticker} — "
            f"{score:.0f}/100"
        )

        lines.append(
            f"{icon} {trade_type}"
        )

        lines.append(
            f"Gap: "
            f"{candidate.get('gap_pct', 0):.1f}% | "
            f"Swing: "
            f"{swing_score:.0f}"
        )

        lines.append("")

    # --------------------------------------------------------
    # Best Intraday
    # --------------------------------------------------------

    intraday = [
        c for c in top5
        if c.get(
            "trade_type"
        ) in [
            "INTRADAY",
            "BOTH",
        ]
    ]

    if intraday:

        best = intraday[0]

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            "🟢 BEST INTRADAY"
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            f"Ticker: {best['ticker']}"
        )

        lines.append(
            f"Score: "
            f"{best.get('composite_score', 0):.0f}/100"
        )

        lines.append(
            f"Gap: "
            f"{best.get('gap_pct', 0):.1f}%"
        )

        lines.append(
            f"PM Volume: "
            f"{best.get('pm_volume', 0):,}"
        )

        lines.append(
            f"Entry: "
            f"{_money(best.get('entry'))}"
        )

        lines.append(
            f"Stop:  "
            f"{_money(best.get('stop'))}"
        )

        lines.append(
            f"T1:    "
            f"{_money(best.get('target_1'))}"
        )

        lines.append(
            f"T2:    "
            f"{_money(best.get('target_2'))}"
        )

        lines.append(
            f"Shares: "
            f"{best.get('position_size', 0)}"
        )

        lines.append(
            f"Plan: "
            f"{best.get('decision', 'NO_TRADE')}"
        )

        lines.append("")

    # --------------------------------------------------------
    # Best Swing
    # --------------------------------------------------------

    swing = [
        c for c in top5
        if c.get(
            "trade_type"
        ) in [
            "SWING_1_3D",
            "BOTH",
        ]
    ]

    if swing:

        best = swing[0]

        swing_data = best.get(
            "swing_data",
            {},
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            "🟣 BEST SWING (1–3 DAYS)"
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            f"Ticker: {best['ticker']}"
        )

        lines.append(
            f"Swing Score: "
            f"{best.get('swing_score', 0):.0f}/100"
        )

        lines.append(
            f"Entry: "
            f"{_money(best.get('entry'))}"
        )

        lines.append(
            f"Stop:  "
            f"{_money(best.get('stop'))}"
        )

        lines.append(
            f"T1:    "
            f"{_money(best.get('target_1'))}"
        )

        lines.append(
            f"T2:    "
            f"{_money(best.get('target_2'))}"
        )

        lines.append(
            f"Trend: "
            f"{'🟢' if swing_data.get('above_20') else '🔴'} "
            f"20 EMA"
        )

        lines.append(
            f"RS vs SPY: "
            f"{swing_data.get('rs_vs_spy', 0):.1f}%"
        )

        lines.append(
            f"Structure: "
            f"{swing_data.get('structure', 'N/A')}"
        )

        lines.append("")

    # --------------------------------------------------------
    # Decision
    # --------------------------------------------------------

    trade_candidates = [
        c for c in top5
        if c.get(
            "trade_type"
        ) in [
            "INTRADAY",
            "SWING_1_3D",
            "BOTH",
        ]
    ]

    if trade_candidates:

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            "✅ DECISION: "
            "TRADE OPPORTUNITIES FOUND"
        )

        lines.append(
            "⚠️ Entry is conditional — "
            "wait for confirmation."
        )

    else:

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        lines.append(
            "🟡 DECISION: WATCHLIST"
        )

        lines.append(
            "Top 5 are the strongest "
            "research candidates."
        )

        lines.append(
            "No automatic trade signal."
        )

    lines.append("")

    lines.append(
        "⏳ Next scan: 09:30 ET"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "⚠️ MANUAL EXECUTION ONLY"
    )

    return "\n".join(lines)
