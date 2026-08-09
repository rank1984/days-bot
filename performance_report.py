"""
Performance Report – calculates real win rates and statistics
"""
from database.db import get_all_trades
import pandas as pd
from datetime import datetime

def generate_report():
    trades = get_all_trades()
    if not trades:
        return "📊 No trades yet."
    
    df = pd.DataFrame(trades)
    
    # סינון עסקאות עם תוצאות
    df_completed = df[df['exit_time'].notna()]
    
    if df_completed.empty:
        return "📊 No completed trades yet.\nCheck back after trades are closed."
    
    total = len(df_completed)
    wins = len(df_completed[df_completed['win'] == 1])
    win_rate = (wins / total) * 100 if total > 0 else 0
    
    avg_win = df_completed[df_completed['win'] == 1]['pnl'].mean() if wins > 0 else 0
    avg_loss = df_completed[df_completed['win'] == 0]['pnl'].mean() if (total - wins) > 0 else 0
    
    # MFE/MAE (אם קיימים)
    has_mfe = 'mfe' in df_completed.columns
    avg_mfe = df_completed['mfe'].mean() if has_mfe and not df_completed.empty else 0
    avg_mae = df_completed['mae'].mean() if has_mfe and not df_completed.empty else 0
    
    lines = []
    lines.append("=" * 50)
    lines.append("🔥 DAYS-BOT PERFORMANCE REPORT")
    lines.append("=" * 50)
    lines.append(f"Trades:         {total}")
    lines.append(f"Win Rate:       {win_rate:.1f}%")
    lines.append(f"Avg Winner:     {avg_win:.2f}%")
    lines.append(f"Avg Loser:      {avg_loss:.2f}%")
    lines.append("-" * 50)
    lines.append(f"Avg MFE:        {avg_mfe:.2f}%")
    lines.append(f"Avg MAE:        {avg_mae:.2f}%")
    lines.append("=" * 50)
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_report())
