"""
Probability Engine – learns from historical trades
"""
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "data/alerts.db"  # או data/trades.db


def get_all_trades():
    """שליפת כל העסקאות מהמסד"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trades", conn)
    conn.close()
    return df


def get_win_rate_by_param(param: str, bins: int = 5) -> dict:
    """
    מחשב אחוזי הצלחה לפי פרמטר (למשל Score, RVOL, Gap)
    """
    df = get_all_trades()
    if df.empty:
        return {'error': 'No trades yet'}
    
    # מסנן רק עסקאות שהסתיימו
    df = df[df['exit_time'].notna()]
    if df.empty:
        return {'error': 'No completed trades yet'}
    
    if param not in df.columns:
        return {'error': f'Parameter {param} not found in DB'}
    
    df['bin'] = pd.cut(df[param], bins=bins)
    result = df.groupby('bin').agg(
        win_rate=('win', 'mean'),
        count=('win', 'count')
    ).reset_index()
    
    # המרה לפורמט קריא
    output = {}
    for _, row in result.iterrows():
        bin_label = f"{row['bin'].left:.1f}-{row['bin'].right:.1f}"
        output[bin_label] = {
            'win_rate': row['win_rate'] * 100,
            'count': int(row['count'])
        }
    return output


def get_best_params() -> dict:
    """מחזיר את הפרמטרים עם אחוזי ההצלחה הגבוהים ביותר"""
    params = ['score', 'rvol', 'gap', 'pm_high_dist', 'atr']
    results = {}
    
    for p in params:
        try:
            results[p] = get_win_rate_by_param(p, bins=4)
        except:
            results[p] = {'error': 'No data'}
    
    return results


def generate_report() -> str:
    """מייצר דוח המלצות"""
    df = get_all_trades()
    if df.empty:
        return "📊 No trades yet. Run more trades first."
    
    df_completed = df[df['exit_time'].notna()]
    if df_completed.empty:
        return "📊 No completed trades yet. Wait for trades to close."
    
    total = len(df_completed)
    wins = len(df_completed[df_completed['win'] == 1])
    win_rate = (wins / total) * 100 if total > 0 else 0
    avg_pnl = df_completed['pnl'].mean() if not df_completed.empty else 0
    
    lines = []
    lines.append("=" * 50)
    lines.append("📊 PROBABILITY ENGINE REPORT")
    lines.append("=" * 50)
    lines.append(f"Total Trades:     {total}")
    lines.append(f"Win Rate:         {win_rate:.1f}%")
    lines.append(f"Avg P&L:          {avg_pnl:.2f}%")
    lines.append("-" * 50)
    
    # המלצות לפי Win Rate
    if win_rate >= 60 and avg_pnl > 0:
        lines.append("🚀 RECOMMENDATION: Good strategy! Continue with current filters.")
    elif win_rate >= 50 and avg_pnl > 0:
        lines.append("📈 RECOMMENDATION: Decent. Consider tightening filters slightly.")
    elif win_rate >= 40 and avg_pnl > 0:
        lines.append("📊 RECOMMENDATION: Needs improvement. Check entry timing.")
    elif win_rate < 40 and total > 20:
        lines.append("⚠️ RECOMMENDATION: Strategy is not working. Adjust filters.")
    else:
        lines.append("📚 RECOMMENDATION: Collect more data (at least 20 trades).")
    
    # הצגת הפרמטרים הטובים ביותר
    lines.append("-" * 50)
    lines.append("🏆 TOP PARAMETERS BY WIN RATE:")
    
    for param in ['score', 'rvol', 'gap']:
        try:
            data = get_win_rate_by_param(param, bins=3)
            if data and 'error' not in data:
                best_bin = max(data, key=lambda x: data[x]['win_rate'])
                lines.append(f"  • {param}: {best_bin} → {data[best_bin]['win_rate']:.0f}% win rate")
        except:
            pass
    
    lines.append("=" * 50)
    return "\n".join(lines)


def get_win_rate_table() -> pd.DataFrame:
    """מחזיר טבלת Win Rate מלאה"""
    df = get_all_trades()
    if df.empty or df[df['exit_time'].notna()].empty:
        return pd.DataFrame({'message': ['No data']})
    
    df = df[df['exit_time'].notna()]
    
    # חישוב Win Rate לפי קבוצות
    params = ['score', 'rvol', 'gap', 'pm_high_dist']
    results = []
    
    for p in params:
        if p not in df.columns:
            continue
        df['bin'] = pd.cut(df[p], bins=4)
        grouped = df.groupby('bin').agg(
            win_rate=('win', 'mean'),
            count=('win', 'count')
        ).reset_index()
        for _, row in grouped.iterrows():
            results.append({
                'param': p,
                'range': f"{row['bin'].left:.1f}-{row['bin'].right:.1f}",
                'win_rate': row['win_rate'] * 100,
                'count': row['count']
            })
    
    return pd.DataFrame(results)
