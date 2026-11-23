"""Realized simple-return metrics; losses are signed (negative means a gain)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .data import FloatArray, ReturnKind, frozen_array
from .exceptions import ValidationError


def _vector(values: ArrayLike, minimum: int = 1) -> FloatArray:
    array = frozen_array(values)
    if array.ndim != 1 or len(array) < minimum:
        raise ValidationError(f"Expected a vector of at least {minimum} observations")
    return array


def historical_tail_risk(returns: ArrayLike, *, confidence: float = 0.95) -> tuple[float, float]:
    """(VaR, CVaR) of one-observation losses, without zero-clipping.

    VaR is the left empirical inverse CDF at confidence. CVaR integrates exactly
    the worst (1-confidence)*T observations, using fractional mass at the boundary.
    This matches the optimizer LP even when the tail count is not an integer.
    """
    r = _vector(returns)
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValidationError("confidence must lie strictly between zero and one")
    losses = np.sort(-r)
    var = float(losses[max(0, math.ceil(confidence * len(r)) - 1)])
    mass = (1 - confidence) * len(r)
    whole = int(math.floor(mass))
    worst = losses[::-1]
    # For tiny confidence, floating arithmetic can round mass to the full sample.
    boundary = (mass - whole) * float(worst[whole]) if whole < len(worst) else 0.0
    scale = float(np.max(np.abs(worst))) or 1.0
    es = (float((worst[:whole] / scale).sum()) + boundary / scale) / mass * scale
    if not math.isfinite(es):
        raise ValidationError("Tail risk exceeds representable numeric limits")
    return var, es


def turnover(previous: ArrayLike, target: ArrayLike) -> float:
    """Gross traded asset notional / pre-trade NAV (L1, not half turnover).

    Cash is excluded: pass only risky-asset exposures. Initial deployment from
    cash to a fully invested portfolio has turnover 1; switching all assets has 2.
    """
    before, after = _vector(previous), _vector(target)
    if before.shape != after.shape:
        raise ValidationError("Weight vectors must have the same shape")
    return float(np.abs(after - before).sum())


@dataclass(frozen=True)
class RiskReport:
    """Realized observation-frequency metrics; not forward-looking estimates."""

    cumulative_return: float
    annualized_return: float
    volatility: float
    sharpe: float | None
    max_drawdown: float
    var: float
    cvar: float
    observations: int
    periods_per_year: int
    annual_risk_free_rate: float
    confidence: float
    kind: ReturnKind


def risk_report(
    returns: ArrayLike,
    *,
    periods_per_year: int,
    annual_risk_free_rate: float,
    kind: ReturnKind,
    confidence: float = 0.95,
) -> RiskReport:
    """Compound performance, sample volatility and arithmetic excess Sharpe.

    Annualization is observation-based: growth^(periods_per_year/T)-1.
    Effective annual risk-free rate is converted to a constant per-period rate.
    Drawdown includes the initial unit wealth. Zero-volatility Sharpe is None.
    """
    r = _vector(returns, 2)
    if np.any(r <= -1):
        raise ValidationError("Simple returns must exceed -1")
    if type(periods_per_year) is not int or periods_per_year <= 0:
        raise ValidationError("periods_per_year must be a positive integer")
    if not math.isfinite(annual_risk_free_rate) or annual_risk_free_rate <= -1:
        raise ValidationError("annual_risk_free_rate must be finite and exceed -1")
    if kind not in ("price", "total_return"):
        raise ValidationError("Explicit price or total_return classification required")
    log_growth = np.cumsum(np.log1p(r))
    try:
        cumulative = math.expm1(float(log_growth[-1]))
        annualized = math.expm1(float(log_growth[-1]) * periods_per_year / len(r))
    except OverflowError as exc:
        raise ValidationError("Compounded performance overflows; check units/frequency") from exc
    log_wealth = np.r_[0.0, log_growth]
    drawdowns = np.expm1(log_wealth - np.maximum.accumulate(log_wealth))
    scale = float(np.max(np.abs(r))) or 1.0
    std_scaled = float(np.std(r / scale, ddof=1))
    std = std_scaled * scale
    rf = math.expm1(math.log1p(annual_risk_free_rate) / periods_per_year)
    sharpe = (
        float(((r / scale).mean() - rf / scale) / std_scaled * math.sqrt(periods_per_year))
        if std_scaled > 0
        else None
    )
    volatility = std * math.sqrt(periods_per_year)
    if not math.isfinite(volatility) or (sharpe is not None and not math.isfinite(sharpe)):
        raise ValidationError("Risk metrics exceed representable numeric limits")
    var, cvar = historical_tail_risk(r, confidence=confidence)
    return RiskReport(
        cumulative,
        annualized,
        volatility,
        sharpe,
        float(drawdowns.min()),
        var,
        cvar,
        len(r),
        periods_per_year,
        annual_risk_free_rate,
        confidence,
        kind,
    )
