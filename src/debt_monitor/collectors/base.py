"""Collector base class and registry."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

from debt_monitor.config import Settings, get_settings
from debt_monitor.db import MongoRepository
from debt_monitor.http import AsyncHttpClient
from debt_monitor.models import CollectResult, Observation, PeriodType


class BaseCollector(ABC):
    """One provider = one collector = one MongoDB collection."""

    name: ClassVar[str]
    collection: ClassVar[str]
    description: ClassVar[str] = ""

    def __init__(
        self,
        http: AsyncHttpClient,
        repo: MongoRepository,
        settings: Settings | None = None,
    ) -> None:
        self.http = http
        self.repo = repo
        self.settings = settings or get_settings()

    @abstractmethod
    async def collect(self) -> CollectResult:
        """Fetch, parse and upsert. Must never partially fail silently."""

    # ---- shared helpers -------------------------------------------------
    def obs(
        self,
        *,
        dataset: str,
        period: str,
        value: float,
        series: str = "",
        country: str = "",
        period_type: PeriodType | None = None,
        unit: str = "",
        dimensions: dict[str, Any] | None = None,
    ) -> Observation:
        from debt_monitor.models import classify_period

        return Observation(
            source=self.name,
            dataset=dataset,
            series=series,
            country=country,
            period=period,
            period_type=period_type or classify_period(period),
            value=value,
            unit=unit,
            dimensions=dimensions or {},
        )

    async def upsert(self, observations: Sequence[Observation]) -> int:
        return await self.repo.upsert_observations(self.collection, observations)


_REGISTRY: dict[str, type[BaseCollector]] = {}


def register(cls: type[BaseCollector]) -> type[BaseCollector]:
    _REGISTRY[cls.name] = cls
    return cls


def registered_collectors() -> dict[str, type[BaseCollector]]:
    """Import all collector modules so their @register decorators run."""
    from debt_monitor.collectors import (  # noqa: F401  (imports have side effects)
        bis,
        boe,
        dbnomics,
        ecb,
        eurostat,
        fi_filings,
        fred,
        imf,
        japan_mof,
        news,
        nyfed,
        us_treasury,
        worldbank,
    )

    return dict(_REGISTRY)
