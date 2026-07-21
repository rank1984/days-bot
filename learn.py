"""
Run learning and optimization
"""
import sys
import os
from pathlib import Path

# הוסף את ספריית הבסיס לנתיב
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from learning.feedback import FeedbackLearner

def main():
    print("=" * 50)
    print("🧠 DAYS-BOT LEARNING MODULE")
    print("=" * 50)
    
    learner = FeedbackLearner()
    
    # בדיקת תוצאות של מועמדויות קודמות (עד 30 יום אחורה)
    print("[Learning] Checking past candidates...")
    learner.check_results(days_back=30)
    
    # דוח מלא
    report = learner.generate_report()
    print(report)
    
    # 10 המועמדויות הטובות ביותר
    print("\n🏆 TOP 10 PERFORMERS:")
    top = learner.get_top_performers(10)
    if top:
        for i, c in enumerate(top, 1):
            print(f"  {i}. {c['ticker']}  +{c.get('max_pnl', 0):.1f}%  (Gap: {c.get('gap_pct', 0):.1f}%)")
    else:
        print("  No data yet. Run main.py full first to collect candidates.")
    
    # 10 הגרועות ביותר
    print("\n📉 BOTTOM 10 PERFORMERS:")
    bottom = learner.get_bottom_performers(10)
    if bottom:
        for i, c in enumerate(bottom, 1):
            print(f"  {i}. {c['ticker']}  {c.get('max_pnl', 0):.1f}%  (Gap: {c.get('gap_pct', 0):.1f}%)")
    else:
        print("  No data yet.")
    
    print("\n" + "=" * 50)
    print("💡 Run 'python main.py full' daily to collect more data.")
    print("=" * 50)

if __name__ == "__main__":
    main()
