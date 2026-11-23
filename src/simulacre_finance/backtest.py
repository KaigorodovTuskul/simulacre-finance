"""Close-to-close, self-financing, chronological portfolio research. No synthetic fills."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.optimize import brentq

from .data import FloatArray, Metadata, ReturnData, frozen_array
from .exceptions import OptimizationError, ValidationError
from .portfolio import METHODS, Method, optimize
from .risk import RiskReport, risk_report


@dataclass(frozen=True)
class Rebalance:
    """Decision has training_end <= execution - lag; costs include buys and sells."""

    training_start: date
    training_end: date
    execution_date: date
    target_weights: FloatArray
    pre_trade_nav: float
    post_trade_nav: float
    turnover: float
    cost: float
    solver: str


@dataclass(frozen=True)
class BacktestResult:
    """Equity starts in cash; weights are post-close, with a separate cash column.

    turnover/costs arrays align with dates, initial values zero. Returns align with
    dates[1:]. drawdown includes initial capital. Trades are self-financing; costs
    are charged at execution. Results preserve data classification/provenance.
    """

    dates: tuple[date, ...]
    assets: tuple[str, ...]
    equity: FloatArray
    weights: FloatArray
    cash_weights: FloatArray
    returns: FloatArray
    turnover: FloatArray
    costs: FloatArray
    drawdown: FloatArray
    rebalances: tuple[Rebalance, ...]
    metrics: RiskReport
    metadata: Metadata
    method: Method


def walk_forward(
    data: ReturnData,
    method: Method = "equal_weight",
    *,
    lookback: int = 20,
    rebalance_every: int = 5,
    execution_lag: int = 1,
    initial_capital: float = 1.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    bounds: tuple[tuple[float, float], ...] | None = None,
    budget: float = 1.0,
    confidence: float = 0.95,
    annual_risk_free_rate: float = 0.0,
) -> BacktestResult:
    """Rolling training and close execution; integer schedules count observations.

    After lookback observations, evaluation begins entirely in cash. First signal
    uses that window and executes execution_lag observed closes later. Return for
    each execution date is earned by OLD holdings; new weights apply to the NEXT
    observation. Between rebalances, holdings drift with asset returns. Cash earns
    zero (risk-free rate is only a metric reference). Costs are decimal bps of
    actual gross asset trades, including initial purchases. No borrowing/shorts,
    volume/market impact, or exchange-calendar invention. Solver failures raise.
    """
    for name, value, minimum in (
        ("lookback", lookback, 2),
        ("rebalance_every", rebalance_every, 1),
        ("execution_lag", execution_lag, 1),
    ):
        if type(value) is not int or value < minimum:
            raise ValidationError(f"{name} must be an integer >= {minimum}")
    if len(data.dates) < lookback + execution_lag + 2:
        raise ValidationError("Insufficient history for training, lag and two evaluation returns")
    if not math.isfinite(initial_capital) or initial_capital <= 0:
        raise ValidationError("Positive finite initial_capital required")
    if any(not math.isfinite(x) or x < 0 for x in (commission_bps, slippage_bps)):
        raise ValidationError("Costs must be finite nonnegative basis points")
    cost_rate = (commission_bps + slippage_bps) / 10000
    if cost_rate >= 1:
        raise ValidationError("Combined cost rate must be below 100% of traded notional")
    if method not in METHODS:
        raise ValidationError("Unknown portfolio method")
    # Validate risk arguments before beginning a potentially expensive simulation.
    risk_report(
        [0, 0],
        periods_per_year=data.metadata.periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        kind=data.metadata.kind,
        confidence=confidence,
    )
    start = lookback - 1
    nav = initial_capital
    holdings = np.zeros(len(data.assets))
    cash = initial_capital
    dates, equity, weights, cash_weights = [data.dates[start]], [nav], [holdings.copy()], [1.0]
    turns, costs, logs = [0.0], [0.0], []
    for t in range(start + 1, len(data.dates)):
        holdings *= 1 + data.values[t]
        nav = float(holdings.sum() + cash)
        if not math.isfinite(nav) or nav <= 0:
            raise ValidationError("Portfolio NAV became nonpositive/nonfinite")
        cost, traded = 0.0, 0.0
        decision = t - execution_lag
        if decision >= start and (decision - start) % rebalance_every == 0:
            training = data.window(decision - lookback + 1, decision + 1)
            solution = optimize(
                training, method, bounds=bounds, budget=budget, confidence=confidence
            )
            target = solution.weights

            # Solve C = fee * sum(abs((NAV-C)*target - old_holdings)). This
            # accounts for fees without borrowing cash or overinvesting capital.
            def fee_balance(
                fraction: float,
                allocation: FloatArray = target,
                old_weights: FloatArray = holdings / nav,
            ) -> float:
                traded_fraction = float(np.abs((1 - fraction) * allocation - old_weights).sum())
                return fraction - cost_rate * traded_fraction

            # A dimensionless root keeps fees invariant to portfolio capital scale.
            cost = nav * brentq(fee_balance, 0, 1, xtol=1e-14) if cost_rate else 0
            new_holdings = (nav - cost) * target
            traded = float(np.abs(new_holdings - holdings).sum()) / nav
            pre_nav = nav
            holdings = new_holdings
            cash = (nav - cost) * (1 - float(target.sum()))
            nav = float(holdings.sum() + cash)
            if cash < -pre_nav * 1e-7 or nav <= 0:
                raise OptimizationError("Rebalance accounting produced invalid cash or NAV")
            logs.append(
                Rebalance(
                    training.dates[0],
                    training.dates[-1],
                    data.dates[t],
                    frozen_array(target),
                    pre_nav,
                    nav,
                    traded,
                    cost,
                    solution.solver,
                )
            )
        dates.append(data.dates[t])
        equity.append(nav)
        weights.append(holdings / nav)
        cash_weights.append(cash / nav)
        turns.append(traded)
        costs.append(cost)
    curve = frozen_array(equity)
    realized = frozen_array(curve[1:] / curve[:-1] - 1)
    metrics = risk_report(
        realized,
        periods_per_year=data.metadata.periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        kind=data.metadata.kind,
        confidence=confidence,
    )
    return BacktestResult(
        tuple(dates),
        data.assets,
        curve,
        frozen_array(weights),
        frozen_array(cash_weights),
        realized,
        frozen_array(turns),
        frozen_array(costs),
        frozen_array(curve / np.maximum.accumulate(curve) - 1),
        tuple(logs),
        metrics,
        data.metadata,
        method,
    )


def compare_methods(
    data: ReturnData,
    *,
    lookback: int = 20,
    rebalance_every: int = 5,
    execution_lag: int = 1,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    bounds: tuple[tuple[float, float], ...] | None = None,
    budget: float = 1.0,
    confidence: float = 0.95,
    annual_risk_free_rate: float = 0.0,
) -> dict[Method, BacktestResult]:
    """All four methods on identical data, windows, constraints and costs.

    Exact ERC/equal-weight infeasibility raises; never quietly omit a failed method.
    """
    return {
        method: walk_forward(
            data,
            method,
            lookback=lookback,
            rebalance_every=rebalance_every,
            execution_lag=execution_lag,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            bounds=bounds,
            budget=budget,
            confidence=confidence,
            annual_risk_free_rate=annual_risk_free_rate,
        )
        for method in METHODS
    }
