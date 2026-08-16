"""
AI Quant Agent V1 - Main Engine

DAYS-BOT Discovery
        ↓
Parser
        ↓
Live Data
        ↓
Hard Filters
        ↓
Quant Score
        ↓
Ranking
"""

from typing import List, Dict, Any

from .live_data import LiveDataEngine
from .filters import apply_hard_filters
from .scoring import calculate_scores


class AIQuantEngine:

    def __init__(self):
        self.live = LiveDataEngine()

    def analyze(
        self,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        if not candidates:
            return {
                "total": 0,
                "passed": [],
                "rejected": [],
            }

        # 1. Live enrichment
        enriched = self.live.enrich_candidates(
            candidates
        )

        passed = []
        rejected = []

        # 2. Hard filters
        for candidate in enriched:

            candidate = apply_hard_filters(
                candidate
            )

            # 3. Quant scoring
            candidate = calculate_scores(
                candidate
            )

            if candidate.get("filter_pass"):
                passed.append(candidate)
            else:
                rejected.append(candidate)

        # 4. Ranking
        passed.sort(
            key=lambda x: x.get(
                "final_score",
                0
            ),
            reverse=True
        )

        return {
            "total": len(candidates),
            "passed": passed,
            "rejected": rejected,
            "top": passed[:2],
        }
