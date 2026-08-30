"""
Float & Short Interest Analyzer – מ-Finviz (סריקה חינמית)
"""
import requests
from bs4 import BeautifulSoup
import time

def get_float_and_short(ticker: str) -> dict:
    """
    מחזיר מילון עם: float, short_interest, short_ratio
    """
    result = {
        "float": None,
        "short_interest": None,
        "short_ratio": None,
        "source": "finviz"
    }

    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        # חפש את הטבלה הראשית עם הנתונים
        table = soup.find("table", {"class": "snapshot-table2"})
        if not table:
            return result

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].text.strip()
            value = cells[1].text.strip()

            if "Float" in label:
                # המספר בפורמט "12.34M" או "1.23B"
                result["float"] = parse_number(value)
            elif "Short Float" in label or "Short Interest" in label:
                result["short_interest"] = parse_percent(value)
            elif "Short Ratio" in label:
                result["short_ratio"] = parse_number(value)

        return result

    except Exception as e:
        print(f"[FloatAnalyzer] Error for {ticker}: {e}")
        return result


def parse_number(text: str) -> float:
    """ממיר מחרוזת כמו '12.34M' ל-12340000"""
    try:
        text = text.replace(",", "").strip()
        if not text:
            return None
        if text.endswith("B"):
            return float(text[:-1]) * 1_000_000_000
        elif text.endswith("M"):
            return float(text[:-1]) * 1_000_000
        elif text.endswith("K"):
            return float(text[:-1]) * 1_000
        else:
            return float(text)
    except:
        return None


def parse_percent(text: str) -> float:
    """ממיר מחרוזת כמו '12.34%' ל-0.1234"""
    try:
        text = text.replace("%", "").strip()
        return float(text) / 100.0
    except:
        return None
