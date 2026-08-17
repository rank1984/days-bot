"""
Risk Engine – Dilution, ATM, PIPE, Red Flags
"""
import re

DILUTION_KEYWORDS = [
    "offering", "direct offering", "atm", "at-the-market",
    "pipe", "resale", "resale registration", "warrant",
    "dilution", "shelf", "follow-on", "registered direct",
    "convertible", "reverse split", "reverse stock split",
    "going concern", "compliance", "nasdaq notice"
]

def analyze_dilution_risk(text: str) -> dict:
    """
    מנתח סיכון דילול מתוך טקסט (חדשות, תיאור מניה)
    """
    if not text:
        return {"dilution_risk": "UNKNOWN", "red_flags": [], "risk_score": 0}
    
    lower = text.lower()
    flags = []
    for kw in DILUTION_KEYWORDS:
        if kw in lower:
            flags.append(kw.upper())
    
    if not flags:
        return {"dilution_risk": "LOW", "red_flags": [], "risk_score": 0}
    
    # Score based on number and severity
    score = len(flags) * 5
    if any(k in text.lower() for k in ["pipe", "atm", "offering", "dilution"]):
        score += 10
    if any(k in text.lower() for k in ["reverse split", "going concern"]):
        score += 15
    
    if score >= 30:
        risk = "CRITICAL"
    elif score >= 20:
        risk = "HIGH"
    elif score >= 10:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    
    return {
        "dilution_risk": risk,
        "red_flags": flags[:5],
        "risk_score": min(score, 50)
    }
