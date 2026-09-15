"""
DAYS-BOT V5.0.6 — Report Formatting Helpers

Formats: Snapshot (S0) → Recommendation → Trigger → Outcome
Strict rules:
    NO_TRIGGER ≠ LOSS
    NOT_EXECUTABLE ≠ LOSS
    DATA_UNAVAILABLE ≠ LOSS
"""


def fmt_price(v):
    if v is None:
        return "—"
    try:
        return f"${float(v):.4f}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v, sign=False):
    if v is None:
        return "—"
    try:
        s = f"{float(v):+.2f}%" if sign else f"{float(v):.2f}%"
        return s
    except (TypeError, ValueError):
        return "—"


def fmt_int(v):
    if v is None:
        return "—"
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return "—"


def fmt_r(v, sign=True):
    if v is None:
        return "—"
    try:
        return f"{float(v):+.3f}R" if sign else f"{float(v):.3f}R"
    except (TypeError, ValueError):
        return "—"


def fmt_time(iso_str):
    if not iso_str:
        return "—"
    try:
        return iso_str.split(" ")[1] if " " in iso_str else iso_str
    except Exception:
        return iso_str


def recommendation_state(snapshot):
    """Classify snapshot into actionable tier."""
    tt = (snapshot.get("trade_type") or "").upper()
    ds = (snapshot.get("data_status") or "").upper()

    if tt == "NO_TRADE" or ds == "NO_TRADE":
        return "NO_TRADE"
    if tt in ("ACTIONABLE", "INTRADAY", "BOTH", "SWING_1_3D"):
        return "ACTIONABLE"
    if tt in ("WATCH", "RESEARCH") or ds == "WATCH":
        return "RESEARCH"
    return "OTHER"


def trigger_outcome_label(trigger, outcome):
    """
    Compute display label for trigger+outcome pair.
    Respects: NO_TRIGGER, NOT_EXECUTABLE, DATA_UNAVAILABLE are NOT losses.
    """
    if trigger is None:
        return "NO_TRIGGER"

    hit = trigger.get("hit")
    reason = None
    if trigger.get("metadata_json"):
        import json
        try:
            meta = json.loads(trigger["metadata_json"])
            reason = meta.get("reason")
        except Exception:
            pass

    if hit is None:
        if reason in ("VOLUME_UNAVAILABLE", "VWAP_UNAVAILABLE"):
            return f"DATA_UNAVAILABLE ({reason})"
        if reason == "NO_PMH":
            return "NO_PMH"
        if reason == "FETCH_FAILED":
            return "FETCH_FAILED"
        return "DATA_UNAVAILABLE"

    if hit == 0:
        if reason == "TIMEOUT":
            return "NO_TRIGGER (TIMEOUT)"
        if reason == "PULLBACK_FAILED":
            return "NO_TRIGGER (PULLBACK_FAILED)"
        return "NO_TRIGGER"

    # hit == 1 — check outcome
    if outcome is None:
        return "TRIGGERED_NO_OUTCOME"

    exit_reason = outcome.get("exit_reason")
    if exit_reason == "NOT_EXECUTABLE":
        return "NOT_EXECUTABLE"

    if exit_reason == "HORIZON_END":
        net_r = outcome.get("net_r")
        if net_r is None:
            return "COMPLETED"
        return "WIN" if net_r > 0.05 else ("LOSS" if net_r < -0.05 else "BREAKEVEN")

    if exit_reason in ("STOP_HIT",):
        return "LOSS (STOP)"
    if exit_reason == "BE_HIT":
        return "BREAKEVEN (BE_HIT)"
    if exit_reason == "T2_HIT":
        return "WIN (T2)"
    if exit_reason == "EOD_CLOSE":
        net_r = outcome.get("net_r")
        if net_r is None:
            return "EOD"
        return "WIN (EOD)" if net_r > 0.05 else ("LOSS (EOD)" if net_r < -0.05 else "BREAKEVEN (EOD)")

    return exit_reason or "UNKNOWN"