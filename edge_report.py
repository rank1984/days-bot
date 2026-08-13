#!/usr/bin/env python3
"""
Edge Report – calculates performance metrics from completed trades
"""
from database.db import get_all_trades
import pandas as pd

def generate_edge_report():
    trades = get_all_trades()
    if not trades:
        return "📊 No trades yet."
    
    df = pd.DataFrame(trades)
    df_completed = df[df['exit_time'].notna()]
    if df_completed.empty:
        return "📊 No completed trades yet."

    total = len(df_completed)
    wins = len(df_completed[df_completed['win'] == 1])
    win_rate = (wins / total) * 100 if total > 0 else 0

    avg_win = df_completed[df_completed['win'] == 1]['pnl'].mean() if wins > 0 else 0
    avg_loss = df_completed[df_completed['win'] == 0]['pnl'].mean() if (total - wins) > 0 else 0
    profit_factor = abs(df_completed[df_completed['win'] == 1]['pnl'].sum() / df_completed[df_completed['win'] == 0]['pnl'].sum()) if (total - wins) > 0 else 0
    expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * abs(avg_loss))

    report = f"""
═══ EDGE REPORT ═══
Total Trades:     {total}
Win Rate:         {win_rate:.1f}%
Avg Winner:       {avg_win:.2f}%
Avg Loser:        {avg_loss:.2f}%
Profit Factor:    {profit_factor:.2f}
Expectancy:       {expectancy:.2f}%
"""
    return report

if __name__ == "__main__":
    print(generate_edge_report())
