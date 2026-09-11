"""
DAYS-BOT V5.0.5.2 – Corporate Action Analyzer

Detects:
- Recent splits (FMP)
- Offerings (SEC EDGAR)
- Ticker changes / halts (if available)

Returns NO_TRADE if any detected.
"""
import requests
from datetime import datetime, timedelta
from utils.config import FMP_API_KEY

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


def _get_from_fmp(endpoint: str, params: dict) -> list:
    if not FMP_API_KEY:
        return []
    try:
        url = f"{FMP_BASE_URL}/{endpoint}"
        params["apikey"] = FMP_API_KEY
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else [data]
        return []
    except Exception as e:
        print(f"[CorpAction] FMP error: {e}")
        return []


def check_corporate_action(ticker: str) -> dict:
    result = {
        "corporate_action": False,
        "corporate_action_type": None,
        "reason": "NONE",
        "halt_flag": False,
    }

    # 1. Splits (30 days)
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        split_data = _get_from_fmp("historical-price-full/stock_split", {"symbol": ticker})

        if split_data and isinstance(split_data, list) and len(split_data) > 0:
            splits = split_data[0].get("historical", []) if isinstance(split_data[0], dict) else []
            for split in splits[:5]:
                split_date_str = split.get("date")
                if not split_date_str:
                    continue
                try:
                    split_date = datetime.strptime(split_date_str, "%Y-%m-%d")
                    if split_date >= start:
                        num = split.get("numerator", 1)
                        den = split.get("denominator", 1)
                        split_type = "REVERSE_SPLIT" if num < den else "FORWARD_SPLIT"
                        result["corporate_action"] = True
                        result["corporate_action_type"] = split_type
                        result["reason"] = f"{split_type} on {split_date_str}"
                        return result
                except:
                    continue
    except Exception as e:
        print(f"[CorpAction] Split check error {ticker}: {e}")

    # 2. Offerings (via SEC)
    try:
        from scanner.analyzers.sec_analyzer import check_offering_risk
        sec_result = check_offering_risk(ticker)
        if isinstance(sec_result, dict):
            has_offering = sec_result.get("has_offering", False)
            risk_level = sec_result.get("risk_level", "LOW")
            if has_offering and risk_level in ("HIGH", "MEDIUM"):
                result["corporate_action"] = True
                result["corporate_action_type"] = "OFFERING"
                result["reason"] = f"Offering ({risk_level}) – {sec_result.get('filing_type', 'UNKNOWN')}"
                return result
    except Exception as e:
        print(f"[CorpAction] SEC check error {ticker}: {e}")

    return result