"""
AI Small-Cap Quant Analyzer

Pipeline:

DAYS-BOT message
        ↓
Parser
        ↓
Live Data
        ↓
Quant Engine
        ↓
Ranking
"""

from typing import List, Dict, Any

from quant_agent.parser import parse_watchlist
from quant_agent.live_data import LiveDataEngine
from quant_agent.quant_engine import rank_candidates


class QuantAnalyzer:

    def __init__(self):
        self.live_engine = LiveDataEngine()

    def analyze_message(
        self,
        message: str
    ) -> List[Dict[str, Any]]:

        # 1. Parse DAYS-BOT
        candidates = parse_watchlist(
            message
        )

        if not candidates:
            print(
                "[QuantAnalyzer] "
                "No candidates parsed."
            )
            return []

        # 2. Live validation
        live_candidates = (
            self.live_engine
            .get_snapshots(candidates)
        )

        if not live_candidates:
            print(
                "[QuantAnalyzer] "
                "No live candidates."
            )
            return []

        # 3. Independent Quant ranking
        ranked = rank_candidates(
            live_candidates
        )

        return ranked
