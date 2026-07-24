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
    
    # 2. אתחול PaperTrader – עם paper=True (או False לכסף אמיתי)
    trader = PaperTrader()   # <-- עכשיו עובד!
    
    # 3. קבלת תוכניות המסחר (הלוגיקה שלך)
    # לדוגמה – שליפת תוכניות מה-TradeManager
    plans = get_trading_plans()  # או כל פונקציה שמחזירה רשימת plans
    
    trades_taken = len(plans)
    print(f"\n[Main] Trades taken: {trades_taken}")
    print("-" * 30)
    
    # 4. ביצוע העסקאות
    for plan in plans:
        ticker = plan['ticker']
        entry = plan['entry']
        
        print(f"[Main] Entering {ticker} @ ${entry:.2f}")
        
        # כניסה
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
            rvol=plan.get('raw_data', {}).get('rvol', 0.0),
            gap=plan.get('raw_data', {}).get('gap', 0.0),
            dvol=plan.get('raw_data', {}).get('dvol', 0.0),
            catalyst=plan.get('raw_data', {}).get('catalyst', '')
        )
    
    print(f"[Main] Done. {trades_taken} trades executed.")

if __name__ == "__main__":
    main()