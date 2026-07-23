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

def main():
    # 1. אתחול מסד הנתונים (יוצר את הטבלה אם לא קיימת)
    init_db()

    # 2. אתחול בוט המסחר
    trader = PaperTrader(paper=True)

    # 3. קבלת העסקאות לביצוע (הלוגיקה שלך)
    plans = get_trading_plans()
    
    # ספירת עסקאות - פותר את הבאג ב-FeedbackLearner
    trades_taken = len(plans)
    print(f"\n[Main] Trades taken: {trades_taken}")
    print("-" * 30)

    # 4. מעבר על העסקאות, ביצוע ושמירה
    for plan in plans:
        ticker = plan['ticker']
        entry_price = plan['entry']
        
        print(f"[Main] Entering {ticker} @ ${entry_price:.2f}")    
        
        # --- פקודות Paper Trader ---
        trader.enter_trade(ticker, entry_price)    
        trader.set_stop_loss(ticker, plan['stop'])    
        trader.set_take_profit(ticker, plan['tp1'])    
        
        if plan.get('runner'):        
            trader.set_take_profit(ticker, plan['tp2'])

        # --- שמירה למסד הנתונים ---
        save_trade(
            ticker=ticker,
            entry=entry_price,
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

if __name__ == "__main__":
    main()
