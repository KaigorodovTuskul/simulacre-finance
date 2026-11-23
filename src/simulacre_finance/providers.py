"""Optional public MOEX ISS transport, separate from validated transformations."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from urllib.parse import quote

from .data import Metadata, PriceData, frozen_array, iso_date
from .exceptions import DataUnavailableError, ValidationError

JSONTransport = Callable[[str, Mapping[str, str | int], float], Mapping[str, Any]]


@dataclass(frozen=True)
class Instrument:
    """ISS search identifier; not proof of currency, trading availability or eligibility."""

    secid: str
    shortname: str
    isin: str | None


def _table(payload: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    try:
        block = payload[name]
        columns, rows = block["columns"], block["data"]
        if (
            not isinstance(columns, list)
            or not isinstance(rows, list)
            or not columns
            or not all(isinstance(x, str) for x in columns)
            or len(set(columns)) != len(columns)
        ):
            raise ValueError("Malformed columns/data")
        if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
            raise ValueError("Incomplete ISS row")
        return [dict(zip(columns, row, strict=True)) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise DataUnavailableError(f"Malformed ISS table: {name}") from exc


class MoexISS:
    """Bounded, retried ISS search and stock/share historical CLOSE access.

    Install [http] for the default HTTPS transport. A fixture/custom transport has
    signature (url, params, timeout_seconds) -> JSON mapping. It should raise
    DataUnavailableError, TimeoutError or OSError for retriable failures.
    All history pages must complete; a page limit never silently truncates data.
    """

    def __init__(
        self,
        *,
        transport: JSONTransport | None = None,
        timeout: float = 10,
        retries: int = 2,
        max_pages: int = 100,
        backoff: float = 0.2,
    ) -> None:
        import math

        if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(backoff) or backoff < 0:
            raise ValidationError("Positive finite timeout and nonnegative backoff required")
        if type(retries) is not int or not 0 <= retries <= 10:
            raise ValidationError("retries must be an integer from 0 to 10")
        if type(max_pages) is not int or not 1 <= max_pages <= 10000:
            raise ValidationError("max_pages must be an integer from 1 to 10000")
        self.transport = transport or self._http
        self.timeout, self.retries, self.max_pages, self.backoff = (
            timeout,
            retries,
            max_pages,
            backoff,
        )

    @staticmethod
    def _http(url: str, params: Mapping[str, str | int], timeout: float) -> Mapping[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise DataUnavailableError(
                "MOEX HTTP transport requires simulacre-finance[http]"
            ) from exc
        try:
            response = httpx.get(url, params=params, timeout=timeout, follow_redirects=False)
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, dict):
                raise ValueError("JSON object expected")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise DataUnavailableError("MOEX ISS request failed") from exc

    def _request(self, path: str, params: Mapping[str, str | int]) -> Mapping[str, Any]:
        for attempt in range(self.retries + 1):
            try:
                payload = self.transport(
                    f"https://iss.moex.com/iss/{path}.json", params, self.timeout
                )
                if not isinstance(payload, Mapping):
                    raise DataUnavailableError("ISS JSON object expected")
                return payload
            except (DataUnavailableError, TimeoutError, OSError) as exc:
                if attempt == self.retries:
                    raise DataUnavailableError("ISS request exhausted retries") from exc
                time.sleep(self.backoff * 2**attempt)
        raise AssertionError("Unreachable retry state")

    def _pages(
        self, path: str, table: str, params: Mapping[str, str | int]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        start = 0
        expected_total: int | None = None
        previous: list[dict[str, Any]] | None = None
        for _ in range(self.max_pages):
            payload = self._request(path, {**params, "start": start, "iss.meta": "off"})
            rows = _table(payload, table)
            if rows and rows == previous:
                raise DataUnavailableError("ISS pagination repeated a page")
            cursor_name = f"{table}.cursor"
            if cursor_name in payload:
                cursor = _table(payload, cursor_name)
                try:
                    index, total, size = (cursor[0][k] for k in ("INDEX", "TOTAL", "PAGESIZE"))
                    if any(type(x) is not int for x in (index, total, size)):
                        raise ValueError("Invalid cursor types")
                    if index != start or total < start or size <= 0:
                        raise ValueError("Invalid cursor bounds")
                    if len(rows) != min(size, total - start):
                        raise ValueError("ISS page length disagrees with advertised cursor")
                    if expected_total is not None and total != expected_total:
                        raise ValueError("ISS pagination total changed during the request")
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise DataUnavailableError("Malformed ISS pagination cursor") from exc
                expected_total = total
                result.extend(rows)
                if start + size >= total:
                    return result
                start += size
            else:
                if expected_total is not None:
                    raise DataUnavailableError("ISS pagination cursor disappeared mid-request")
                if not rows:
                    return result
                result.extend(rows)
                start += len(rows)
            previous = rows
        raise DataUnavailableError("ISS page bound reached; response is incomplete")

    def lookup(self, query: str) -> tuple[Instrument, ...]:
        """Search instruments; no result is an empty tuple, transport failure raises."""
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("Nonempty instrument query required")
        rows = self._pages("securities", "securities", {"q": query, "iss.only": "securities"})
        instruments = []
        for row in rows:
            if not isinstance(row.get("secid"), str) or not row["secid"]:
                raise DataUnavailableError("ISS search row is missing secid")
            if any(
                row.get(key) is not None and not isinstance(row[key], str)
                for key in ("shortname", "isin")
            ):
                raise DataUnavailableError("ISS search name/ISIN must be strings or null")
            instruments.append(
                Instrument(row["secid"], str(row.get("shortname") or ""), row.get("isin"))
            )
        if len({x.secid for x in instruments}) != len(instruments):
            raise DataUnavailableError("ISS search returned duplicate identifiers")
        return tuple(instruments)

    def history(
        self,
        secid: str,
        start: str | date,
        end: str | date,
        *,
        currency: str,
        board: str = "TQBR",
        periods_per_year: int = 252,
        missing: Literal["raise", "drop"] = "raise",
    ) -> PriceData:
        """Unadjusted share CLOSE prices, one explicit board, ascending observed dates.

        currency is asserted by the caller after instrument verification; ISS history
        does not establish a common base currency. Missing CLOSE raises by default;
        missing='drop' explicitly drops null CLOSE rows, never fills absent sessions.
        No bond percent-of-par prices or corporate-action adjustments are inferred.
        """
        first, last = iso_date(start), iso_date(end)
        if first > last or missing not in ("raise", "drop"):
            raise ValidationError("Ordered dates and missing='raise' or 'drop' required")
        if not all(isinstance(x, str) and x.strip() for x in (secid, board)):
            raise ValidationError("Explicit secid and board required")
        metadata = Metadata(
            currency,
            periods_per_year,
            f"MOEX ISS shares/{board}/{secid} CLOSE; missing={missing}",
            date.today(),
            adjustment="unadjusted",
            frequency="daily",
        )
        path = (
            "history/engines/stock/markets/shares/boards/"
            f"{quote(board, safe='')}/securities/{quote(secid, safe='')}"
        )
        rows = self._pages(
            path,
            "history",
            {
                "from": first.isoformat(),
                "till": last.isoformat(),
                "iss.only": "history,history.cursor",
            },
        )
        days, prices = [], []
        for row in rows:
            try:
                day = iso_date(row["TRADEDATE"])
                if row.get("SECID") != secid or row.get("BOARDID") != board:
                    raise DataUnavailableError("ISS returned a different instrument/board")
                if not first <= day <= last:
                    raise DataUnavailableError("ISS returned an out-of-range observation")
                value = row["CLOSE"]
                if value is None and missing == "drop":
                    continue
                days.append(day)
                prices.append([float(value)])
            except (KeyError, TypeError, ValueError) as exc:
                raise DataUnavailableError("Invalid/missing ISS historical close") from exc
        if not days:
            raise DataUnavailableError("No historical closes in requested interval")
        try:
            return PriceData(tuple(days), (secid,), frozen_array(prices), metadata)
        except ValidationError as exc:
            raise DataUnavailableError("ISS history violates the price data contract") from exc
