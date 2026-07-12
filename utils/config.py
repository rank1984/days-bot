import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── BREAKOUT FILTERS ─────────────────────────────────────
MIN_RSI_14           = 50
MAX_RSI_14           = 70
MIN_VOLUME_RATIO     = 1.3
MIN_GAIN_5D          = 3.0
MAX_GAIN_5D          = 20.0       # לא לקפוץ על מנייה שכבר זינקה
MAX_SHORT_INTEREST   = 0.2
MIN_AVG_VOLUME_20D   = 100_000
# ── HARD FILTERS ──────────────────────────────────────────
MIN_PRICE            = 0.5        # הורד - מניות ממש זולות לתנודתיות גבוהה
MAX_PRICE            = 15.0       # הורד - לא צריך יותר מ-15$ למיקרו-קאפ
MIN_AVG_VOLUME       = 100_000    # הורד - מניות קטנות יותר, נזילות מספיקה
MAX_FLOAT            = 30_000_000 # הורד - התמקדות במניות ממש קטנות!
MIN_GAP_PCT          = 0.0        # בטל - אתה לא רוצה פער, אתה רוצה מומנטום
MAX_GAP_PCT          = 3.0          # הוסף - מקסימום 3% gap
MIN_PREMARKET_VOL    = 0          # בטל - לא מעוניין בפרמרקט
MIN_DOLLAR_VOLUME    = 100_000    # הורד - מניות קטנות יותר

# ── NEW FILTERS: MOMENTUM DETECTION ─────────────────────
MIN_RSI_14           = 55         # RSI מעל 55 = מומנטום עולה
MAX_RSI_14           = 75         # מתחת ל-75 = עוד לא הגיע לשיא
MIN_VOLUME_RATIO     = 1.5        # נפח היום גבוה ב-50% מהממוצע
MIN_GAIN_5D          = 5.0        # עלתה 5%+ ב-5 ימים (מומנטום מצטבר)
MIN_GAIN_1D          = 2.0        # עלתה 2%+ אתמול (מומנטום מתחיל)
SHORT_INTEREST_RATIO = 0.2        # פחות מ-20% מהמניות מושאלות = 덜 מורידות

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 35          # מוריד — לקבל יותר מועמדות

# ── Cooldown ─────────────────────────────────────────────
COOLDOWN_HOURS       = 4

# ── News ─────────────────────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda","approval","approved","contract","acquisition",
    "acquires","merger","patent","earnings","revenue",
    "partnership","grant","award","breakthrough","positive",
    "phase","trial","clearance","designation",
]
NEGATIVE_CATALYSTS = [
    "offering","direct offering","shelf","registration",
    "dilution","warrant","priced offering","atm",
]

WEEKLY_REPORT_DAY = 4
