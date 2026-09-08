"""
DAYS-BOT V5.0.4 – Replay Engine
Saves candidate snapshot at scan time for future performance tracking.
"""
import json
from pathlib import Path
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")
REPLAY_PATH = Path(__file__).resolve().parent.parent / "data" / "replay"


def save_candidate_snapshot(candidate: dict):
    """Save candidate data at scan time for future replay."""
    try:
        REPLAY_PATH.mkdir(parents=True, exist_ok=True)
        today = datetime.now(ET).strftime("%Y-%m-%d")
        path = REPLAY_PATH / f"{today}.json"

        data = []
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
            except:
                data = []

        # Build snapshot from available fields
        snapshot = {
            "timestamp": datetime.now(ET).isoformat(),
            "ticker": candidate.get('ticker'),
            "price": candidate.get('price'),
            "gap_pct": candidate.get('gap_pct'),
            "pm_volume": candidate.get('pm_volume'),
            "float": candidate.get('float'),
            "short_interest": candidate.get('short_interest'),
            "catalyst_type": candidate.get('catalyst_type'),
            "catalyst_score": candidate.get('catalyst_score'),
            "early_score": candidate.get('early_score'),
            "early_state": candidate.get('early_state'),
            "swing_score": candidate.get('swing_score'),
            "swing_qualified": candidate.get('swing_qualified', False),
            "composite_score": candidate.get('composite_score'),
            "entry": candidate.get('entry'),
            "stop": candidate.get('stop'),
            "target_1": candidate.get('target_1'),
            "target_2": candidate.get('target_2'),
            "data_status": candidate.get('data_status'),
            "trade_type": candidate.get('trade_type'),
            "sec_risk_level": candidate.get('sec_risk_level'),
            "spread_pct": candidate.get('spread_pct'),
        }

        data.append(snapshot)

        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    except Exception as e:
        print(f"[Replay] Error saving {candidate.get('ticker')}: {e}")
