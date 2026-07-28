"""
Trade Analytics Engine – daily report of strategy performance
"""
import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_PATH = "data/trades.db"

class AnalyticsEngine:
    def __init__(self):
        self.df = self._load_trades()
    
    def _load_trades(self):
        if not os.path.exists(DB_PATH):
            return pd.DataFrame()
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT * FROM trades", conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()
    
    def daily_report(self) -> str:
        """דוח יומי"""
        if self.df.empty:
            return "📊 No trades yet."
        
        today = datetime.now().strftime('%Y-%m-%d')
        if 'entry_time' not in self.df.columns:
            return "📊 Invalid database structure."
            
        df_today = self.df[self.df['entry_time'].astype(str).str.contains(today)]
        
        if df_today.empty:
            return f"📊 No trades for {today}"
        
        completed = df_today[df_today['exit_time'].notna()]
        if completed.empty:
            return f"📊 {len(df_today)} trades today, none completed yet."
        
        total = len(completed)
        wins = len(completed[completed['win'] == 1])
        win_rate = (wins / total) * 100 if total > 0 else 0
        avg_pnl = completed['pnl'].mean()
        total_pnl = completed['pnl'].sum()
        
        lines = []
        lines.append("=" * 50)
        lines.append(f"📊 DAILY REPORT – {today}")
        lines.append("=" * 50)
        lines.append(f"Trades:         {total}")
        lines.append(f"Wins:           {wins}")
        lines.append(f"Win Rate:       {win_rate:.1f}%")
        lines.append(f"Avg P&L:        {avg_pnl:.2f}%")
        lines.append(f"Total P&L:      {total_pnl:.2f}%")
        lines.append("=" * 50)
        return "\n".join(lines)
    
    def best_filters(self) -> str:
        """מחזיר אילו פילטרים הכי מנבאים Win"""
        if self.df.empty or 'exit_time' not in self.df.columns:
            return "📊 No completed trades."
            
        df = self.df[self.df['exit_time'].notna()]
        if df.empty:
            return "📊 No completed trades."
        
        lines = []
        lines.append("=" * 50)
        lines.append("🏆 BEST FILTERS")
        lines.append("=" * 50)
        
        if 'score' in df.columns:
            score_bins = pd.cut(df['score'], bins=4)
            score_win = df.groupby(score_bins)['win'].mean()
            lines.append("\n📊 Score:")
            for k, v in score_win.items():
                lines.append(f"  {k}: {v*100:.0f}%")
                
        if 'rvol' in df.columns:
            rvol_bins = pd.cut(df['rvol'], bins=4)
            rvol_win = df.groupby(rvol_bins)['win'].mean()
            lines.append("\n📊 RVOL:")
            for k, v in rvol_win.items():
                lines.append(f"  {k}: {v*100:.0f}%")
                
        if 'gap' in df.columns:
            gap_bins = pd.cut(df['gap'], bins=4)
            gap_win = df.groupby(gap_bins)['win'].mean()
            lines.append("\n📊 Gap:")
            for k, v in gap_win.items():
                lines.append(f"  {k}: {v*100:.0f}%")
                
        lines.append("=" * 50)
        return "\n".join(lines)
