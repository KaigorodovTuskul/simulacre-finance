"""Deterministic positive fixed cash flows, nominal periodic yield and dated discounting."""

from __future__ import annotations

import calendar
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

from .data import FloatArray, iso_date
from .exceptions import ValidationError

DayCount = Literal["ACT/365F", "ACT/360", "30E/360"]


def year_fraction(start: date, end: date, convention: DayCount = "ACT/365F") -> float:
    """Actual fixed denominator or European 30/360 (both month days capped at 30)."""
    first, last = iso_date(start), iso_date(end)
    if last < first:
        raise ValidationError("End date cannot precede start date")
    if convention == "ACT/365F":
        return (last - first).days / 365
    if convention == "ACT/360":
        return (last - first).days / 360
    if convention == "30E/360":
        return (
            (last.year - first.year) * 360
            + (last.month - first.month) * 30
            + min(last.day, 30)
            - min(first.day, 30)
        ) / 360
    raise ValidationError("Unsupported day count")


@dataclass(frozen=True)
class CashFlow:
    """Known payment amount in the contract currency, not percent of par."""

    payment_date: date
    amount: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "payment_date", iso_date(self.payment_date))
        if not math.isfinite(self.amount) or self.amount <= 0:
            raise ValidationError("Cash-flow amount must be known, finite and positive")


@dataclass(frozen=True)
class FixedCashflows:
    """Complete contractual dated payments supplied by caller; no exercise/default model.

    A caller may explicitly include known principal amortizations as dated amounts.
    The library never invents an unknown redemption, coupon reset or option exercise.
    """

    identifier: str
    currency: str
    flows: tuple[CashFlow, ...]

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValidationError("Identifier and uppercase three-letter currency required")
        flows = tuple(self.flows)
        if not flows or any(not isinstance(x, CashFlow) for x in flows):
            raise ValidationError("A complete nonempty fixed cash-flow schedule is required")
        if any(a.payment_date >= b.payment_date for a, b in zip(flows, flows[1:], strict=False)):
            raise ValidationError("Combine same-day payments; dates must strictly increase")
        object.__setattr__(self, "flows", flows)


def _month_shift(anchor: date, months: int) -> date:
    ordinal = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(ordinal, 12)
    month += 1
    end = calendar.monthrange(year, month)[1]
    anchor_end = anchor.day == calendar.monthrange(anchor.year, anchor.month)[1]
    return date(year, month, end if anchor_end else min(anchor.day, end))


def fixed_rate_bullet(
    *,
    identifier: str,
    currency: str,
    issue: date,
    maturity: date,
    face: float,
    coupon_rate: float,
    payments_per_year: int = 2,
) -> FixedCashflows:
    """Regular fixed-rate bullet, maturity-anchored calendar schedule, no stub periods.

    Coupon = face * decimal annual coupon / payments_per_year. Unadjusted calendar
    dates, end-of-month anchoring, no holiday/ex-coupon rule. Only full regular
    periods are accepted. For real market conventions supply explicit cash flows.
    Floating/optional terms are not accepted by this fixed-rate convenience API.
    """
    first, last = iso_date(issue), iso_date(maturity)
    if (
        type(payments_per_year) is not int
        or payments_per_year not in (1, 2, 4, 12)
        or first >= last
    ):
        raise ValidationError("Ordered issue/maturity and frequency 1, 2, 4 or 12 required")
    if not math.isfinite(face) or face <= 0 or not math.isfinite(coupon_rate) or coupon_rate < 0:
        raise ValidationError("Positive face and known nonnegative fixed coupon required")
    step = 12 // payments_per_year
    months = (last.year - first.year) * 12 + last.month - first.month
    if months <= 0 or months % step or _month_shift(last, -months) != first:
        raise ValidationError("Stub/incomplete periods unsupported; supply explicit cash flows")
    coupon = face * coupon_rate / payments_per_year
    dates = [_month_shift(last, -m) for m in range(months - step, -1, -step)]
    flows = tuple(
        CashFlow(day, coupon + (face if day == last else 0))
        for day in dates
        if coupon > 0 or day == last
    )
    return FixedCashflows(identifier, currency, flows)


def _future(
    bond: FixedCashflows,
    settlement: date,
    day_count: DayCount,
    payments_per_year: int,
) -> tuple[FloatArray, FloatArray]:
    if type(payments_per_year) is not int or payments_per_year <= 0:
        raise ValidationError("Yield compounding frequency must be a positive integer")
    settled = iso_date(settlement)
    year_fraction(settled, settled, day_count)
    flows = [flow for flow in bond.flows if flow.payment_date > settled]
    if not flows:
        raise ValidationError("No payments strictly after settlement")
    times = np.array([year_fraction(settled, flow.payment_date, day_count) for flow in flows])
    if np.any(times <= 0):
        raise ValidationError("Day count collapses a future payment to zero time")
    return times, np.log([flow.amount for flow in flows])


@dataclass(frozen=True)
class BondAnalytics:
    """Prices in currency per supplied notional; sensitivities to decimal annual yield."""

    dirty_price: float
    clean_price: float | None
    accrued_interest: float | None
    macaulay_duration: float
    modified_duration: float
    convexity: float
    nominal_yield: float
    payments_per_year: int
    day_count: DayCount


def bond_analytics(
    bond: FixedCashflows,
    settlement: date,
    nominal_yield: float,
    *,
    payments_per_year: int = 2,
    day_count: DayCount = "ACT/365F",
    accrued_interest: float | None = None,
) -> BondAnalytics:
    """PV=sum(CF/(1+y/m)^(m*t)), duration and exact second derivative/P.

    Settlement-date payments are excluded. Accrued interest, if supplied, must be
    a nonnegative amount under the caller's explicit instrument convention. We do
    not infer it from an incomplete schedule. Clean = dirty - supplied accrued.
    """
    times, logs = _future(bond, settlement, day_count, payments_per_year)
    if not math.isfinite(nominal_yield) or nominal_yield <= -payments_per_year:
        raise ValidationError("Nominal yield must be finite and exceed -compounding frequency")
    base = 1 + nominal_yield / payments_per_year
    logpv = logs - payments_per_year * times * math.log(base)
    logprice = float(logsumexp(logpv))
    try:
        price = math.exp(logprice)
    except OverflowError as exc:
        raise ValidationError("PV overflows for this yield/schedule") from exc
    if not math.isfinite(price) or price <= 0:
        raise ValidationError("PV must be representable as a positive finite number")
    weights = np.exp(logpv - logprice)
    macaulay = float(weights @ times)
    convexity = float(weights @ ((times / base) * ((times + 1 / payments_per_year) / base)))
    if accrued_interest is not None and (
        not math.isfinite(accrued_interest) or accrued_interest < 0 or accrued_interest > price
    ):
        raise ValidationError("Accrued interest must be a finite amount between 0 and dirty price")
    if not all(math.isfinite(x) for x in (macaulay, macaulay / base, convexity)):
        raise ValidationError("Bond sensitivities exceed representable numeric limits")
    return BondAnalytics(
        price,
        None if accrued_interest is None else price - accrued_interest,
        accrued_interest,
        macaulay,
        macaulay / base,
        convexity,
        nominal_yield,
        payments_per_year,
        day_count,
    )


def yield_to_maturity(
    bond: FixedCashflows,
    settlement: date,
    dirty_price: float,
    *,
    payments_per_year: int = 2,
    day_count: DayCount = "ACT/365F",
) -> float:
    """Unique nominal annual yield for positive known flows and a positive dirty price.

    Brent root in log(1+y/m) handles negative yields without crossing -m.
    No unsupported multiple-root IRR is reported for mixed-sign cash flows.
    """
    times, logs = _future(bond, settlement, day_count, payments_per_year)
    if not math.isfinite(dirty_price) or dirty_price <= 0:
        raise ValidationError("YTM requires a positive finite dirty price in currency units")

    def objective(z: float) -> float:
        return float(logsumexp(logs - payments_per_year * times * z)) - math.log(dirty_price)

    bound = 1.0
    while (objective(-bound) < 0 or objective(bound) > 0) and bound < 1048576:
        bound *= 2
    if objective(-bound) < 0 or objective(bound) > 0:
        raise ValidationError("Yield cannot be bracketed within numeric limits")
    z = brentq(objective, -bound, bound, xtol=1e-14)
    try:
        result = payments_per_year * math.expm1(z)
    except OverflowError as exc:
        raise ValidationError("Yield is outside representable numeric limits") from exc
    if not math.isfinite(result) or result <= -payments_per_year:
        raise ValidationError("Yield is outside representable numeric limits")
    return result
