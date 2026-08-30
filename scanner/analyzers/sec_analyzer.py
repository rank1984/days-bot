"""
SEC EDGAR Analyzer – בודק דיווחי 8-K, S-1, 424B5 ב-24 שעות אחרונות
"""
import requests
import re
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")

# רשימת סוגי דיווחים שמעידים על הנפקה
OFFERING_FORMS = ["S-1", "S-3", "S-8", "424B5", "424B3", "F-1", "F-3", "8-K"]


def check_offering_risk(ticker: str) -> dict:
    """
    מחזיר מילון:
    - has_offering: True/False
    - filing_type: סוג הדיווח
    - filing_date: תאריך
    - risk_level: "HIGH", "MEDIUM", "LOW"
    """
    result = {
        "has_offering": False,
        "filing_type": None,
        "filing_date": None,
        "risk_level": "LOW"
    }

    try:
        # נשתמש ב-SEC EDGAR API (באמצעות CIK)
        cik = get_cik(ticker)
        if not cik:
            return result

        # שליפת 10 דיווחים אחרונים
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        headers = {
            "User-Agent": "DAYS-BOT (contact@example.com)",
            "Accept": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return result

        data = resp.json()
        filings = data.get("filings", {}).get("recent", {})
        if not filings:
            return result

        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        descriptions = filings.get("primaryDocument", [])

        now_et = datetime.now(ET)
        cutoff = now_et - timedelta(days=7)  # נבדוק שבוע אחורה

        for i, form in enumerate(forms):
            if i >= len(dates) or i >= len(descriptions):
                continue
            filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
            filing_date = ET.localize(filing_date)

            # אם הדיווח ישן מ-7 ימים – דלג
            if filing_date < cutoff:
                continue

            # בדיקה אם זה דיווח הנפקה
            if any(offering_form in form for offering_form in OFFERING_FORMS):
                # בדיקה נוספת – האם כתוב Offering / Prospectus
                desc = descriptions[i].lower()
                if "offering" in desc or "prospectus" in desc or "s-1" in desc or "424b" in desc:
                    result["has_offering"] = True
                    result["filing_type"] = form
                    result["filing_date"] = filing_date.strftime("%Y-%m-%d")
                    # דירוג סיכון
                    if form in ["S-1", "S-3", "424B5"]:
                        result["risk_level"] = "HIGH"
                    elif form in ["S-8"]:
                        result["risk_level"] = "MEDIUM"
                    else:
                        result["risk_level"] = "MEDIUM"
                    break

        return result

    except Exception as e:
        print(f"[SEC] Error for {ticker}: {e}")
        return result


def get_cik(ticker: str) -> str:
    """מקבל CIK עבור סימבול (מהמאגר הציבורי)"""
    try:
        # נשתמש במאגר CIK המקומי (אפשר גם לשלוף מהרשת)
        # לפרויקט הזה, נשתמש במפה מובנית או ניצור cache
        # מכיוון שזה דורש הורדה – נחזיר None כרגע, אבל אפשר להרחיב
        # נשתמש ב-API של SEC
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany"
        headers = {"User-Agent": "DAYS-BOT (contact@example.com)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # ננסה למצוא CIK בתגובה
            import re
            match = re.search(r'CIK=(\d+)', resp.text)
            if match:
                return match.group(1).zfill(10)
    except:
        pass
    return None
