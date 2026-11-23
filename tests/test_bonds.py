from datetime import date

import pytest

from simulacre_finance import ValidationError
from simulacre_finance.bonds import (
    CashFlow,
    FixedCashflows,
    bond_analytics,
    fixed_rate_bullet,
    year_fraction,
    yield_to_maturity,
)

SETTLED = date(2024, 1, 1)


def bullet():
    return fixed_rate_bullet(
        identifier="DEMO",
        currency="RUB",
        issue=SETTLED,
        maturity=date(2026, 1, 1),
        face=1000,
        coupon_rate=0.1,
        payments_per_year=1,
    )


def test_par_bond_and_clean_price():
    bond = bullet()
    # 30E/360 makes each annual payment exactly one year apart.
    result = bond_analytics(
        bond, SETTLED, 0.1, payments_per_year=1, day_count="30E/360", accrued_interest=5
    )
    assert result.dirty_price == pytest.approx(1000)
    assert result.clean_price == pytest.approx(995)
    duration = (100 / 1.1 + 2 * 1100 / 1.1**2) / 1000
    assert result.macaulay_duration == pytest.approx(duration)
    assert result.modified_duration == pytest.approx(duration / 1.1)
    assert result.convexity == pytest.approx((2 * 100 / 1.1**3 + 6 * 1100 / 1.1**4) / 1000)


@pytest.mark.parametrize("yield_", [-0.5, -0.01, 0, 0.07, 0.5, 2.0])
@pytest.mark.parametrize("day_count", ["ACT/365F", "ACT/360", "30E/360"])
def test_yield_round_trip_and_sensitivities(yield_, day_count):
    bond = bullet()
    result = bond_analytics(bond, SETTLED, yield_, day_count=day_count)
    assert result.clean_price is None
    assert yield_to_maturity(
        bond, SETTLED, result.dirty_price, day_count=day_count
    ) == pytest.approx(yield_)
    h = 1e-4
    up = bond_analytics(bond, SETTLED, yield_ + h, day_count=day_count).dirty_price
    down = bond_analytics(bond, SETTLED, yield_ - h, day_count=day_count).dirty_price
    assert -(up - down) / (2 * h) / result.dirty_price == pytest.approx(
        result.modified_duration, rel=1e-6
    )
    assert (up + down - 2 * result.dirty_price) / h**2 / result.dirty_price == pytest.approx(
        result.convexity, rel=1e-6
    )


def test_zero_coupon_payment_boundaries_and_schedule():
    bond = fixed_rate_bullet(
        identifier="ZERO",
        currency="RUB",
        issue=SETTLED,
        maturity=date(2025, 1, 1),
        face=100,
        coupon_rate=0,
    )
    assert len(bond.flows) == 1
    assert bond_analytics(
        bond, SETTLED, 0.1, payments_per_year=1, day_count="30E/360"
    ).dirty_price == pytest.approx(100 / 1.1)
    with pytest.raises(ValidationError, match="No payments"):
        bond_analytics(bond, date(2025, 1, 1), 0.1)
    result = bond_analytics(
        bullet(), date(2025, 1, 1), 0.1, payments_per_year=1, day_count="30E/360"
    )
    assert result.dirty_price == pytest.approx(1000)  # coupon on settlement excluded
    eom = fixed_rate_bullet(
        identifier="EOM",
        currency="RUB",
        issue=date(2023, 8, 31),
        maturity=date(2024, 8, 31),
        face=100,
        coupon_rate=0.1,
    )
    assert eom.flows[0].payment_date == date(2024, 2, 29)
    assert year_fraction(SETTLED, date(2025, 1, 1)) == pytest.approx(366 / 365)


def test_reject_unknown_incomplete_or_bad_terms():
    with pytest.raises(ValidationError):
        CashFlow(date(2025, 1, 1), float("nan"))
    with pytest.raises(ValidationError):
        FixedCashflows("EMPTY", "RUB", ())
    with pytest.raises(ValidationError, match="Stub"):
        fixed_rate_bullet(
            identifier="STUB",
            currency="RUB",
            issue=date(2024, 2, 1),
            maturity=date(2025, 1, 1),
            face=100,
            coupon_rate=0.1,
        )
    with pytest.raises(ValidationError):
        bond_analytics(bullet(), SETTLED, -2)
    with pytest.raises(ValidationError):
        yield_to_maturity(bullet(), SETTLED, 0)
