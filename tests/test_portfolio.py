from types import SimpleNamespace

import numpy as np
import pytest

from simulacre_finance import InfeasibleError, OptimizationError, ReturnData, ValidationError
from simulacre_finance.portfolio import METHODS, optimize


def diagonal_data(scenarios, scale=1.0):
    # Exactly orthogonal demeaned columns: diagonal covariance in a 1:4 ratio.
    a = np.array([[-1, -2], [-1, 2], [1, -2], [1, 2]]) * 0.01 * scale
    return ReturnData(scenarios.dates[:4], ("A", "B"), a, scenarios.metadata)


@pytest.mark.parametrize("scale", [1.0, 1e-5, 100.0])
def test_known_gmv_and_erc(scenarios, scale):
    if scale == 100:
        # Keep simple returns above -1 while testing covariance scaling.
        scale = 10
    data = diagonal_data(scenarios, scale)
    result = optimize(data, "minimum_variance")
    np.testing.assert_allclose(result.weights, [0.8, 0.2], atol=1e-6)
    assert result.objective == pytest.approx(
        result.weights @ np.cov(data.values.T) @ result.weights
    )
    erc = optimize(data, "equal_risk_contribution")
    np.testing.assert_allclose(erc.weights, [2 / 3, 1 / 3], atol=1e-5)
    np.testing.assert_allclose(erc.risk_fractions, [0.5, 0.5], atol=1e-5)


@pytest.mark.parametrize("method", METHODS)
def test_budget_bounds_and_reproducibility(scenarios, method):
    result = optimize(scenarios, method, budget=0.8)
    assert result.weights.sum() == pytest.approx(0.8)
    assert result.weights.min() >= -1e-8
    np.testing.assert_array_equal(result.weights, optimize(scenarios, method, budget=0.8).weights)
    assert not result.weights.flags.writeable
    assert result.message and result.solver


def test_cvar_reference_two_offset_assets(scenarios):
    a = np.array([[-0.1, 0.1], [0.1, -0.1], [-0.2, 0.2], [0.2, -0.2]])
    data = ReturnData(scenarios.dates[:4], ("A", "B"), a, scenarios.metadata)
    result = optimize(data, "minimum_cvar", confidence=0.75)
    np.testing.assert_allclose(result.weights, [0.5, 0.5], atol=1e-7)
    assert result.objective == pytest.approx(0, abs=1e-8)
    # Dense grid independently checks the objective minimum.
    objectives = [np.max(-a @ [x, 1 - x]) for x in np.linspace(0, 1, 1001)]
    assert result.objective == pytest.approx(min(objectives), abs=1e-8)


def test_infeasible_and_tight_constraints(scenarios):
    with pytest.raises(InfeasibleError):
        optimize(scenarios, bounds=((0, 0.1),) * 3)
    with pytest.raises(InfeasibleError):
        optimize(scenarios, "equal_weight", bounds=((0, 0.2), (0, 1), (0, 1)))
    with pytest.raises(InfeasibleError):
        optimize(diagonal_data(scenarios), "equal_risk_contribution", bounds=((0, 0.5), (0, 1)))
    for method in ("minimum_variance", "minimum_cvar"):
        np.testing.assert_allclose(
            optimize(scenarios, method, bounds=((0.2, 0.2), (0.3, 0.3), (0.5, 0.5))).weights,
            [0.2, 0.3, 0.5],
        )


def test_solver_failure_and_singular_erc(scenarios, monkeypatch):
    monkeypatch.setattr(
        "simulacre_finance.portfolio.minimize",
        lambda *a, **kw: SimpleNamespace(success=False, message="injected"),
    )
    with pytest.raises(OptimizationError, match="injected"):
        optimize(scenarios, "minimum_variance")
    constant = ReturnData(scenarios.dates, scenarios.assets, np.zeros((100, 3)), scenarios.metadata)
    with pytest.raises(ValidationError, match="positive-definite"):
        optimize(constant, "equal_risk_contribution")


def test_lp_solver_failure_and_missing_solution(scenarios, monkeypatch):
    monkeypatch.setattr(
        "simulacre_finance.portfolio.linprog",
        lambda *a, **kw: SimpleNamespace(success=False, status=2, message="injected infeasible"),
    )
    with pytest.raises(InfeasibleError, match="injected infeasible"):
        optimize(scenarios, "minimum_cvar")


def test_erc_precision_stop_requires_verified_stationarity(scenarios, monkeypatch):
    import simulacre_finance.portfolio as portfolio

    real_minimize = portfolio.minimize

    def precision_stop(*args, **kwargs):
        result = real_minimize(*args, **kwargs)
        result.success = False
        result.message = "precision stop"
        return result

    monkeypatch.setattr(portfolio, "minimize", precision_stop)
    result = optimize(diagonal_data(scenarios), "equal_risk_contribution")
    assert "accepted after stationarity" in result.message
    np.testing.assert_allclose(result.risk_fractions, [0.5, 0.5], atol=1e-5)

    monkeypatch.setattr(
        portfolio,
        "minimize",
        lambda *a, **kw: SimpleNamespace(success=False, message="bad iterate", x=np.ones(2), nit=1),
    )
    with pytest.raises(OptimizationError, match="bad iterate"):
        optimize(diagonal_data(scenarios), "equal_risk_contribution")
    monkeypatch.setattr(
        "simulacre_finance.portfolio.linprog",
        lambda *a, **kw: SimpleNamespace(success=True, x=None, fun=None),
    )
    with pytest.raises(OptimizationError, match="without a solution"):
        optimize(scenarios, "minimum_cvar")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"budget": np.nan},
        {"budget": -1},
        {"confidence": 1},
        {"bounds": ((-1, 1),) * 3},
        {"method": "fake"},
    ],
)
def test_invalid_parameters(scenarios, kwargs):
    with pytest.raises(ValidationError):
        optimize(scenarios, **kwargs)
