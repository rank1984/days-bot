import re
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from layer2.models.candidate import DaysCandidate


ET = ZoneInfo("America/New_York")


class DaysBotParser:
    """
    Parses the raw Telegram watchlist message produced by DAYS-BOT.

    Parser responsibilities:
    - Extract candidates
    - Validate required fields
    - Preserve DAYS-BOT values
    - Never calculate trading signals
    """

    CANDIDATE_PATTERN = re.compile(
        r"""
        ^\s*
        \d+\.\s*
        (?P<ticker>[A-Z][A-Z0-9.\-]{0,9})
        .*?
        \$\s*(?P<price>\d+(?:\.\d+)?)
        \s+
        Gap:\s*(?P<gap>[+-]?\d+(?:\.\d+)?)
        %
        \s+
        Score:\s*(?P<score>\d+(?:\.\d+)?)
        .*?
        (?P<status>PREPARE|WATCH|READY|NO_TRADE)
        \s*\|\s*
        Hits:\s*(?P<hits>\d+)
        .*?
        📰\s*(?P<news>.*?)
        \s*$
        """,
        re.VERBOSE,
    )

    HEADER_PATTERN = re.compile(
        r"DAYS-BOT WATCHLIST.*?"
        r"(?P<date>\d{4}-\d{2}-\d{2})"
        r".*?"
        r"(?P<time>\d{2}:\d{2})\s*ET",
        re.DOTALL,
    )

    def parse(self, message: str) -> List[DaysCandidate]:
        if not message or not message.strip():
            raise ValueError("Empty DAYS-BOT message")

        source_timestamp = self._parse_source_timestamp(message)
        parsed_at = datetime.now(ET)

        candidates: List[DaysCandidate] = []

        for line in message.splitlines():
            line = self._clean_line(line)

            if not line:
                continue

            match = self.CANDIDATE_PATTERN.match(line)

            if not match:
                continue

            data = match.groupdict()

            news = self._clean_news(data.get("news"))

            candidate = DaysCandidate(
                ticker=data["ticker"].upper(),
                price=float(data["price"]),
                gap_pct=float(data["gap"]),
                days_score=float(data["score"]),
                days_status=data["status"].upper(),
                days_hits=int(data["hits"]),
                days_news=news,
                source="DAYS-BOT",
                source_timestamp=source_timestamp,
                parsed_at=parsed_at,
            )

            candidates.append(candidate)

        if not candidates:
            raise ValueError(
                "No valid DAYS-BOT candidates found in message"
            )

        return candidates

    @staticmethod
    def _clean_line(line: str) -> str:
        """
        Remove Telegram formatting characters that can interfere
        with parsing while preserving the actual values.
        """

        line = line.strip()

        # Markdown bold
        line = line.replace("**", "")

        return line

    @staticmethod
    def _clean_news(news: Optional[str]) -> Optional[str]:
        if not news:
            return None

        news = news.strip()

        if news in {"—", "-", "N/A", "None"}:
            return None

        return news

    @classmethod
    def _parse_source_timestamp(
        cls,
        message: str,
    ) -> Optional[datetime]:

        match = cls.HEADER_PATTERN.search(message)

        if not match:
            return None

        date_str = match.group("date")
        time_str = match.group("time")

        try:
            return datetime.strptime(
                f"{date_str} {time_str}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ET)

        except ValueError:
            return None


def parse_days_message(message: str) -> List[DaysCandidate]:
    """
    Convenience function.
    """

    parser = DaysBotParser()

    return parser.parse(message)
