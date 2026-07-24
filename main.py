# ודא שהנתיבים האלה תואמים למבנה התיקיות שלך
from paper_trader.paper_trader import PaperTrader
from database.db import init_db, save_trade

def get_trading_plans():
    """
    כאן אמורה להיות הלוגיקה שלך שמייצרת את העסקאות.
    לצורך הדוגמה, הנה רשימה של plan אחד לדוגמה כדי שהקוד ירוץ בלי שגיאות.
    """
    # תחליף את החלק הזה בקוד האמיתי שמייצר את ה-plans
    mock_plans = [
        {
            'ticker': 'BTC/USDT',
            'entry': 65000.00,
            'stop': 64000.00,
            'tp1': 67000.00,
            'tp2': 69000.00,
            'runner': True,
            'rr1': 2.0,
            'rr2': 4.0,
            'quality_score': 8.5,
            'raw_data': {
                'rvol': 1.5,
                'gap': 2.1,
                'dvol': 5000000,
                'catalyst': 'News breakout'
            }
        }
    ]
    return mock_plans

    # ... imports קיימים ...
from paper_trader.paper_trader import PaperTrader
from database.db import init_db, save_trade

def main():
    # 1. אתחול מסד הנתונים
    init_db()
    
    # 2. אתחול PaperTrader
    trader = PaperTrader()
    
    # 3. קבלת תוכניות המסחר (מהסורק האמיתי)
    today = datetime.now().strftime("%Y-%m-%d")
    candidates = scan_premarket(today)
    
    if not candidates:
        # שליחת הודעה "אין מועמדויות"
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return
    
    # 4. שליחת רשימת המועמדויות לטלגרם (התראה)
    msg = format_preopen_list(candidates, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    print(f"[Main] Sent {len(candidates)} candidates summary to Telegram")
    
    # 5. יצירת תוכניות מסחר (רק למניות, לא קריפטו)
    manager = TradeManager()
    plans = []
    for c in candidates[:5]:  # 5 הראשונות
        # דילוג על קריפטו
        if '/' in c['ticker'] or 'USDC' in c['ticker'] or 'USDT' in c['ticker']:
            continue
        plan = manager.generate_plan(c)
        if plan:
            plans.append(plan)
    
    # 6. ביצוע עסקאות (Paper Trading)
    trades_taken = len(plans)
    print(f"\n[Main] Trades taken: {trades_taken}")
    print("-" * 30)
    
    for plan in plans:
        ticker = plan['ticker']
        entry = plan['entry']
        print(f"[Main] Entering {ticker} @ ${entry:.2f}")
        
        trader.enter_trade(ticker, entry)
        trader.set_stop_loss(ticker, plan['stop'])
        trader.set_take_profit(ticker, plan['tp1'])
        
        if plan.get('runner'):
            trader.set_take_profit(ticker, plan['tp2'])
        
        # שמירה ל-DB
        save_trade(
            ticker=ticker,
            entry=entry,
            stop=plan['stop'],
            tp1=plan['tp1'],
            tp2=plan['tp2'],
            rr1=plan.get('rr1', 0.0),
            rr2=plan.get('rr2', 0.0),
            score=plan.get('quality_score', 0.0),
            rvol=plan['raw_data'].get('rvol', 0.0),
            gap=plan['raw_data'].get('gap', 0.0),
            dvol=plan['raw_data'].get('dvol', 0.0),
            catalyst=plan['raw_data'].get('catalyst', '')
        )
    
    print(f"[Main] Done. {trades_taken} trades executed.")

if __name__ == "__main__":
    main()
