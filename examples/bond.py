"""Offline known fixed cash flows -> price/yield/duration. No provider data."""

import json
from dataclasses import asdict
from datetime import date

from simulacre_finance import bond_analytics, fixed_rate_bullet, yield_to_maturity


def main() -> None:
    settlement = date(2024, 1, 1)
    bond = fixed_rate_bullet(
        identifier="SYNTHETIC_FIXED",
        currency="RUB",
        issue=settlement,
        maturity=date(2026, 1, 1),
        face=1000,
        coupon_rate=0.1,
        payments_per_year=1,
    )
    result = bond_analytics(
        bond,
        settlement,
        0.1,
        payments_per_year=1,
        day_count="30E/360",
        accrued_interest=0,  # settlement is on issue date, no accrued coupon
    )
    solved = yield_to_maturity(
        bond,
        settlement,
        result.dirty_price,
        payments_per_year=1,
        day_count="30E/360",
    )
    assert abs(result.dirty_price - 1000) < 1e-8
    assert abs(solved - 0.1) < 1e-10
    print(
        json.dumps(
            {"analytics": asdict(result), "recovered_nominal_yield": solved},
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
