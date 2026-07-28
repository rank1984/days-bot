"""
Backtester – evaluates strategy performance on historical data
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any

from database.trade_db import get_all_trades

class Backtester:
    def __init__(self):
        self.trades = get_all_trades()
    
    def calculate_metrics(self) -> Dict[str, Any]:
        if not self.trades:
            return {'error': 'No trades found'}
        
        df = pd.DataFrame(self.trades)
        
        # Filter only completed trades
        df = df[df['exit_time'].notna()]
        if df.empty:
            return {'error': 'No completed trades'}
        
        total = len(df)
        wins = df[df['win'] == 1]
        losses = df[df['win'] == 0]
        
        metrics = {
            'total_trades': total,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': (len(wins) / total) * 100 if total > 0 else 0,
            'avg_pnl': df['pnl'].mean(),
            'median_pnl': df['pnl'].median(),
            'max_pnl': df['pnl'].max(),
            'min_pnl': df['pnl'].min(),
            'avg_win': wins['pnl'].mean() if not wins.empty else 0,
            'avg_loss': losses['pnl'].mean() if not losses.empty else 0,
            'profit_factor': abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 0,
            'tp1_hit_rate': (df['tp1_hit'].sum() / total) * 100 if total > 0 else 0,
            'tp2_hit_rate': (df['tp2_hit'].sum() / total) * 100 if total > 0 else 0,
            'stop_hit_rate': (df['stop_hit'].sum() / total) * 100 if total > 0 else 0,
        }
        return metrics
    
    def get_win_rate_by_param(self, param: str, bins: int = 5) -> Dict:
        df = pd.DataFrame(self.trades)
        df = df[df['exit_time'].notna()]
        if df.empty:
            return {}
        
        df['bin'] = pd.cut(df[param], bins=bins)
        result = df.groupby('bin').agg(
            win_rate=('win', 'mean'),
            count=('win', 'count')
        ).reset_index()
        
        return result.to_dict('records')
    
    def generate_report(self) -> str:
        metrics = self.calculate_metrics()
        if 'error' in metrics:
            return f"📊 Backtest Error: {metrics['error']}"
        
        lines = []
        lines.append("=" * 50)
        lines.append("📊 BACKTEST REPORT")
        lines.append("=" * 50)
        lines.append(f"Total Trades:   {metrics['total_trades']}")
        lines.append(f"Win Rate:       {metrics['win_rate']:.1f}%")
        lines.append(f"Avg P&L:        {metrics['avg_pnl']:.2f}%")
        lines.append(f"Median P&L:     {metrics['median_pnl']:.2f}%")
        lines.append(f"Max P&L:        {metrics['max_pnl']:.2f}%")
        lines.append(f"Min P&L:        {metrics['min_pnl']:.2f}%")
        lines.append(f"Profit Factor:  {metrics['profit_factor']:.2f}")
        lines.append("-" * 50)
        lines.append(f"TP1 Hit Rate:   {metrics['tp1_hit_rate']:.1f}%")
        lines.append(f"TP2 Hit Rate:   {metrics['tp2_hit_rate']:.1f}%")
        lines.append(f"Stop Hit Rate:  {metrics['stop_hit_rate']:.1f}%")
        lines.append("=" * 50)
        return "\n".join(lines)
