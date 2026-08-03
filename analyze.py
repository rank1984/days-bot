"""
Performance Analytics – analyzes trades from database
"""
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "data/alerts.db"  # או data/trades.db

def get_trades_df():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trades", conn)
    conn.close()
    return df

def analyze_performance():
    df = get_trades_df()
    if df.empty:
        print("📊 No trades yet.")
        return
    
    # Filter only completed trades
    df_completed = df[df['exit_time'].notna()]
    if df_completed.empty:
        print("📊 No completed trades yet.")
        return
    
    total = len(df_completed)
    wins = len(df_completed[df_completed['win'] == 1])
    win_rate = (wins / total) * 100 if total > 0 else 0
    
    print("=" * 50)
    print("📊 PERFORMANCE ANALYTICS")
    print("=" * 50)
    print(f"Total Trades:    {total}")
    print(f"Wins:            {wins}")
    print(f"Losses:          {total - wins}")
    print(f"Win Rate:        {win_rate:.1f}%")
    print(f"Avg P&L:         {df_completed['pnl'].mean():.2f}%")
    print(f"Total P&L:       {df_completed['pnl'].sum():.2f}%")
    print(f"Max Gain:        {df_completed['pnl'].max():.2f}%")
    print(f"Max Loss:        {df_completed['pnl'].min():.2f}%")
    
    # TP/Stop hit rates
    tp1_hit = df_completed['tp1_hit'].sum() if 'tp1_hit' in df_completed else 0
    tp2_hit = df_completed['tp2_hit'].sum() if 'tp2_hit' in df_completed else 0
    stop_hit = df_completed['stop_hit'].sum() if 'stop_hit' in df_completed else 0
    
    print("-" * 50)
    print(f"TP1 Hit Rate:    {(tp1_hit/total)*100:.1f}%")
    print(f"TP2 Hit Rate:    {(tp2_hit/total)*100:.1f}%")
    print(f"Stop Hit Rate:   {(stop_hit/total)*100:.1f}%")
    print("=" * 50)

if __name__ == "__main__":
    analyze_performance()
