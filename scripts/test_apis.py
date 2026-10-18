#!/usr/bin/env python3
"""
DAYS-BOT API Diagnostics
בודק אילו מקורות נתונים מחזירים נתוני Pre-Market בזמן אמת.
לא מחייב התחברות ל-DB, לא משנה שום קובץ.
"""
import os
import json
import urllib.parse
import requests
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

# מניות לבדיקה: AAPL (נפח גבוה), BRLS (מיקרו-קאפ מהדוח)
TICKERS = ["AAPL", "BRLS"]

def get_today_et():
    return datetime.now(ET).strftime("%Y-%m-%d")

def get_start_utc(hours_ago=6):
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_end_utc():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def print_result(source, ticker, status_code, count, note=""):
    print(f"[{source}] {ticker:5s} | HTTP {status_code} | Results: {count:4d} | {note}")

def test_polygon(ticker):
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        print_result("POLYGON", ticker, "-", 0, "API KEY MISSING")
        return

    today = get_today_et()
    # בדיקת 1 דקה (כולל Pre-Market)
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{today}/{today}"
    params = {"apiKey": api_key, "extended_hours": "true"}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = data.get("resultsCount", 0)
            print_result("POLYGON", ticker, r.status_code, count, "1min bars (extended)")
        else:
            print_result("POLYGON", ticker, r.status_code, 0, r.text[:50])
    except Exception as e:
        print_result("POLYGON", ticker, "ERR", 0, str(e))

def test_fmp(ticker):
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        print_result("FMP", ticker, "-", 0, "API KEY MISSING")
        return

    # FMP historical chart 1min
    url = f"https://financialmodelingprep.com/api/v3/historical-chart/1min/{ticker}"
    params = {"apikey": api_key}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = len(data) if isinstance(data, list) else 0
            print_result("FMP", ticker, r.status_code, count, "1min bars")
        else:
            print_result("FMP", ticker, r.status_code, 0, r.text[:50])
    except Exception as e:
        print_result("FMP", ticker, "ERR", 0, str(e))

def test_finnhub(ticker):
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        print_result("FINNHUB", ticker, "-", 0, "API KEY MISSING")
        return

    start = int((datetime.now(UTC) - timedelta(hours=6)).timestamp())
    end = int(datetime.now(UTC).timestamp())
    
    url = f"https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": ticker, "resolution": "1", 
        "from": start, "to": end, "token": api_key
    }
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("s") == "ok":
                count = len(data.get("c", []))
                print_result("FINNHUB", ticker, r.status_code, count, "1min candles")
            else:
                print_result("FINNHUB", ticker, r.status_code, 0, f"Status: {data.get('s')}")
        else:
            print_result("FINNHUB", ticker, r.status_code, 0, r.text[:50])
    except Exception as e:
        print_result("FINNHUB", ticker, "ERR", 0, str(e))

def test_alpaca(ticker):
    api_key = os.environ.get("ALPACA_API_KEY")
    api_secret = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not api_secret:
        print_result("ALPACA", ticker, "-", 0, "API KEYS MISSING")
        return

    base_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    start = get_start_utc(6)
    end = get_end_utc()

    # בדיקת IEX
    params_iex = {"symbols": ticker, "timeframe": "1Min", "start": start, "end": end, "feed": "iex"}
    try:
        r = requests.get(base_url, headers=headers, params=params_iex, timeout=10)
        if r.status_code == 200:
            bars = r.json().get("bars", {}).get(ticker, [])
            print_result("ALPACA (IEX)", ticker, r.status_code, len(bars), "Free tier")
        else:
            print_result("ALPACA (IEX)", ticker, r.status_code, 0, r.text[:50])
    except Exception as e:
        print_result("ALPACA (IEX)", ticker, "ERR", 0, str(e))

    # בדיקת SIP (דורש מנוי בתשלום)
    params_sip = {"symbols": ticker, "timeframe": "1Min", "start": start, "end": end, "feed": "sip"}
    try:
        r = requests.get(base_url, headers=headers, params=params_sip, timeout=10)
        if r.status_code == 200:
            bars = r.json().get("bars", {}).get(ticker, [])
            print_result("ALPACA (SIP)", ticker, r.status_code, len(bars), "Paid tier")
        else:
            print_result("ALPACA (SIP)", ticker, r.status_code, 0, "Subscription required (403)")
    except Exception as e:
        print_result("ALPACA (SIP)", ticker, "ERR", 0, str(e))

def main():
    print("=" * 70)
    print(f"API DIAGNOSTICS - {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 70)
    
    for ticker in TICKERS:
        print(f"\n--- Testing {ticker} ---")
        test_polygon(ticker)
        test_fmp(ticker)
        test_finnhub(ticker)
        test_alpaca(ticker)
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)

if __name__ == "__main__":
    main()
