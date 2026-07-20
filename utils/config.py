import os

# API Keys
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── FILTERS (Aggressive Momentum Tuning) ──────────────────
MIN_PRICE            = 0.5
MAX_PRICE            = 15.0          # הורד – מניות זולות יותר נוטות לזוז באחוזים גדולים
MIN_GAP_PCT          = 3.0           # Gap של 3% ומעלה – מומנטום חזק
MAX_GAP_PCT          = 25.0          # לא גבוה מדי (מעל 25% זה סיכון גבוה להיפוך מגמה)
MIN_PREMARKET_VOL    = 200_000
MIN_AVG_VOLUME       = 100_000       # נזילות בסיסית היסטורית
MIN_DOLLAR_VOLUME    = 1_000_000     # מינימום $1M נזילות דולרית
MIN_RELATIVE_VOLUME  = 2.0           # נפח גדול פי 2 מהממוצע – עניין אמיתי (RVOL)
MAX_SPREAD_PCT       = 2.0
MAX_FLOAT            = 50_000_000    # מניות עם Float נמוך זזות מהר יותר

# ── SCORING WEIGHTS (Max Total: 100) ──────────────────────
WEIGHT_GAP           = 30            # המשקל העיקרי לזיהוי עוצמת הגאפ
WEIGHT_RVOL          = 25            # אימות נפח חריג יחסית לממוצע
WEIGHT_DOLLAR_VOL    = 20            # הבטחת נזילות כספית אמיתית בדולרים
WEIGHT_CATALYST      = 15            # זרז חדשותי תומך
WEIGHT_FLOAT         = 10            # יתרון למניות בעלות סירקולציה נמוכה

# ── SCORING THRESHOLD ─────────────────────────────────────
MIN_SCORE            = 50            # רק מועמדויות איכותיות עוברות את הסורק

# ── COOLDOWN & MISC ───────────────────────────────────────
COOLDOWN_HOURS       = 4
WEEKLY_REPORT_DAY    = 4

# ── NEWS & CATALYSTS ──────────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda", "approval", "approved", "contract", "acquisition",
    "acquires", "merger", "patent", "earnings", "revenue",
    "partnership", "grant", "award", "breakthrough", "positive",
    "phase", "trial", "clearance", "designation",
]
NEGATIVE_CATALYSTS = [
    "offering", "direct offering", "shelf", "registration",
    "dilution", "warrant", "priced offering", "atm",
]

# ── BACKTEST ──────────────────────────────────────────────
BACKTEST_LOOKBACK_DAYS = 30
BACKTEST_MIN_TRADES = 50
