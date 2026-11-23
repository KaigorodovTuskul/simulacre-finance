from datetime import date, timedelta

import numpy as np
import pytest

from simulacre_finance import Metadata, ReturnData, ValidationError
from simulacre_finance.backtest import compare_methods, walk_forward


def one_asset(values):
    days = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(len(values)))
    return ReturnData(
        days, ("A",), np.array(values)[:, None], Metadata("RUB", 252, "synthetic", days[-1])
    )


def test_hand_path_execution_after_return_and_self_financing_costs():
    data = one_asset([0, 0, 0.5, 0.1, -0.2, 0])
    result = walk_forward(data, lookback=2, rebalance_every=99, commission_bps=100)
    # Evaluation starts at day 1 in cash; buy at day 2 AFTER the 50% move.
    purchase = 1 / 1.01
    np.testing.assert_allclose(
        result.equity, [1, purchase, purchase * 1.1, purchase * 1.1 * 0.8, purchase * 1.1 * 0.8]
    )
    assert result.costs.sum() == pytest.approx(purchase * 0.01)
    assert result.turnover.sum() == pytest.approx(purchase)
    assert result.metrics.cumulative_return == pytest.approx(result.equity[-1] - 1)
    assert result.rebalances[0].training_end == data.dates[1]
    assert result.rebalances[0].execution_date == data.dates[2]


@pytest.mark.parametrize("capital", [1e-300, 1e-12, 1e12])
def test_costs_are_invariant_to_capital_scale(capital):
    data = one_asset([0, 0, 0.5, 0.1, -0.2, 0])
    result = walk_forward(
        data, lookback=2, rebalance_every=99, commission_bps=100, initial_capital=capital
    )
    np.testing.assert_allclose(
        result.equity / capital, [1, 1 / 1.01, 1.1 / 1.01, 0.88 / 1.01, 0.88 / 1.01]
    )
    assert result.costs.sum() / capital == pytest.approx(1 / 101)


def test_no_future_observations_and_execution_lag(scenarios):
    first = walk_forward(scenarios, "minimum_variance", lookback=10, execution_lag=3)
    changed = scenarios.values.copy()
    changed[60:] *= 5
    future = ReturnData(scenarios.dates, scenarios.assets, changed, scenarios.metadata)
    second = walk_forward(future, "minimum_variance", lookback=10, execution_lag=3)
    np.testing.assert_array_equal(first.equity[:51], second.equity[:51])
    np.testing.assert_array_equal(first.weights[:51], second.weights[:51])
    for trade in first.rebalances:
        execution = scenarios.dates.index(trade.execution_date)
        assert trade.training_end == scenarios.dates[execution - 3]
    assert first.rebalances[0].execution_date == scenarios.dates[12]


def test_drift_cash_budget_cost_and_comparison(scenarios):
    results = compare_methods(
        scenarios, lookback=12, rebalance_every=7, commission_bps=10, slippage_bps=5, budget=0.8
    )
    assert len(results) == 4
    for result in results.values():
        np.testing.assert_allclose(result.weights.sum(axis=1) + result.cash_weights, 1)
        assert result.costs.sum() > 0
        assert result.metrics.kind == "price"
        for trade in result.rebalances:
            assert trade.pre_trade_nav - trade.post_trade_nav == pytest.approx(trade.cost)
            assert trade.cost == pytest.approx(trade.pre_trade_nav * trade.turnover * 0.0015)
    assert len({result.dates for result in results.values()}) == 1


@pytest.mark.parametrize(
    "kwargs",
    [{"execution_lag": 0}, {"lookback": 100}, {"commission_bps": -1}, {"slippage_bps": 10000}],
)
def test_invalid_backtest(scenarios, kwargs):
    with pytest.raises(ValidationError):
        walk_forward(scenarios, **kwargs)
