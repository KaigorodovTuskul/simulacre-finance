"""Independent financial computation; see individual modules for assumptions."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .exceptions import (
    DataUnavailableError,
    FinanceError,
    InfeasibleError,
    OptimizationError,
    ValidationError,
)
from .rates import simple_accrual_factor

if TYPE_CHECKING:
    from .backtest import BacktestResult, Rebalance, compare_methods, walk_forward
    from .bonds import (
        BondAnalytics,
        CashFlow,
        FixedCashflows,
        bond_analytics,
        fixed_rate_bullet,
        year_fraction,
        yield_to_maturity,
    )
    from .data import Metadata, PriceData, ReturnData, load_csv
    from .macro import CBR, FRED, MOEXMacro, WorldBank
    from .portfolio import METHODS, OptimizationResult, optimize
    from .providers import Instrument, MoexISS
    from .risk import RiskReport, historical_tail_risk, risk_report, turnover

# Keep cash accrual imports free of NumPy/SciPy startup costs; static analyzers
# still see the explicit typed exports above.
_LAZY = {
    **dict.fromkeys(("CBR", "FRED", "MOEXMacro", "WorldBank"), "macro"),
    **dict.fromkeys(("BacktestResult", "Rebalance", "compare_methods", "walk_forward"), "backtest"),
    **dict.fromkeys(
        (
            "BondAnalytics",
            "CashFlow",
            "FixedCashflows",
            "bond_analytics",
            "fixed_rate_bullet",
            "year_fraction",
            "yield_to_maturity",
        ),
        "bonds",
    ),
    **dict.fromkeys(("Metadata", "PriceData", "ReturnData", "load_csv"), "data"),
    **dict.fromkeys(("METHODS", "OptimizationResult", "optimize"), "portfolio"),
    **dict.fromkeys(("Instrument", "MoexISS"), "providers"),
    **dict.fromkeys(("RiskReport", "historical_tail_risk", "risk_report", "turnover"), "risk"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_LAZY[name]}", __name__), name)
    globals()[name] = value
    return value


__version__ = "0.2.0"
__all__ = [
    "CBR",
    "FRED",
    "MOEXMacro",
    "WorldBank",
    "Metadata",
    "PriceData",
    "ReturnData",
    "load_csv",
    "simple_accrual_factor",
    "FinanceError",
    "ValidationError",
    "DataUnavailableError",
    "OptimizationError",
    "InfeasibleError",
    "BacktestResult",
    "Rebalance",
    "compare_methods",
    "walk_forward",
    "BondAnalytics",
    "CashFlow",
    "FixedCashflows",
    "bond_analytics",
    "fixed_rate_bullet",
    "year_fraction",
    "yield_to_maturity",
    "METHODS",
    "OptimizationResult",
    "optimize",
    "Instrument",
    "MoexISS",
    "RiskReport",
    "historical_tail_risk",
    "risk_report",
    "turnover",
]
