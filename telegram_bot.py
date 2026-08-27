import requests
from typing import Dict, Any
from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from database.db import log_buy_trade, log_sell_trade, get_monthly_usage


def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram Mock] Token/ChatID missing. Message:\n", message)
        return True

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False


def format_review_alert(candidate: Dict[str, Any], shares: int, net_info: Dict[str, float]) -> str:
    ticker = candidate['ticker']
    entry = candidate['entry']
    tp1 = candidate['tp1']
    stop = candidate['stop']

    msg = (
        f"🚨 **התראת REVIEW - {ticker}**\n\n"
        f"• מחיר כניסה: `${entry:.2f}`\n"
        f"• כמות מומלצת: `{shares}` מניות\n"
        f"• יעד (TP1): `${tp1:.2f}` | סטופ: `${stop:.2f}`\n"
        f"• תשואה נקייה משוערת: `{net_info['net_pct']}%` (עמלה: `${net_info['fees']:.2f}`)\n\n"
        f"👇 **לתיעוד כניסה בזמן אמת (לחץ להעתקה):**\n"
        f"`/log {ticker} {shares} {entry}`\n\n"
        f"👇 **לתיעוד יציאה (העתק והוסף מחיר ביצוע בפועל בסוף):**\n"
        f"`/close {ticker} `"
    )
    return msg


def handle_log_command(command_text: str) -> str:
    parts = command_text.strip().split()
    if len(parts) != 4:
        return "⚠️ **פורמט לא תקין לכניסה.** השתמש ב:\n`/log TICKER SHARES ENTRY_PRICE`"

    try:
        ticker = parts[1].upper()
        shares = int(parts[2])
        entry_price = float(parts[3])

        trade_id = log_buy_trade(ticker, shares, entry_price)
        ops, total_shares = get_monthly_usage()

        return (
            f"✅ **עסקת כניסה נפתחה (ID #{trade_id})**\n"
            f"• מניה: `{ticker}` | כמות: `{shares}` | מחיר: `${entry_price:.2f}`\n"
            f"📊 שימוש חודשי עדכני (ET): `{ops}` פעולות | `{total_shares}` מניות"
        )
    except Exception as e:
        return f"❌ **שגיאה ברישום כניסה:** {str(e)}"


def handle_close_command(command_text: str) -> str:
    parts = command_text.strip().split()
    if len(parts) != 3:
        return "⚠️ **פורמט לא תקין לסגירה.** השתמש ב:\n`/close TICKER EXIT_PRICE`"

    try:
        ticker = parts[1].upper()
        exit_price = float(parts[2])

        success, warning = log_sell_trade(ticker, exit_price)
        if not success:
            return f"⚠️ {warning}"

        ops, total_shares = get_monthly_usage()
        return (
            f"🏁 **עסקת `{ticker}` נסגרה בהצלחה!**{warning}\n"
            f"• מחיר יציאה בפועל: `${exit_price:.2f}`\n"
            f"📊 שימוש חודשי עדכני (ET): `{ops}` פעולות | `{total_shares}` מניות"
        )
    except Exception as e:
        return f"❌ **שגיאה ברישום יציאה:** {str(e)}"
