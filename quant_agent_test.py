from quant_agent.analyzer import QuantAnalyzer


MESSAGE = """
📋 **DAYS-BOT WATCHLIST**
📅 2026-08-16 | 🕐 05:46 ET
📊 10 candidates | 0 READY
━━━━━━━━━━━━━━━━━━

**1. LUMN** 💰 $6.73 Gap: +5.1% Score: 90 🟡 PREPARE | Hits: 1 📰 —
**2. WULF** 💰 $17.39 Gap: +6.7% Score: 90 🟡 PREPARE | Hits: 1 📰 —
**3. POET** 💰 $9.58 Gap: +7.8% Score: 90 🔵 WATCH | Hits: 1 📰 —
**4. NNBR** 💰 $3.89 Gap: +8.1% Score: 90 🟡 PREPARE | Hits: 1 📰 —
**5. BORR** 💰 $4.43 Gap: +9.8% Score: 90 🟡 PREPARE | Hits: 1 📰 —
**6. KEEL** 💰 $3.51 Gap: +6.0% Score: 90 🟡 PREPARE | Hits: 1 📰 —
**7. NU** 💰 $15.20 Gap: +9.4% Score: 85 🔵 WATCH | Hits: 1 📰 —
**8. ALM** 💰 $15.09 Gap: +8.8% Score: 85 🟡 PREPARE | Hits: 1 📰 —
**9. CIFR** 💰 $17.86 Gap: +7.4% Score: 85 🟡 PREPARE | Hits: 1 📰 —
**10. GENI** 💰 $8.38 Gap: +6.2% Score: 85 🟡 PREPARE | Hits: 1 📰 —
"""


if __name__ == "__main__":

    analyzer = QuantAnalyzer()

    results = analyzer.analyze_message(
        MESSAGE
    )

    print("\n")
    print("=" * 60)
    print("AI SMALL-CAP QUANT")
    print("=" * 60)

    for i, result in enumerate(
        results,
        start=1
    ):

        print(
            f"{i}. "
            f"{result['ticker']} | "
            f"Final={result['final_score']} | "
            f"Opportunity={result['opportunity_score']} | "
            f"Risk={result['risk_score']} | "
            f"Tradeability={result['tradeability']}"
        )
