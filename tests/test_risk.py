import numpy as np
import pytest

from simulacre_finance import ValidationError
from simulacre_finance.risk import historical_tail_risk, risk_report, turnover


def test_hand_calculated_path():
    r = [0.1, -0.2, 0.25]
    report = risk_report(
        r, periods_per_year=3, annual_risk_free_rate=0, kind="price", confidence=0.5
    )
    assert report.cumulative_return == pytest.approx(0.1)
    assert report.annualized_return == pytest.approx(0.1)
    assert report.max_drawdown == pytest.approx(-0.2)
    assert report.volatility == pytest.approx(np.std(r, ddof=1) * np.sqrt(3))
    assert report.sharpe == pytest.approx(np.mean(r) / np.std(r, ddof=1) * np.sqrt(3))
    assert report.var == pytest.approx(-0.1)
    # Tail mass = 1.5: worst 0.2 + half of -0.1.
    assert report.cvar == pytest.approx(0.1)


def test_initial_loss_and_zero_volatility():
    report = risk_report(
        [-0.1, -0.1], periods_per_year=2, annual_risk_free_rate=0, kind="total_return"
    )
    assert report.max_drawdown == pytest.approx(-0.19)
    assert report.sharpe is None
    assert report.kind == "total_return"
    assert historical_tail_risk([0.1, 0.2], confidence=0.95) == pytest.approx((-0.1, -0.1))
    assert turnover([0, 0], [0.5, 0.5]) == 1
    assert turnover([1, 0], [0, 1]) == 2


@pytest.mark.parametrize("r", [[], [0.1], [0.1, np.nan], [-1, 0], [[0.1, 0.2]]])
def test_bad_metrics(r):
    with pytest.raises(ValidationError):
        risk_report(r, periods_per_year=252, annual_risk_free_rate=0, kind="price")
