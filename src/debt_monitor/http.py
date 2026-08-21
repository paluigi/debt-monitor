"""Shared async HTTP client with tenacity retries (exponential jitter) and
host-specific header quirks documented in the source dossiers."""

import io
import logging
import zipfile
from collections.abc import Mapping
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

DEFAULT_UA = "debt-monitor/0.1 (data collection; contact: repo owner)"
# www/efts/data.sec.gov reject non-browser user agents (dossier 10).
CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_RETRYABLE_STATUS = {413, 429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    """Raised for transient statuses so tenacity can retry with backoff."""

    def __init__(self, status_code: int, url: str, body_snippet: str = "") -> None:
        self.status_code = status_code
        self.url = url
        self.body_snippet = body_snippet[:300]
        super().__init__(f"HTTP {status_code} for {url}: {self.body_snippet}")


class AsyncHttpClient:
    """Thin wrapper over httpx.AsyncClient with retries and per-host headers.

    `proxy` is applied ONLY to www.sec.gov archive hosts — the one documented
    egress-blocked case (dossier 10). Everything else goes direct.
    """

    def __init__(self, proxy: str = "") -> None:
        self._proxy = proxy or None
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_UA},
        )
        self._proxied_client: httpx.AsyncClient | None = None

    @property
    def client_for_sec_www(self) -> httpx.AsyncClient:
        if self._proxied_client is None:
            self._proxied_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0),
                follow_redirects=True,
                headers={"User-Agent": CHROME_UA},
                proxy=self._proxy,
            )
        return self._proxied_client

    async def aclose(self) -> None:
        await self._client.aclose()
        if self._proxied_client is not None:
            await self._proxied_client.aclose()

    def _host_headers(self, url: str) -> dict[str, str]:
        host = httpx.URL(url).host
        if host.endswith("sec.gov"):
            return {"User-Agent": CHROME_UA, "Accept-Encoding": "gzip, deflate"}
        return {}

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, RetryableHTTPError)),
        wait=wait_exponential_jitter(initial=1, max=45),
        stop=stop_after_attempt(4),
        before_sleep=lambda rs: logger.warning(
            "retrying request (attempt %d failed): %s",
            rs.attempt_number,
            rs.outcome.exception() if rs.outcome else "unknown error",
        ),
    )
    async def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        merged = {**self._host_headers(url), **(headers or {})}
        response = await self._client.get(url, params=params, headers=merged, timeout=timeout)
        if response.status_code in _RETRYABLE_STATUS:
            raise RetryableHTTPError(response.status_code, str(response.url))
        response.raise_for_status()
        return response

    async def get_bytes(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        response = await self._request(url, params=params, headers=headers, timeout=timeout)
        return response.content

    async def get_text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> str:
        response = await self._request(url, params=params, headers=headers, timeout=timeout)
        return response.text

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        response = await self._request(url, params=params, headers=headers, timeout=timeout)
        return response.json()


def unzip_members(data: bytes) -> dict[str, bytes]:
    """Return {filename: bytes} for every member of an in-memory zip."""
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith("/"):
                members[name] = zf.read(name)
    return members
