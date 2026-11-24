"""Shared HTTP and DataFrame contracts for the optional macro providers."""

from __future__ import annotations

import math
import ssl
import time
from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from ..data import iso_date
from ..exceptions import DataUnavailableError, ValidationError

if TYPE_CHECKING:
    import httpx
    import pandas as pd


def pandas() -> Any:
    try:
        import pandas as pd
    except ImportError as exc:
        raise DataUnavailableError("DataFrames require simulacre-finance[macro]") from exc
    return pd


def interval(start: str | date, end: str | date) -> tuple[date, date]:
    first, last = iso_date(start), iso_date(end)
    if first > last:
        raise ValidationError("start must be on or before end")
    return first, last


def number(value: Any) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError("Boolean is not a financial value")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite value")
        return result
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataUnavailableError("Missing or invalid numeric observation") from exc


def observed_date(value: str) -> date:
    try:
        # Keep the source's local observation date, without a UTC date shift.
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError) as exc:
        raise DataUnavailableError("Invalid provider observation date") from exc


def frame(
    rows: Sequence[Mapping[str, Any]],
    units: Mapping[str, str],
    *,
    source: str,
    frequency: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    pd = pandas()
    result = pd.DataFrame(rows, columns=["date", *units])
    try:
        result["date"] = pd.to_datetime(result["date"]).astype("datetime64[ns]")
        for column in units:
            result[column] = result[column].astype("float64")
            if result[column].isin([math.inf, -math.inf]).any():
                raise ValueError("Nonfinite calculated observation")
        if result["date"].duplicated().any():
            raise ValueError("Duplicate observation dates")
        if not result.empty:
            days = result["date"].dt.date
            if ((days < start) | (days > end)).any():
                raise ValueError("Out-of-range observation")
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataUnavailableError("Provider violates the macro DataFrame contract") from exc
    result = result.sort_values("date").reset_index(drop=True)
    result.attrs = {
        "source": source,
        "units": dict(units),
        "frequency": frequency,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "date_semantics": "observation date, not publication date",
        "vintage": "latest available; not point-in-time history",
    }
    return result  # type: ignore[no-any-return]


class HTTPSource:
    """Small bounded transport; callers own any supplied HTTPX client."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20,
        retries: int = 2,
        backoff: float = 0.5,
    ) -> None:
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(backoff)
            or backoff < 0
            or type(retries) is not int
            or not 0 <= retries <= 10
        ):
            raise ValidationError(
                "Positive timeout, nonnegative backoff and 0..10 retries required"
            )
        self.client = client
        self.timeout, self.retries, self.backoff = timeout, retries, backoff

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            import httpx
        except ImportError as exc:
            raise DataUnavailableError("Network access requires simulacre-finance[macro]") from exc
        context = (
            nullcontext(self.client)
            if self.client is not None
            else httpx.Client(
                verify=ssl.create_default_context(),
                headers={"User-Agent": "simulacre-finance macro data client"},
            )
        )
        with context as client:
            for attempt in range(self.retries + 1):
                try:
                    response = client.request(method, url, timeout=self.timeout, **kwargs)
                    response.raise_for_status()
                    return response
                except httpx.HTTPError as exc:
                    retryable = isinstance(exc, httpx.TransportError) or (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code in (408, 429, 500, 502, 503, 504)
                    )
                    if not retryable or attempt == self.retries:
                        raise DataUnavailableError(f"Macro source request failed: {url}") from exc
                    time.sleep(self.backoff * 2**attempt)
        raise AssertionError("Unreachable retry state")
