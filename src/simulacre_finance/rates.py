"""Small currency-agnostic cash accrual primitive; no provider dependencies."""

import math

from .exceptions import ValidationError


def simple_accrual_factor(annual_rate: float, days: int, *, basis: int = 365) -> float:
    """1 + decimal annual rate * actual days / basis (ACT/365F or ACT/360).

    This is simple interest, not an effective annual compounded rate.
    """
    if not math.isfinite(annual_rate) or type(days) is not int or days < 0:
        raise ValidationError("Finite decimal rate and nonnegative integer days required")
    if basis not in (360, 365):
        raise ValidationError("basis must be 360 or 365")
    result = 1 + annual_rate * days / basis
    if not math.isfinite(result) or result <= 0:
        raise ValidationError("Accrual factor must remain positive and finite")
    return result
