import sqlite3
import pandas as pd

def get_win_rate_by_param(param, bins):
    conn = sqlite3.connect("data/alerts.db")
    df = pd.read_sql("SELECT * FROM trades", conn)
    conn.close()
    
    if df.empty:
        return {}
    
    df['bin'] = pd.cut(df[param], bins)
    result = df.groupby('bin').agg(
        win_rate=('win', 'mean'),
        count=('win', 'count')
    ).reset_index()
    
    return result.to_dict('records')
