"""Thin offline boundary for existing Portfolio Lab date->level sleeve responses."""

from collections.abc import Mapping
from datetime import date

import numpy as np

from simulacre_finance import Metadata, PriceData, ValidationError, optimize


def sleeve_prices(
    series: Mapping[str, Mapping[str, float]],
    *,
    metadata: Metadata,
) -> PriceData:
    """Map src.portfolio.engine.run_backtest's existing series contract.

    Require identical date sets: the adapter does not silently forward-fill like
    the legacy sleeve engine. Asset values must already share a currency and kind.
    The host is responsible for point-in-time selection and authorized provenance.
    """
    if not series:
        raise ValidationError("No sleeves supplied")
    assets = tuple(series)
    days = sorted(series[assets[0]])
    if any(set(series[key]) != set(days) for key in assets):
        raise ValidationError("Align all sleeves explicitly before mapping")
    values = np.array([[series[key][day] for key in assets] for day in days])
    return PriceData(tuple(date.fromisoformat(day) for day in days), assets, values, metadata)


def optimize_sleeves(
    series: Mapping[str, Mapping[str, float]],
    *,
    metadata: Metadata,
) -> dict[str, float]:
    """Real function suitable for an authenticated thin MCP wrapper in the host."""
    data = sleeve_prices(series, metadata=metadata).returns()
    result = optimize(data, "minimum_variance")
    return dict(zip(result.assets, result.weights.tolist(), strict=True))
