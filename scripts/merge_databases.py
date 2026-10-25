#!/usr/bin/env python3
"""
merge_databases.py — merge two DAYS-BOT SQLite databases safely.

Strategy:
  • OLD DB is the base (preserves all history + 176 outcomes)
  • NEW DB snapshots are copied with FRESH IDs starting at max(old) + 1
  • Duplicates detected by (ticker, scan_date) — skipped, never overwritten
  • NEW outcomes are NOT copied (they're PENDING; evaluator handles them)
  • NEW alerts are copied only if their snapshot was actually merged

Usage:
    python3 scripts/merge_databases.py <old.db> <new.db> <out.db>
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys


def table_columns(conn: sqlite3.Connection, schema: str | None, table: str) -> list[str]:
    if schema:
        rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    else:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def safe_attach(conn: sqlite3.Connection, path: str) -> None:
    # SQLite does not allow parameterized ATTACH — escape single quotes manually.
    safe = path.replace("'", "''")
    conn.execute(f"ATTACH DATABASE '{safe}' AS new_db")


def merge(old_path: str, new_path: str, out_path: str) -> None:
    print(f"[merge] old={old_path}")
    print(f"[merge] new={new_path}")
    print(f"[merge] out={out_path}")

    if not os.path.exists(old_path):
        raise SystemExit(f"[merge] FATAL: old DB missing at {old_path}")
    if not os.path.exists(new_path):
        raise SystemExit(f"[merge] FATAL: new DB missing at {new_path}")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    shutil.copy(old_path, out_path)
    print(f"[merge] copied old → {out_path}")

    conn = sqlite3.connect(out_path)
    conn.row_factory = sqlite3.Row

    safe_attach(conn, new_path)
    print(f"[merge] attached new DB")

    # ---- schema check ----
    old_cols = table_columns(conn, None, "snapshots")
    new_cols = table_columns(conn, "new_db", "snapshots")
    only_old = set(old_cols) - set(new_cols)
    only_new = set(new_cols) - set(old_cols)
    if only_old or only_new:
        print(f"[merge] WARNING: schema drift")
        if only_old:
            print(f"[merge]   only in old: {sorted(only_old)}")
        if only_new:
            print(f"[merge]   only in new: {sorted(only_new)}")
    cols = [c for c in old_cols if c in set(new_cols)]
    print(f"[merge] using {len(cols)} common columns")

    # ---- existing (ticker, scan_date) pairs ----
    existing = set()
    for r in conn.execute("SELECT ticker, scan_date FROM snapshots"):
        existing.add((r["ticker"], r["scan_date"]))
    print(f"[merge] existing (ticker, scan_date) pairs: {len(existing)}")

    # ---- max snapshot_id ----
    max_id = conn.execute(
        "SELECT COALESCE(MAX(snapshot_id), 0) FROM snapshots"
    ).fetchone()[0]
    print(f"[merge] max snapshot_id in old: {max_id}")

    # ---- fetch new snapshots ----
    select_cols = ",".join(f'"{c}"' for c in cols)
    new_rows = conn.execute(
        f"SELECT {select_cols} FROM new_db.snapshots"
    ).fetchall()
    print(f"[merge] new snapshots to consider: {len(new_rows)}")

    ticker_idx = cols.index("ticker")
    scan_date_idx = cols.index("scan_date")
    snap_id_idx = cols.index("snapshot_id") if "snapshot_id" in cols else None

    inserted = 0
    skipped = 0
    id_map: dict[int, int] = {}  # new_db.snapshot_id → merged snapshot_id

    for row in new_rows:
        ticker = row[ticker_idx]
        scan_date = row[scan_date_idx]
        if (ticker, scan_date) in existing:
            skipped += 1
            continue

        max_id += 1
        values = []
        for i, c in enumerate(cols):
            if c == "snapshot_id":
                values.append(max_id)
            else:
                values.append(row[i])

        quoted = ",".join(f'"{c}"' for c in cols)
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO snapshots ({quoted}) VALUES ({placeholders})", values
        )
        inserted += 1
        existing.add((ticker, scan_date))

        if snap_id_idx is not None:
            id_map[row[snap_id_idx]] = max_id

    print(f"[merge] snapshots inserted: {inserted}")
    print(f"[merge] snapshots skipped (duplicate): {skipped}")

    # ---- merge alerts (only those whose snapshot was merged) ----
    if id_map:
        try:
            old_alert_cols = table_columns(conn, None, "alerts")
            new_alert_cols = table_columns(conn, "new_db", "alerts")
            common = [c for c in old_alert_cols if c in set(new_alert_cols)]

            max_alert_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM alerts"
            ).fetchone()[0]

            new_alerts = conn.execute("SELECT * FROM new_db.alerts").fetchall()
            print(f"[merge] new alerts to consider: {len(new_alerts)}")

            alerts_inserted = 0
            for r in new_alerts:
                if "snapshot_id" not in r.keys():
                    continue
                orig = r["snapshot_id"]
                if orig not in id_map:
                    continue

                max_alert_id += 1
                values = []
                for c in common:
                    if c == "id":
                        values.append(max_alert_id)
                    elif c == "snapshot_id":
                        values.append(id_map[orig])
                    else:
                        values.append(r[c])

                quoted = ",".join(f'"{c}"' for c in common)
                placeholders = ",".join("?" for _ in common)
                conn.execute(
                    f"INSERT INTO alerts ({quoted}) VALUES ({placeholders})", values
                )
                alerts_inserted += 1

            print(f"[merge] alerts inserted: {alerts_inserted}")
        except sqlite3.OperationalError as e:
            print(f"[merge] WARN: could not merge alerts: {e}")

    conn.commit()

    # ---- final verification ----
    final_snaps = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    final_out = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    final_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    print(f"[merge] FINAL: snapshots={final_snaps} outcomes={final_out} alerts={final_alerts}")

    conn.execute("DETACH DATABASE new_db")
    conn.close()
    print("[merge] DONE")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <old.db> <new.db> <out.db>", file=sys.stderr)
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2], sys.argv[3])
