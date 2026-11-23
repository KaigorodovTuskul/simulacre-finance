"""Canonical dated arrays. Missing values are rejected, never implicitly filled."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .exceptions import DataUnavailableError, ValidationError

FloatArray = NDArray[np.float64]
ReturnKind = Literal["price", "total_return"]


def iso_date(value: str | date) -> date:
    """Parse strictly YYYY-MM-DD; timestamps and abbreviated dates are rejected."""
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValidationError("Expected an ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid date: {value}") from exc


def frozen_array(values: ArrayLike) -> FloatArray:
    """Own a read-only float64 copy, independent of caller mutation."""
    try:
        if np.iscomplexobj(values):
            raise ValidationError("Complex financial observations are unsupported")
        array = np.array(values, dtype=np.float64, copy=True)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValidationError("Expected a rectangular numeric array") from exc
    if not np.isfinite(array).all():
        raise ValidationError("Missing or non-finite values; align/drop explicitly before analysis")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class Metadata:
    """One base currency and return provenance for all asset columns.

    periods_per_year is an explicit observation-count annualization assumption,
    not an inferred exchange calendar. as_of is a caller/provider observation vintage.
    """

    currency: str
    periods_per_year: int
    source: str
    as_of: date
    kind: ReturnKind = "price"
    adjustment: str = "unadjusted"
    frequency: str = "daily"

    def __post_init__(self) -> None:
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValidationError("currency must be a three-letter uppercase ISO currency code")
        if type(self.periods_per_year) is not int or self.periods_per_year <= 0:
            raise ValidationError("periods_per_year must be a positive integer")
        if self.kind not in ("price", "total_return"):
            raise ValidationError("kind must be price or total_return")
        if not all(
            isinstance(x, str) and x.strip() for x in (self.source, self.adjustment, self.frequency)
        ):
            raise ValidationError("source, adjustment and frequency must be explicit")
        object.__setattr__(self, "as_of", iso_date(self.as_of))


def _contract(
    dates: tuple[date, ...],
    assets: tuple[str, ...],
    values: ArrayLike,
    metadata: Metadata,
) -> tuple[tuple[date, ...], tuple[str, ...], FloatArray]:
    days = tuple(iso_date(x) for x in dates)
    names = tuple(assets)
    array = frozen_array(values)
    if not days or not names or array.shape != (len(days), len(names)):
        raise ValidationError("Expected a nonempty dates-by-assets matrix")
    if any(a >= b for a, b in zip(days, days[1:], strict=False)):
        raise ValidationError("Dates must be unique and strictly increasing")
    if any(not isinstance(x, str) or not x.strip() for x in names) or len(set(names)) != len(names):
        raise ValidationError("Asset identifiers must be nonempty and unique")
    if not isinstance(metadata, Metadata) or metadata.as_of < days[-1]:
        raise ValidationError("metadata.as_of cannot precede the last observation")
    return days, names, array


@dataclass(frozen=True)
class PriceData:
    """Positive dated prices or externally supplied total-return index levels."""

    dates: tuple[date, ...]
    assets: tuple[str, ...]
    values: FloatArray
    metadata: Metadata

    def __post_init__(self) -> None:
        days, names, array = _contract(self.dates, self.assets, self.values, self.metadata)
        if np.any(array <= 0):
            raise ValidationError("Prices/index levels must be strictly positive")
        object.__setattr__(self, "dates", days)
        object.__setattr__(self, "assets", names)
        object.__setattr__(self, "values", array)

    def returns(self) -> ReturnData:
        """Explicit decimal simple returns; no dividends/coupons are inferred."""
        if len(self.dates) < 2:
            raise ValidationError("At least two price observations are required")
        return ReturnData(
            self.dates[1:], self.assets, self.values[1:] / self.values[:-1] - 1, self.metadata
        )


@dataclass(frozen=True)
class ReturnData:
    """Decimal simple interval returns dated at each interval's end.

    Irregular dates are allowed; no absent sessions are synthesized. Annualization
    still uses metadata.periods_per_year, so align/regrid before cross-frequency work.
    Returns <= -100% are rejected: bankruptcy/delisting handling is outside v0.1.
    """

    dates: tuple[date, ...]
    assets: tuple[str, ...]
    values: FloatArray
    metadata: Metadata

    def __post_init__(self) -> None:
        days, names, array = _contract(self.dates, self.assets, self.values, self.metadata)
        if np.any(array <= -1):
            raise ValidationError("Simple returns must exceed -1; bankruptcy is unsupported")
        object.__setattr__(self, "dates", days)
        object.__setattr__(self, "assets", names)
        object.__setattr__(self, "values", array)

    def window(self, start: int, stop: int) -> ReturnData:
        """Return a validated chronological slice [start, stop)."""
        return ReturnData(
            self.dates[start:stop], self.assets, self.values[start:stop], self.metadata
        )


def load_csv(path: str | Path, *, metadata: Metadata) -> PriceData:
    """Read UTF-8 wide CSV: date,ASSET_A,ASSET_B. No sorting/filling or adjustment."""
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DataUnavailableError(f"Cannot read CSV: {path}") from exc
    if len(rows) < 2 or len(rows[0]) < 2 or rows[0][0] != "date":
        raise ValidationError("CSV must contain header date,ASSET... and observations")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValidationError("CSV contains incomplete or extra fields")
    try:
        values = frozen_array([[float(x) for x in row[1:]] for row in rows[1:]])
    except ValueError as exc:
        raise ValidationError("CSV prices must be numeric and complete") from exc
    return PriceData(
        tuple(iso_date(row[0]) for row in rows[1:]), tuple(rows[0][1:]), values, metadata
    )
