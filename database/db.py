"""
DAYS-BOT V5.0.5.2 – Database (Fixed)
Uses named placeholders to prevent column count mismatches.
"""
import os
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"


def get_connection():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT,
            price REAL,
            gap_pct REAL,
            spread_pct REAL,
            pm_volume INTEGER,
            pm_bars INTEGER,
            pm_high REAL,
            pm_low REAL,
            pm_vwap REAL,
            pm_dist_signed REAL,
            pm_high_dist REAL,
            pm_data_quality TEXT,
            pm_volume_status TEXT,
            pm_source TEXT,
            rvol REAL,
            rvol_status TEXT,
            rvol_method TEXT,
            catalyst_score REAL,
            catalyst_type TEXT,
            catalyst_summary TEXT,
            sec_risk_level TEXT,
            sec_has_offering INTEGER,
            corporate_action INTEGER,
            corporate_action_type TEXT,
            halt_flag INTEGER,
            liquidity_gate_passed INTEGER,
            liquidity_reasons TEXT,
            float REAL,
            short_interest REAL,
            short_ratio REAL,
            early_score REAL,
            early_state TEXT,
            early_components TEXT,
            swing_score REAL,
            qualified INTEGER,
            data_status TEXT,
            data_completeness TEXT,
            plan_valid INTEGER,
            plan_error TEXT,
            trade_type TEXT,
            decision TEXT,
            entry REAL,
            stop REAL,
            target_1 REAL,
            target_2 REAL,
            risk_per_share REAL,
            position_size INTEGER,
            max_loss REAL,
            hold_type TEXT,
            hold_min INTEGER,
            hold_max INTEGER,
            risk_model TEXT,
            spread_status TEXT,
            composite_score REAL,
            score_status TEXT,
            strategy_version TEXT,
            data_version TEXT,
            mode TEXT,
            scan_date TEXT,
            source TEXT,
            rvol_calc REAL,
            rs_score REAL,
            sentiment_stocktwits REAL,
            sentiment_google_trends REAL,
            news_headlines TEXT,
            raw_candidate_json TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(alerts)")
    existing_cols = [row["name"] for row in cursor.fetchall()]

    columns_to_add = [
        ("pm_low", "REAL"),
        ("pm_volume_status", "TEXT"),
        ("pm_source", "TEXT"),
        ("rvol_method", "TEXT"),
        ("catalyst_type", "TEXT"),
        ("catalyst_summary", "TEXT"),
        ("sec_risk_level", "TEXT"),
        ("sec_has_offering", "INTEGER"),
        ("corporate_action", "INTEGER"),
        ("corporate_action_type", "TEXT"),
        ("halt_flag", "INTEGER"),
        ("liquidity_gate_passed", "INTEGER"),
        ("liquidity_reasons", "TEXT"),
        ("float", "REAL"),
        ("short_interest", "REAL"),
        ("short_ratio", "REAL"),
        ("early_score", "REAL"),
        ("early_state", "TEXT"),
        ("early_components", "TEXT"),
        ("swing_score", "REAL"),
        ("qualified", "INTEGER"),
        ("data_status", "TEXT"),
        ("data_completeness", "TEXT"),
        ("plan_valid", "INTEGER"),
        ("plan_error", "TEXT"),
        ("trade_type", "TEXT"),
        ("max_loss", "REAL"),
        ("score_status", "TEXT"),
        ("scan_date", "TEXT"),
        ("source", "TEXT"),
        ("rvol_calc", "REAL"),
        ("rs_score", "REAL"),
        ("sentiment_stocktwits", "REAL"),
        ("sentiment_google_trends", "REAL"),
        ("news_headlines", "TEXT"),
        ("raw_candidate_json", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()


def save_alert(**kwargs):
    """
    Save alert using NAMED parameters.
    This prevents 'values for columns' count mismatches.
    """
    conn = get_connection()
    cursor = conn.cursor()

    def _safe(key, default=None):
        return kwargs.get(key, default)

    def _bool_to_int(v):
        if v is None:
            return None
        return 1 if v else 0

    def _to_json(v):
        if v is None:
            return None
        if isinstance(v, (list, dict)):
            try:
                return json.dumps(v, default=str)
            except Exception:
                return None
        return v

    # Extract liquidity gate info
    liq_gate = _safe("liquidity_gate")
    liq_passed = None
    liq_reasons = None
    if isinstance(liq_gate, dict):
        liq_passed = _bool_to_int(liq_gate.get("passed"))
        liq_reasons = _to_json(liq_gate.get("reasons"))

    # Full dump for debugging
    try:
        raw_json = json.dumps(kwargs, default=str)
    except Exception:
        raw_json = None

    # Build params dict with named placeholders
    params = {
        "ticker": _safe("ticker"),
        "price": _safe("price"),
        "gap_pct": _safe("gap_pct"),
        "spread_pct": _safe("spread_pct"),
        "pm_volume": _safe("pm_volume"),
        "pm_bars": _safe("pm_bars"),
        "pm_high": _safe("pm_high"),
        "pm_low": _safe("pm_low"),
        "pm_vwap": _safe("pm_vwap"),
        "pm_dist_signed": _safe("pm_dist_signed"),
        "pm_high_dist": _safe("pm_high_dist"),
        "pm_data_quality": _safe("pm_data_quality"),
        "pm_volume_status": _safe("pm_volume_status"),
        "pm_source": _safe("pm_source"),
        "rvol": _safe("rvol"),
        "rvol_status": _safe("rvol_status"),
        "rvol_method": _safe("rvol_method"),
        "catalyst_score": _safe("catalyst_score"),
        "catalyst_type": _safe("catalyst_type"),
        "catalyst_summary": _safe("catalyst_summary"),
        "sec_risk_level": _safe("sec_risk_level"),
        "sec_has_offering": _bool_to_int(_safe("sec_has_offering")),
        "corporate_action": _bool_to_int(_safe("corporate_action")),
        "corporate_action_type": _safe("corporate_action_type"),
        "halt_flag": _bool_to_int(_safe("halt_flag")),
        "liquidity_gate_passed": liq_passed,
        "liquidity_reasons": liq_reasons,
        "float": _safe("float"),
        "short_interest": _safe("short_interest"),
        "short_ratio": _safe("short_ratio"),
        "early_score": _safe("early_score"),
        "early_state": _safe("early_state"),
        "early_components": _to_json(_safe("early_components")),
        "swing_score": _safe("swing_score"),
        "qualified": _bool_to_int(_safe("qualified")),
        "data_status": _safe("data_status"),
        "data_completeness": _to_json(_safe("data_completeness")),
        "plan_valid": _bool_to_int(_safe("plan_valid")),
        "plan_error": _safe("plan_error"),
        "trade_type": _safe("trade_type"),
        "decision": _safe("decision"),
        "entry": _safe("entry"),
        "stop": _safe("stop"),
        "target_1": _safe("target_1"),
        "target_2": _safe("target_2"),
        "risk_per_share": _safe("risk_per_share"),
        "position_size": _safe("position_size"),
        "max_loss": _safe("max_loss"),
        "hold_type": _safe("hold_type"),
        "hold_min": _safe("hold_min"),
        "hold_max": _safe("hold_max"),
        "risk_model": _safe("risk_model"),
        "spread_status": _safe("spread_status"),
        "composite_score": _safe("composite_score"),
        "score_status": _safe("score_status"),
        "strategy_version": _safe("strategy_version"),
        "data_version": _safe("data_version"),
        "mode": _safe("mode"),
        "scan_date": _safe("scan_date"),
        "source": _safe("source"),
        "rvol_calc": _safe("rvol_calc"),
        "rs_score": _safe("rs_score"),
        "sentiment_stocktwits": _safe("sentiment_stocktwits"),
        "sentiment_google_trends": _safe("sentiment_google_trends"),
        "news_headlines": _safe("news_headlines"),
        "raw_candidate_json": raw_json,
    }

    cursor.execute("""
        INSERT INTO alerts (
            ticker, price, gap_pct, spread_pct,
            pm_volume, pm_bars, pm_high, pm_low, pm_vwap,
            pm_dist_signed, pm_high_dist, pm_data_quality,
            pm_volume_status, pm_source,
            rvol, rvol_status, rvol_method,
            catalyst_score, catalyst_type, catalyst_summary,
            sec_risk_level, sec_has_offering,
            corporate_action, corporate_action_type, halt_flag,
            liquidity_gate_passed, liquidity_reasons,
            float, short_interest, short_ratio,
            early_score, early_state, early_components,
            swing_score, qualified,
            data_status, data_completeness,
            plan_valid, plan_error, trade_type,
            decision, entry, stop, target_1, target_2,
            risk_per_share, position_size, max_loss,
            hold_type, hold_min, hold_max, risk_model,
            spread_status, composite_score, score_status,
            strategy_version, data_version, mode, scan_date, source,
            rvol_calc, rs_score,
            sentiment_stocktwits, sentiment_google_trends,
            news_headlines, raw_candidate_json
        ) VALUES (
            :ticker, :price, :gap_pct, :spread_pct,
            :pm_volume, :pm_bars, :pm_high, :pm_low, :pm_vwap,
            :pm_dist_signed, :pm_high_dist, :pm_data_quality,
            :pm_volume_status, :pm_source,
            :rvol, :rvol_status, :rvol_method,
            :catalyst_score, :catalyst_type, :catalyst_summary,
            :sec_risk_level, :sec_has_offering,
            :corporate_action, :corporate_action_type, :halt_flag,
            :liquidity_gate_passed, :liquidity_reasons,
            :float, :short_interest, :short_ratio,
            :early_score, :early_state, :early_components,
            :swing_score, :qualified,
            :data_status, :data_completeness,
            :plan_valid, :plan_error, :trade_type,
            :decision, :entry, :stop, :target_1, :target_2,
            :risk_per_share, :position_size, :max_loss,
            :hold_type, :hold_min, :hold_max, :risk_model,
            :spread_status, :composite_score, :score_status,
            :strategy_version, :data_version, :mode, :scan_date, :source,
            :rvol_calc, :rs_score,
            :sentiment_stocktwits, :sentiment_google_trends,
            :news_headlines, :raw_candidate_json
        )
    """, params)

    conn.commit()
    conn.close()
