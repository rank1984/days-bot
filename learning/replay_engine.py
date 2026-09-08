"""
DAYS-BOT V5.0.4 – Replay Engine
Saves candidate snapshots at scan time for performance tracking.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf
import pytz

ET = pytz.timezone("America/New_York")
REPLAY_PATH = Path(__file__).resolve().parent.parent / "data" / "replay"


def save_candidate_snapshot(candidate: dict, top5_index: int = 0):
    """
    Save candidate data at scan time for future replay.
    Called from main.py for Top 5 candidates.
    """
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

    # Extract only what we need for replay
    snapshot = {
        "timestamp": datetime.now(ET).isoformat(),
        "ticker": candidate.get('ticker'),
        "price": candidate.get('price'),
        "gap_pct": candidate.get('gap_pct'),
        "pm_volume": candidate.get('pm_volume'),
        "float": candidate.get('float'),
        "short_interest": candidate.get('short_interest'),
        "catalyst_type": candidate.get('catalyst_type'),
        "early_score": candidate.get('early_score'),
        "early_state": candidate.get('early_state'),
        "swing_score": candidate.get('swing_score'),
        "qualified": candidate.get('qualified', False),
        "composite_score": candidate.get('composite_score'),
        "entry": candidate.get('entry'),
        "stop": candidate.get('stop'),
        "target_1": candidate.get('target_1'),
        "target_2": candidate.get('target_2'),
        "data_status": candidate.get('data_status'),
        "trade_type": candidate.get('trade_type'),
        "top5_index": top5_index,
    }

    data.append(snapshot)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"[Replay] Saved snapshot for {candidate.get('ticker')} (Top {top5_index+1})")


def get_replay_data(date_str: str = None) -> list:
    """Load replay data for a specific date."""
    if date_str is None:
        date_str = datetime.now(ET).strftime("%Y-%m-%d")
    path = REPLAY_PATH / f"{date_str}.json"
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return []


def update_replay_results(date_str: str = None):
    """
    Update candidates with actual performance after 1, 2, 3 days.
    Called manually or as a separate workflow.
    """
    data = get_replay_data(date_str)
    if not data:
        return

    for item in data:
        ticker = item.get('ticker')
        if not ticker:
            continue

        entry = item.get('price', 0)
        if entry <= 0:
            continue

        # Fetch daily data for 3 days after scan
        scan_time = datetime.fromisoformat(item['timestamp'])
        end_date = scan_time + timedelta(days=3)

        try:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if df.empty:
                continue

            # Find closest dates
            idx = df.index
            scan_date = scan_time.date()

            # Filter to dates >= scan_date
            future = df[df.index >= pd.Timestamp(scan_date)]
            if len(future) < 2:
                continue

            # Day 1 performance
            day1_close = future['Close'].iloc[1] if len(future) > 1 else None
            day2_close = future['Close'].iloc[2] if len(future) > 2 else None
            day3_close = future['Close'].iloc[3] if len(future) > 3 else None

            item['day1_close'] = day1_close
            item['day2_close'] = day2_close
            item['day3_close'] = day3_close

            if day1_close:
                item['day1_return'] = round((day1_close - entry) / entry * 100, 2)
            if day2_close:
                item['day2_return'] = round((day2_close - entry) / entry * 100, 2)
            if day3_close:
                item['day3_return'] = round((day3_close - entry) / entry * 100, 2)

            # Check targets
            high = future['High'].max() if not future.empty else 0
            if high > 0 and entry > 0:
                item['max_gain'] = round((high - entry) / entry * 100, 2)

            low = future['Low'].min() if not future.empty else 0
            if low > 0 and entry > 0:
                item['max_loss'] = round((low - entry) / entry * 100, 2)

        except Exception as e:
            print(f"[Replay] Error updating {ticker}: {e}")

    # Save updated data
    today = datetime.now(ET).strftime("%Y-%m-%d")
    path = REPLAY_PATH / f"{today}_updated.json"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
