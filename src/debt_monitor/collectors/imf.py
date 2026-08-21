"""IMF SDMX 2.1: Global Debt Database (GDD) + World Economic Outlook (WEO).

api.imf.org returns structure-specific SDMX regardless of the Accept header, so
series blocks are parsed with a namespace-agnostic regex over the raw XML
(dossier 01). GDD CHN/IND private-sector cells are `<Obs>` without OBS_VALUE —
such observations are dropped naturally by the parser.
"""

import asyncio
import re
from datetime import UTC, datetime

from debt_monitor.collectors.base import BaseCollector, register
from debt_monitor.models import CollectResult

GDD_URL = "https://api.imf.org/external/sdmx/2.1/data/GDD/all"
WEO_URL_BASE = "https://api.imf.org/external/sdmx/2.1/data/WEO"

# Gov / household / non-financial-corp / private debt, percent of GDP variants.
GDD_INDICATOR = re.compile(r"^FL_(S13|S14|S11|PS)[A-Z0-9_]*_PT$")
# The dumps are attribute-based structure-specific SDMX: series dimensions are
# attributes of the <Series> tag and observations are <Obs TIME_PERIOD=.. OBS_VALUE=..>
# attributes. NAs are <Obs> without OBS_VALUE (dropped naturally).
_SERIES_OPEN = re.compile(r"<(?:\w+:)?Series\b([^>]*)>")
_ATTRS = re.compile(r'([A-Za-z_][\w:.-]*)="([^"]*)"')
_OBS_TAG = re.compile(r"<(?:\w+:)?Obs\b([^>]*?)/?>")


def parse_sdmx_series(xml_text: str) -> list[dict]:
    """Return [{dims: {...}, observations: [(period, value), ...]}, ...]."""
    opens = list(_SERIES_OPEN.finditer(xml_text))
    series_list: list[dict] = []
    for i, match in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(xml_text)
        body = xml_text[match.end() : end]
        dims = dict(_ATTRS.findall(match.group(1)))
        observations = []
        for tag in _OBS_TAG.finditer(body):
            attrs = dict(_ATTRS.findall(tag.group(1)))
            if "TIME_PERIOD" in attrs and "OBS_VALUE" in attrs:
                try:
                    observations.append((attrs["TIME_PERIOD"], float(attrs["OBS_VALUE"])))
                except ValueError:
                    continue
        if dims and observations:
            series_list.append({"dims": dims, "observations": observations})
    return series_list


@register
class ImfCollector(BaseCollector):
    name = "imf"
    collection = "imf"
    description = "IMF GDD sector debt %GDP (annual) + WEO gov gross debt %GDP (annual)"

    async def collect(self) -> CollectResult:
        parts: list[str] = []
        total = 0

        gdd_text = await self.http.get_text(GDD_URL, timeout=120.0)
        gdd_series = [
            s
            for s in parse_sdmx_series(gdd_text)
            if GDD_INDICATOR.match(s["dims"].get("INDICATOR", ""))
        ]
        observations = [
            self.obs(
                dataset="GDD",
                series=s["dims"].get("INDICATOR", ""),
                country=s["dims"].get("COUNTRY", ""),
                period=period,
                period_type="year",
                value=value,
                unit="% of GDP",
                dimensions={"indicator": s["dims"].get("INDICATOR", "")},
            )
            for s in gdd_series
            for period, value in s["observations"]
        ]
        total += await self.upsert(observations)
        parts.append(f"GDD: {len(observations)} obs / {len(gdd_series)} series")

        current_year = datetime.now(UTC).year
        weo_series: list[dict] = []
        # `WEO/all` returns 200-but-empty (dossier 01); explicit country lists
        # work. Derive them from the GDD parse, chunked to keep URLs sane.
        gdd_countries = sorted({s["dims"].get("COUNTRY", "") for s in gdd_series} - {""})
        for i in range(0, len(gdd_countries), 50):
            chunk = "+".join(gdd_countries[i : i + 50])
            weo_text = await self.http.get_text(
                f"{WEO_URL_BASE}/{chunk}.GGXWDG_NGDP.A", timeout=120.0
            )
            weo_series.extend(parse_sdmx_series(weo_text))
            await asyncio.sleep(0.3)
        weo_observations = [
            self.obs(
                dataset="WEO",
                series="GGXWDG_NGDP",
                country=s["dims"].get("COUNTRY", ""),
                period=period,
                period_type="year",
                value=value,
                unit="% of GDP",
                dimensions={"indicator": "GGXWDG_NGDP"},
            )
            for s in weo_series
            if s["dims"].get("INDICATOR") == "GGXWDG_NGDP"
            for period, value in s["observations"]
            if period.isdigit() and int(period) <= current_year  # drop forecasts
        ]
        total += await self.upsert(weo_observations)
        parts.append(f"WEO: {len(weo_observations)} obs")

        if not gdd_series:
            return CollectResult(
                source=self.name,
                status="failed",
                n_docs=total,
                detail="; ".join(parts + ["GDD returned no matching series"]),
            )
        return CollectResult(source=self.name, status="ok", n_docs=total, detail="; ".join(parts))
