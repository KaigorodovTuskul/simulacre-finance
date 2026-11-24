"""Annual nominal GDP from the public World Bank Indicators JSON API."""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any

from ..exceptions import DataUnavailableError, ValidationError
from ._common import HTTPSource, frame, number

if TYPE_CHECKING:
    import pandas as pd


class WorldBank(HTTPSource):
    """Annual country data; missing years stay NaN, no built-in historical estimates."""

    def nominal_gdp(self, start_year: int, end_year: int, *, country: str = "RUS") -> pd.DataFrame:
        """NY.GDP.MKTP.CN in current local currency; dates are year-start labels."""
        if (
            type(start_year) is not int
            or type(end_year) is not int
            or not 1960 <= start_year <= end_year <= 9998
        ):
            raise ValidationError("Expected ordered integer years >= 1960")
        if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{3}", country):
            raise ValidationError("Expected a three-letter country code, e.g. RUS")
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/NY.GDP.MKTP.CN"
        rows: list[dict[str, Any]] = []
        # A single-country interval fits in one 10,000-row page; verify it is complete.
        try:
            payload = self._request(
                "GET",
                url,
                params={
                    "format": "json",
                    "date": f"{start_year}:{end_year}",
                    "per_page": 10000,
                },
            ).json()
            meta, items = payload
            if (
                not isinstance(meta, dict)
                or not isinstance(items, list)
                or int(meta["pages"]) != 1
                or int(meta["total"]) != len(items)
            ):
                raise ValueError("Incomplete World Bank response")
            for item in items:
                if (
                    item["countryiso3code"] != country
                    or item["indicator"]["id"] != "NY.GDP.MKTP.CN"
                ):
                    raise ValueError("Different World Bank country/indicator")
                year = int(item["date"])
                if not start_year <= year <= end_year:
                    raise ValueError("Out-of-range World Bank year")
                rows.append(
                    {
                        "date": date(year, 1, 1),
                        "gdp": None if item["value"] is None else number(item["value"]),
                    }
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataUnavailableError("Invalid or incomplete World Bank GDP response") from exc
        result = frame(
            rows,
            {"gdp": "current local currency"},
            source=url,
            frequency="annual",
            start=date(start_year, 1, 1),
            end=date(end_year, 12, 31),
        )
        result.attrs["country"] = country
        result.attrs["date_semantics"] = "year start label, not publication date"
        return result
