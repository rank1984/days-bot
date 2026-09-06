"""
Sympathy Scanner – optional, silent when no sector found
"""
import requests
from bs4 import BeautifulSoup

SECTOR_MAP = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AMD", "INTC", "CSCO", "ORCL", "CRM", "ADBE", "QCOM"],
    "Biotech": ["PFE", "MRK", "ABBV", "AMGN", "GILD", "REGN", "BIIB", "VRTX", "ILMN"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG", "MPC", "PSX", "VLO"],
    "Financial": ["JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "AXP", "COF"],
    "Consumer": ["DIS", "NKE", "MCD", "SBUX", "PEP", "KO", "WMT", "TGT", "COST"],
    "Industrial": ["GE", "BA", "CAT", "DE", "HON", "MMM", "RTX", "LMT", "GD"],
    "Healthcare": ["JNJ", "UNH", "CVS", "WBA", "ABT", "MDT", "SYK", "ISRG", "DHR"]
}


def get_sector_for_ticker(ticker: str) -> str:
    """Get sector from Finviz – silent on failure"""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "Sector" in cells[0].text:
                return cells[1].text.strip()
    except:
        pass

    for sector, symbols in SECTOR_MAP.items():
        if ticker in symbols:
            return sector
    return None


def find_sympathy_candidates(leader: dict, max_candidates: int = 5) -> list:
    """Find sympathy candidates – returns [] silently if no sector"""
    ticker = leader.get('ticker', '')
    sector = get_sector_for_ticker(ticker)
    if not sector:
        return []  # silent return
    print(f"[Sympathy] Leader sector: {sector}")

    candidates = []
    for sym in SECTOR_MAP.get(sector, [])[:max_candidates]:
        if sym == ticker:
            continue
        candidates.append({"ticker": sym, "source": "sector_map", "sector": sector, "sympathy_to": ticker})
    return candidates
