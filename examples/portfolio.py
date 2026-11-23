"""Offline CSV -> all four optimizers -> walk-forward -> realized risk report.

Dataset is authored synthetic price levels, not observations of real securities.
Run with an installed wheel: python examples/portfolio.py
"""

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from simulacre_finance import Metadata, compare_methods, load_csv, optimize


def main() -> None:
    prices = load_csv(
        Path(__file__).with_name("synthetic_prices.csv"),
        metadata=Metadata("RUB", 252, "authored synthetic daily prices", date(2024, 6, 30)),
    )
    returns = prices.returns()
    comparison = compare_methods(
        returns,
        lookback=12,
        rebalance_every=5,
        commission_bps=5,
        slippage_bps=2,
        annual_risk_free_rate=0.05,
    )
    output = {}
    for method, backtest in comparison.items():
        estimate = optimize(returns, method)
        output[method] = {
            "in_sample_weights": dict(zip(returns.assets, estimate.weights.tolist(), strict=True)),
            "out_of_sample_realized_metrics": asdict(backtest.metrics),
            "rebalance_count": len(backtest.rebalances),
            "gross_turnover": float(backtest.turnover.sum()),
            "costs_per_initial_unit": float(backtest.costs.sum()),
        }
    print(json.dumps(output, indent=2, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
