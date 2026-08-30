"""
Sympathy Scanner – מוצא מניות נוספות באותו סקטור עם Float נמוך
"""
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import time

# מפת סקטורים ראשית (נתונים מ-Finviz)
SECTOR_MAP = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AMD", "INTC", "CSCO", "ORCL", "CRM", "ADBE", "QCOM"],
    "Biotech": ["PFE", "MRK", "ABBV", "AMGN", "GILD", "REGN", "BIIB", "VRTX", "ILMN", "CRISPR"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG", "MPC", "PSX", "VLO", "HES"],
    "Financial": ["JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "AXP", "COF"],
    "Consumer": ["DIS", "NKE", "MCD", "SBUX", "PEP", "KO", "WMT", "TGT", "COST", "LOW"],
    "Industrial": ["GE", "BA", "CAT", "DE", "HON", "MMM", "RTX", "LMT", "GD", "NOC"],
    "Healthcare": ["JNJ", "UNH", "CVS", "WBA", "ABT", "MDT", "SYK", "ISRG", "DHR", "TMO"]
}


def get_sector_for_ticker(ticker: str) -> str:
    """מנסה לקבוע סקטור לפי Finviz"""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        # מחפש את השורה עם "Sector"
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "Sector" in cells[0].text:
                return cells[1].text.strip()
    except:
        pass

    # Fallback – חיפוש במפה
    for sector, symbols in SECTOR_MAP.items():
        if ticker in symbols:
            return sector
    return None


def find_sympathy_candidates(leader: dict, max_candidates: int = 5) -> list:
    """
    מקבל מניה מובילה (leader), מחזיר רשימת מניות נוספות באותו סקטור
    עם Float נמוך (לפי Finviz)
    """
    ticker = leader['ticker']
    sector = get_sector_for_ticker(ticker)
    if not sector:
        print(f"[Sympathy] No sector found for {ticker}")
        return []

    print(f"[Sympathy] Leader sector: {sector}")

    # נסה למצוא מניות נוספות באותו סקטור (מ-SECTOR_MAP + Finviz)
    candidates = []

    # 1. מה-SECTOR_MAP
    for sym in SECTOR_MAP.get(sector, []):
        if sym == ticker:
            continue
        candidates.append({"ticker": sym, "source": "sector_map"})

    # 2. נסה לשלוף מ-Finviz
    try:
        url = f"https://finviz.com/screener.ashx?v=111&f=sector_{sector.lower().replace(' ', '_')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "screener-table"})
            if table:
                for row in table.find_all("tr")[1:6]:  # 5 מניות נוספות
                    cells = row.find_all("td")
                    if cells:
                        sym = cells[0].text.strip()
                        if sym and sym != ticker:
                            candidates.append({"ticker": sym, "source": "finviz"})
    except:
        pass

    # 3. סינון Float < 20M באמצעות yfinance (או Finviz)
    filtered = []
    for c in candidates[:20]:
        try:
            # נשלוף Float מ-Finviz
            float_val = get_float(c['ticker'])
            if float_val and float_val < 20_000_000:
                filtered.append(c)
                if len(filtered) >= max_candidates:
                    break
        except:
            continue

    # 4. הוסף נתונים בסיסיים לכל מועמד
    result = []
    for c in filtered:
        try:
            data = yf.download(c['ticker'], period="1d", interval="1m", prepost=True, progress=False)
            if not data.empty:
                price = data['Close'].iloc[-1]
                volume = int(data['Volume'].sum())
                result.append({
                    "ticker": c['ticker'],
                    "price": round(price, 2),
                    "pm_volume": volume,
                    "source": c['source'],
                    "sector": sector,
                    "sympathy_to": ticker
                })
        except:
            continue

    return result


def get_float(ticker: str) -> float:
    """שליפת Float מ-Finviz"""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "snapshot-table2"})
            if table:
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2 and "Float" in cells[0].text:
                        val = cells[1].text.strip()
                        if val.endswith("M"):
                            return float(val[:-1]) * 1_000_000
                        elif val.endswith("B"):
                            return float(val[:-1]) * 1_000_000_000
                        else:
                            return float(val.replace(",", ""))
    except:
        pass
    return None
