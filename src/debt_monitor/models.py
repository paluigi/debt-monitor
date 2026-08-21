"""Record models shared by all collectors."""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PeriodType(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


def classify_period(period: str) -> PeriodType:
    """Infer the period type from a canonical period string."""
    if "Q" in period:
        return PeriodType.QUARTER
    if period.count("-") == 2:
        return PeriodType.DAY
    if period.count("-") == 1:
        return PeriodType.MONTH
    return PeriodType.YEAR


class Observation(BaseModel):
    """One time-series observation, upserted idempotently by deterministic _id."""

    source: str
    dataset: str
    series: str = ""
    country: str = ""
    period: str
    period_type: PeriodType
    value: float
    unit: str = ""
    dimensions: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def mongo_id(self) -> str:
        key = "|".join(
            [
                self.source,
                self.dataset,
                self.series,
                self.country,
                self.period,
                json.dumps(self.dimensions, sort_keys=True, default=str),
            ]
        )
        return hashlib.sha256(key.encode()).hexdigest()

    def to_doc(self) -> dict[str, Any]:
        dims = {
            k: v if isinstance(v, str | int | float | bool | type(None)) else str(v)
            for k, v in self.dimensions.items()
        }
        doc = self.model_dump(mode="json")
        doc["dimensions"] = dims
        doc["_id"] = self.mongo_id()
        return doc


class CollectResult(BaseModel):
    """Outcome of one collector run, persisted in the _runs collection."""

    source: str
    status: str  # "ok" | "skipped" | "failed"
    n_docs: int = 0
    detail: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
