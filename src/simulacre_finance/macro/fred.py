"""Public FRED CSV series; no API key, browser or FRED SDK needed."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import TYPE_CHECKING, Any

from ..exceptions import DataUnavailableError
from ._common import HTTPSource, frame, interval, number, observed_date

if TYPE_CHECKING:
    import pandas as pd

_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_UST = (
    "DGS1MO",
    "DGS3MO",
    "DGS6MO",
    "DGS1",
    "DGS2",
    "DGS3",
    "DGS5",
    "DGS7",
    "DGS10",
    "DGS20",
    "DGS30",
)


class FRED(HTTPSource):
    """Latest-vintage observations; publication dates and past vintages are not supplied."""

    def _series(
        self,
        ids: tuple[str, ...],
        start: str | date,
        end: str | date,
        *,
        unit: str,
        frequency: str,
        scale: float = 1,
    ) -> pd.DataFrame:
        first, last = interval(start, end)
        response = self._request(
            "GET",
            _URL,
            params={
                "id": ",".join(ids),
                "cosd": first.isoformat(),
                "coed": last.isoformat(),
            },
        )
        try:
            reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")), strict=True)
            date_key = (reader.fieldnames or [""])[0]
            if date_key not in ("DATE", "observation_date") or reader.fieldnames != [
                date_key,
                *ids,
            ]:
                raise ValueError("Unexpected FRED CSV header")
            rows: list[dict[str, Any]] = []
            for item in reader:
                if None in item or any(value is None for value in item.values()):
                    raise ValueError("Malformed FRED CSV row")
                day = observed_date(item[date_key])
                if not first <= day <= last:
                    continue  # The CSV export can ignore graph date bounds and return full history.
                row: dict[str, Any] = {"date": day}
                for code in ids:
                    value = item[code]
                    row[code] = None if value in ("", ".", "NA") else number(value) * scale
                rows.append(row)
        except (ValueError, UnicodeError, csv.Error) as exc:
            raise DataUnavailableError("Invalid FRED CSV response") from exc
        result = frame(
            rows,
            dict.fromkeys(ids, unit),
            source=f"{_URL}?id={','.join(ids)}",
            frequency=frequency,
            start=first,
            end=last,
        )
        result.attrs["missing_values"] = "FRED missing observations are NaN; never filled"
        return result

    def treasury_yields(self, start: str | date, end: str | date) -> pd.DataFrame:
        """US Treasury constant-maturity curve, 1M..30Y, decimal annual rates."""
        return self._series(
            _UST, start, end, unit="decimal annual rate", frequency="daily", scale=0.01
        )

    def russia_nominal_gdp(self, start: str | date, end: str | date) -> pd.DataFrame:
        """NGDPNSAXDCRUQ: nominal quarterly GDP, RUB million, not seasonally adjusted.

        Dates denote the START of a quarter, not its release date. The series can lag
        or be discontinued; the returned last date is not a freshness guarantee.
        """
        result = self._series(
            ("NGDPNSAXDCRUQ",), start, end, unit="RUB million", frequency="quarterly"
        )
        result = result.rename(columns={"NGDPNSAXDCRUQ": "gdp"})
        result.attrs["units"] = {"gdp": "RUB million"}
        result.attrs["seasonally_adjusted"] = False
        result.attrs["date_semantics"] = "quarter start, not publication date"
        return result
