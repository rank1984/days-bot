"""
Performance Dashboard – daily and weekly reports
"""
from database.trade_db import get_all_trades
from backtest.backtester import Backtester
from datetime import datetime, timedelta
import pandas as pd

def generate_daily_report():
    trades = get_all_trades()
    if not trades:
        return "📊 No trades yet."
    
    df = pd.DataFrame(trades)
    today = datetime.now().strftime('%Y-%m-%d')
    df_today = df[df['entry_time'].str.contains(today)]
    
    if df_today.empty:
        return f"📊 No trades for {today}"
    
    completed = df_today[df_today['exit_time'].notna()]
    if completed.empty:
        return f"📊 {len(df_today)} trades today, none completed yet."
    
    wins = len(completed[completed['win'] == 1])
    total = len(completed)
    pnl = completed['pnl'].sum()
    
    lines = []
    lines.append("=" * 50)
    lines.append(f"📊 DAILY REPORT – {today}")
    lines.append("=" * 50)
    lines.append(f"Trades:         {total}")
    lines.append(f"Wins:           {wins}")
    lines.append(f"Win Rate:       {(wins/total)*100:.1f}%")
    lines.append(f"Total P&L:      {pnl:.2f}%")
    lines.append("=" * 50)
    return "\n".join(lines)

def generate_weekly_report():
    trades = get_all_trades()
    if not trades:
        return "📊 No trades yet."
    
    df = pd.DataFrame(trades)
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    df_week = df[df['entry_time'] >= week_ago]
    completed = df_week[df_week['exit_time'].notna()]
    
    if completed.empty:
        return "📊 No completed trades this week."
    
    total = len(completed)
    wins = len(completed[completed['win'] == 1])
    pnl = completed['pnl'].sum()
    
    lines = []
    lines.append("=" * 50)
    lines.append("📊 WEEKLY REPORT")
    lines.append("=" * 50)
    lines.append(f"Trades:         {total}")
    lines.append(f"Wins:           {wins}")
    lines.append(f"Win Rate:       {(wins/total)*100:.1f}%")
    lines.append(f"Total P&L:      {pnl:.2f}%")
    lines.append("=" * 50)
    return "\n".join(lines)
