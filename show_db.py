import sqlite3

conn = sqlite3.connect('data/alerts.db')

print("=" * 50)
print("WATCHLIST:")
print("=" * 50)
cursor = conn.execute("SELECT ticker, price, gap_pct, score, rvol, pm_high, trigger_price, status, hits FROM watchlist ORDER BY score DESC;")
for row in cursor:
    print(f"{row[0]} | ${row[1]:.2f} | Gap: {row[2]:.1f}% | Score: {row[3]:.0f} | RVOL: {row[4]:.1f}x | PM High: ${row[5]:.2f} | Trigger: ${row[6]:.2f} | {row[7]} | Hits: {row[8]}")

print("\n" + "=" * 50)
print("TRADES:")
print("=" * 50)
cursor = conn.execute("SELECT ticker, entry_price, exit_price, pnl, win, mfe, mae FROM trades;")
for row in cursor:
    print(f"{row[0]} | Entry: ${row[1]:.2f} | Exit: ${row[2]:.2f} | PnL: {row[3]:.2f}% | Win: {row[4]} | MFE: {row[5]:.2f}% | MAE: {row[6]:.2f}%")

conn.close()
