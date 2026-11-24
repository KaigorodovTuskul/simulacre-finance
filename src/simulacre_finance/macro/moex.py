"""Daily MOEX ISS macro series, reusing the existing bounded ISS paginator."""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ..exceptions import DataUnavailableError, ValidationError
from ..providers import MoexISS
from ._common import HTTPSource, frame, interval, number, observed_date

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx
    import pandas as pd


class MOEXMacro(HTTPSource):
    """Observed daily index/rate closes and OFZ price quotes, with complete pagination."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20,
        retries: int = 2,
        backoff: float = 0.5,
        max_pages: int = 100,
    ) -> None:
        super().__init__(client=client, timeout=timeout, retries=retries, backoff=backoff)
        self._iss = MoexISS(transport=self._json, max_pages=max_pages, retries=0)

    def _json(self, url: str, params: Mapping[str, str | int], timeout: float) -> Mapping[str, Any]:
        try:
            payload: Any = self._request("GET", url, params=params).json()
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
            return payload
        except ValueError as exc:
            raise DataUnavailableError("Invalid MOEX JSON response") from exc

    def _candles(
        self,
        security: str,
        start: str | date,
        end: str | date,
        *,
        market: str,
        board: str,
        column: str,
        unit: str,
        scale: float = 1,
    ) -> pd.DataFrame:
        first, last = interval(start, end)
        if not isinstance(security, str) or not re.fullmatch(r"[A-Za-z0-9_]+", security):
            raise ValidationError("Invalid MOEX security identifier")
        path = (
            f"engines/stock/markets/{market}/boards/{board}/securities/"
            f"{quote(security, safe='')}/candles"
        )
        rows = self._iss._pages(
            path,
            "candles",
            {
                "from": first.isoformat(),
                "till": last.isoformat(),
                "interval": 24,
                "iss.only": "candles,candles.cursor",
                "candles.columns": "begin,close",
            },
        )
        observations = []
        for item in rows:
            try:
                observations.append(
                    {"date": observed_date(item["begin"]), column: number(item["close"]) * scale}
                )
            except (KeyError, TypeError) as exc:
                raise DataUnavailableError("Missing MOEX daily candle fields") from exc
        return frame(
            observations,
            {column: unit},
            source=f"https://iss.moex.com/iss/{path}.json",
            frequency="daily",
            start=first,
            end=last,
        )

    def index(self, security: str, start: str | date, end: str | date) -> pd.DataFrame:
        """SNDX index close, in index points (e.g. IMOEX, RGBI, RGBITR)."""
        return self._candles(
            security, start, end, market="index", board="SNDX", column="value", unit="index points"
        )

    def imoex(self, start: str | date, end: str | date) -> pd.DataFrame:
        """IMOEX price index; dividends are not included."""
        return self.index("IMOEX", start, end)

    def rgbi(self, start: str | date, end: str | date) -> pd.DataFrame:
        """RGBI price index; coupons are not reinvested (use index('RGBITR', ...) for TR)."""
        return self.index("RGBI", start, end)

    def rusfar(
        self,
        start: str | date,
        end: str | date,
        *,
        tenor: str = "ON",
    ) -> pd.DataFrame:
        """RUSFAR ON/1W/2W/1M/3M annual decimal rate, not an investable price series."""
        if tenor not in ("ON", "1W", "2W", "1M", "3M"):
            raise ValidationError("RUSFAR tenor must be ON, 1W, 2W, 1M or 3M")
        security = "RUSFAR" + ("" if tenor == "ON" else tenor)
        return self._candles(
            security,
            start,
            end,
            market="index",
            board="MMIX",
            column="rate",
            unit="decimal annual rate",
            scale=0.01,
        )

    def rusfar_curve(self, start: str | date, end: str | date) -> pd.DataFrame:
        """Five term rates, outer-aligned by observation date; missing tenors stay NaN."""
        first, last = interval(start, end)
        points: dict[date, dict[str, Any]] = {}
        units = {}
        for tenor in ("ON", "1W", "2W", "1M", "3M"):
            name = f"rusfar_{tenor.lower()}"
            units[name] = "decimal annual rate"
            data = self.rusfar(start, end, tenor=tenor)
            for day, value in data.itertuples(index=False, name=None):
                points.setdefault(day.date(), {"date": day.date()})[name] = value
        return frame(
            list(points.values()),
            units,
            source="https://iss.moex.com/iss/",
            frequency="daily",
            start=first,
            end=last,
        )

    def ofz(self, security: str, start: str | date, end: str | date) -> pd.DataFrame:
        """TQOB OFZ quoted clean price as fraction of par, not YTM or total return."""
        if not isinstance(security, str) or not re.fullmatch(r"SU\d{5}RMFS\d", security):
            raise ValidationError("Expected an OFZ SECID such as SU26238RMFS4")
        return self._candles(
            security,
            start,
            end,
            market="bonds",
            board="TQOB",
            column="price",
            unit="fraction of par",
            scale=0.01,
        )
