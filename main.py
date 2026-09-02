"""
DAYS-BOT V4.1 – RESEARCH ENGINE
Intraday + Swing 1–3D

Manual execution only.
No automatic orders.
"""

import sys
from pathlib import Path
from datetime import datetime

import pytz


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(
    0,
    str(BASE_DIR),
)

ET = pytz.timezone(
    "America/New_York"
)


from utils.config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)

from scanner.premarket import (
    scan_premarket,
)

from scanner.full_scan_v34 import (
    full_scan_v34,
)

from scanner.swing_engine import (
    calculate_swing_score,
)

from database.db import (
    init_db,
    save_alert,
)

from telegram_v3 import (
    send_message,
    format_research_report,
)


def _safe_swing(candidate):

    try:

        result = calculate_swing_score(
            candidate
        )

        if not isinstance(
            result,
            dict,
        ):
            return {
                "swing_score": 0,
                "swing_type": "INVALID",
            }

        return result

    except Exception as e:

        print(
            f"[Main] Swing error "
            f"{candidate.get('ticker')}: {e}"
        )

        return {
            "swing_score": 0,
            "swing_type": "ERROR",
            "error": str(e),
        }


def _classify_trade_type(candidate):

    intraday_score = float(
        candidate.get(
            "composite_score",
            0,
        )
        or 0
    )

    swing_score = float(
        candidate.get(
            "swing_score",
            0,
        )
        or 0
    )

    plan_valid = bool(
        candidate.get(
            "plan_valid",
            False,
        )
    )

    # Strong candidates.
    if (
        intraday_score >= 75
        and swing_score >= 70
    ):
        return "BOTH"

    if (
        intraday_score >= 75
        and plan_valid
    ):
        return "INTRADAY"

    if swing_score >= 70:
        return "SWING_1_3D"

    # Research/watchlist.
    if (
        intraday_score >= 60
        or swing_score >= 60
    ):
        return "WATCH"

    return "WATCH"


def run_fullscan_v34(
    manual=False,
):

    init_db()

    now_et = datetime.now(
        ET
    )

    print(
        "\n"
        + "=" * 74
    )

    print(
        "DAYS-BOT V4.1 – "
        "RESEARCH ENGINE "
        "(Intraday + Swing)"
    )

    print(
        f"Date: "
        f"{now_et.strftime('%Y-%m-%d')} "
        f"| Mode: "
        f"{'MANUAL' if manual else 'LIVE'}"
    )

    print(
        "=" * 74
    )

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------

    candidates = scan_premarket(
        now_et.strftime(
            "%Y-%m-%d"
        ),
        manual,
    )

    if not candidates:

        print(
            "[Main] No candidates found."
        )

        msg = (
            "😴 DAYS-BOT\n\n"
            "לא נמצאו מועמדים.\n"
            "אין מספיק market data כרגע.\n\n"
            "⚠️ אין לבצע עסקה על בסיס "
            "סריקה ריקה."
        )

        send_message(
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID,
            msg,
        )

        return

    print(
        f"[Main] Discovery returned "
        f"{len(candidates)} candidates"
    )

    # --------------------------------------------------------
    # Full analysis
    # --------------------------------------------------------

    top5 = full_scan_v34(
        candidates,
        manual,
    )

    if not top5:

        print(
            "[Main] Full scan returned empty."
        )

        msg = (
            "😴 DAYS-BOT\n\n"
            "ה־discovery עבד, "
            "אבל לא התקבל מועמד "
            "לניתוח מלא."
        )

        send_message(
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID,
            msg,
        )

        return

    # --------------------------------------------------------
    # Swing analysis
    # --------------------------------------------------------

    for candidate in top5:

        swing = _safe_swing(
            candidate
        )

        candidate[
            "swing_score"
        ] = float(
            swing.get(
                "swing_score",
                0,
            )
            or 0
        )

        candidate[
            "swing_data"
        ] = swing

        candidate[
            "trade_type"
        ] = _classify_trade_type(
            candidate
        )

        # ----------------------------------------------------
        # Persist
        # ----------------------------------------------------

        try:

            save_alert(
                **candidate
            )

        except Exception as e:

            # DB failure should not prevent Telegram.
            print(
                f"[Main] DB save error "
                f"{candidate.get('ticker')}: {e}"
            )

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    msg = format_research_report(
        top5,
        now_et,
    )

    telegram_ok = send_message(
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        msg,
    )

    print(
        f"[Main] Telegram sent: "
        f"{telegram_ok}"
    )

    # --------------------------------------------------------
    # Console summary
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 74
    )

    print(
        "TOP 5"
    )

    print(
        "=" * 74
    )

    for i, candidate in enumerate(
        top5,
        1,
    ):

        print(
            f"{i}. "
            f"{candidate.get('ticker')} | "
            f"Intraday="
            f"{candidate.get('composite_score', 0):.1f} | "
            f"Swing="
            f"{candidate.get('swing_score', 0):.1f} | "
            f"Type="
            f"{candidate.get('trade_type', 'WATCH')}"
        )

    print(
        "=" * 74
    )

    print(
        "⚠️ NO AUTOMATIC ORDERS – "
        "MANUAL EXECUTION ONLY"
    )

    print(
        "=" * 74
    )


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage: "
            "python main.py "
            "fullscan_v34 [--manual]"
        )

        sys.exit(1)

    manual = (
        "--manual"
        in sys.argv
    )

    run_fullscan_v34(
        manual
    )
