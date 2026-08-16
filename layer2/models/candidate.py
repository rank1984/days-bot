from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class DaysCandidate(BaseModel):
    """
    Raw candidate received from DAYS-BOT.

    IMPORTANT:
    This model contains ONLY information supplied by DAYS-BOT.
    No live market calculations are performed here.
    """

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=10)

    price: float = Field(gt=0)

    gap_pct: float

    days_score: float = Field(ge=0, le=100)

    days_status: str

    days_hits: int = Field(ge=0)

    days_news: Optional[str] = None

    source: str = "DAYS-BOT"

    source_timestamp: Optional[datetime] = None

    parsed_at: datetime
