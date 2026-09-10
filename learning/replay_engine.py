"""
DAYS-BOT V5.0.5 – Replay Engine
Saves candidate snapshots at scan time for performance tracking.

CRITICAL FIXES:
- Returns True/False to indicate success/failure
- Full error logging with ticker + exception
- Saves spread + rejection info for ALL candidates
- Handles non-serializable values safely
"""
import json
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional
import pytz

ET = pytz.timezone("America/New_York")
REPLAY_PATH = Path(__file__).resolve().parent.parent / "data" / "replay"


def _safe_value(value: Any) -> Any:
    """
    Convert non-serializable values to serializable ones.
    Handles NaN, pd.NA, numpy types, etc.
    """
    if value is None:
        return None

    # Handle numpy / pandas NaN
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return None
    except:
        pass

    # Handle pandas NA
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except:
        pass

    # Handle numpy scalars
    try:
        import numpy as np
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
    except:
        pass

    # Handle datetime
    if isinstance(value, datetime):
        return value.isoformat()

    # Handle dict
    if isinstance(value, dict):
        return {k: _safe_value(v) for k, v in value.items()}

    # Handle list/tuple
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]

    return value


def _spread_bucket(spread_pct: Optional[float]) -> str:
    """Categorize spread into buckets for later analysis."""
    if spread_pct is None:
        return "UNKNOWN"
    try:
        s = float(spread_pct)
    except (TypeError, ValueError):
        return "UNKNOWN"

    if s <= 2.0:
        return "LE_2"
    elif s <= 5.0:
        return "2_5"
    elif s <= 8.0:
        return "5_8"
    elif s <= 12.0:
        return "8_12"
    elif s <= 15.0:
        return "12_15"
    else:
        return "GT_15"


def save_candidate_snapshot(candidate: dict, top5_index: int = 0) -> bool:
    """
    Save candidate data at scan time for future replay.

    Returns:
        True on success, False on failure.
    """
    ticker = candidate.get('ticker', 'UNKNOWN')

    try:
        REPLAY_PATH.mkdir(parents=True, exist_ok=True)
        today = datetime.now(ET).strftime("%Y-%m-%d")
        path = REPLAY_PATH / f"{today}.json"

        # Load existing data
        data = []
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except Exception as load_err:
                print(f"[REPLAY WARN] Could not load existing data: {load_err}")
                data = []

        # Extract spread bucket
        spread_pct = candidate.get('spread_pct')
        spread_bucket = _spread_bucket(spread_pct)

        # Build snapshot with safe values
        snapshot = {
            "timestamp": datetime.now(ET).isoformat(),
            "ticker": ticker,
            "top5_index": top5_index,

            # Price & Gap
            "price": _safe_value(candidate.get('price')),
            "gap_pct": _safe_value(candidate.get('gap_pct')),

            # PM Data
            "pm_volume": _safe_value(candidate.get('pm_volume')),
            "pm_volume_status": candidate.get('pm_volume_status'),
            "pm_high": _safe_value(candidate.get('pm_high')),
            "pm_low": _safe_value(candidate.get('pm_low')),
            "pm_vwap": _safe_value(candidate.get('pm_vwap')),
            "pm_source": candidate.get('pm_source'),
            "pm_data_quality": candidate.get('pm_data_quality'),

            # Float & Short
            "float": _safe_value(candidate.get('float')),
            "short_interest": _safe_value(candidate.get('short_interest')),
            "short_ratio": _safe_value(candidate.get('short_ratio')),

            # Spread (with bucket)
            "spread_pct": _safe_value(spread_pct),
            "spread_bucket": spread_bucket,

            # Catalyst / SEC
            "catalyst_type": candidate.get('catalyst_type'),
            "catalyst_score": _safe_value(candidate.get('catalyst_score')),
            "sec_risk_level": candidate.get('sec_risk_level'),
            "sec_has_offering": candidate.get('sec_has_offering'),

            # Corporate Action
            "corporate_action": candidate.get('corporate_action', False),
            "corporate_action_type": candidate.get('corporate_action_type'),

            # Scores
            "early_score": _safe_value(candidate.get('early_score')),
            "early_state": candidate.get('early_state'),
            "swing_score": _safe_value(candidate.get('swing_score')),
            "composite_score": _safe_value(candidate.get('composite_score')),
            "qualified": candidate.get('qualified', False),

            # Trade Plan
            "entry": _safe_value(candidate.get('entry')),
            "stop": _safe_value(candidate.get('stop')),
            "target_1": _safe_value(candidate.get('target_1')),
            "target_2": _safe_value(candidate.get('target_2')),

            # Status
            "data_status": candidate.get('data_status'),
            "trade_type": candidate.get('trade_type'),

            # Rejection tracking (for analysis)
            "liquidity_gate": candidate.get('liquidity_gate'),
            "plan_error": candidate.get('plan_error'),
        }

        data.append(snapshot)

        # Write to file
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"[REPLAY ERROR] {ticker} | {type(e).__name__}: {e}")
        # Print first few lines of traceback for debugging
        tb_lines = traceback.format_exc().split('\n')
        for line in tb_lines[:5]:
            if line.strip():
                print(f"[REPLAY TRACE] {line}")
        return False


def get_replay_data(date_str: str = None) -> list:
    """Load replay data for a specific date."""
    if date_str is None:
        date_str = datetime.now(ET).strftime("%Y-%m-%d")
    path = REPLAY_PATH / f"{date_str}.json"
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[REPLAY] Error reading {path}: {e}")
            return []
    return []


def update_replay_results(date_str: str = None):
    """
    Placeholder for V5.0.6 – will fill MFE/MAE/etc.
    """
    print("[Replay] update_replay_results – to be implemented in V5.0.6")
    return
