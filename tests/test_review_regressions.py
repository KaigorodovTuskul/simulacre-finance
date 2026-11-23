"""Independent review reproductions, not merely snapshots of implementation output."""

import copy
import importlib.util
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from simulacre_finance import (
    CashFlow,
    DataUnavailableError,
    FixedCashflows,
    Metadata,
    MoexISS,
    OptimizationError,
    PriceData,
    ReturnData,
    ValidationError,
    bond_analytics,
    historical_tail_risk,
    optimize,
    risk_report,
)

META = Metadata("RUB", 252, "authored review fixture", date(2024, 1, 10))
DAYS = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(4))


@pytest.mark.parametrize("budget", [1, 1e-6, 1e-9, 1e-12])
@pytest.mark.parametrize("scale", [1, 1e-9])
def test_optimizer_scale_invariance(budget, scale):
    diagonal = np.array([[-0.01, -0.02], [-0.01, 0.02], [0.01, -0.02], [0.01, 0.02]]) * scale
    data = ReturnData(DAYS, ("A", "B"), diagonal, META)
    result = optimize(data, "minimum_variance", budget=budget)
    np.testing.assert_allclose(result.weights / budget, [0.8, 0.2], atol=1e-6)
    np.testing.assert_allclose(
        optimize(data, "equal_risk_contribution", budget=budget).weights / budget,
        [2 / 3, 1 / 3],
        atol=1e-5,
    )
    opposite = np.array([[-0.1, 0.1], [0.1, -0.1], [-0.2, 0.2], [0.2, -0.2]]) * scale
    data = ReturnData(DAYS, ("A", "B"), opposite, META)
    result = optimize(data, "minimum_cvar", budget=budget, confidence=0.75)
    np.testing.assert_allclose(result.weights / budget, [0.5, 0.5], atol=1e-7)


@pytest.mark.parametrize("confidence", [1e-20, 1e-17, 0.5, 1 - 1e-15])
def test_tail_boundaries(confidence):
    var, cvar = historical_tail_risk([-0.1, 0.2], confidence=confidence)
    assert np.isfinite([var, cvar]).all()
    if confidence < 1e-16:
        assert cvar == pytest.approx(-0.05)
    if confidence > 0.99:
        assert cvar == pytest.approx(0.1)


def test_numeric_extremes_are_finite_or_explicit_errors():
    result = risk_report([1e160, -0.99], periods_per_year=1, annual_risk_free_rate=0, kind="price")
    assert np.isfinite(result.volatility)
    assert result.sharpe != 0
    data = ReturnData(DAYS[:2], ("A", "B"), np.array([[1e160, 1e159], [0, 0.1]]), META)
    with pytest.raises(OptimizationError, match="numeric limits"):
        optimize(data, "equal_weight")
    bond = FixedCashflows("SYNTH", "RUB", (CashFlow(date(2024, 1, 2), 100),))
    priced = bond_analytics(bond, DAYS[0], 1e308)
    assert np.isfinite([priced.dirty_price, priced.convexity]).all()


def test_reject_complex_and_overflow_and_metadata_types():
    for values in (np.array([[1 + 2j], [2 + 3j]]), [[10**1000], [1]]):
        with pytest.raises(ValidationError):
            PriceData(DAYS[:2], ("A",), values, META)
    with pytest.raises(ValidationError):
        Metadata(None, 252, "synthetic", DAYS[-1])


@pytest.mark.parametrize("failure", ["empty", "short", "changed_total", "lost_cursor"])
def test_incomplete_cursor_history_rejected(failure):
    calls = []

    def transport(url, params, timeout):
        start = params["start"]
        calls.append(start)
        rows = [["TQBR", "2024-01-01", "DEMO", 100], ["TQBR", "2024-01-02", "DEMO", 101]]
        if start:
            rows = (
                []
                if failure == "empty"
                else [["TQBR", "2024-01-03", "DEMO", 102], ["TQBR", "2024-01-04", "DEMO", 103]]
            )
        if failure == "short" and not start:
            rows = rows[:1]
        payload = {
            "history": {"columns": ["BOARDID", "TRADEDATE", "SECID", "CLOSE"], "data": rows},
            "history.cursor": {
                "columns": ["INDEX", "TOTAL", "PAGESIZE"],
                "data": [[start, 5 if start and failure == "changed_total" else 4, 2]],
            },
        }
        if start and failure == "lost_cursor":
            del payload["history.cursor"]
        return payload

    with pytest.raises(DataUnavailableError):
        MoexISS(transport=transport).history("DEMO", "2024-01-01", "2024-01-04", currency="RUB")


def test_provider_contract_validation_precedes_network():
    def no_call(*args):
        raise AssertionError("Invalid currency must fail before any request")

    with pytest.raises(ValidationError):
        MoexISS(transport=no_call).history("A", DAYS[0], DAYS[-1], currency=None)
    payload = {"securities": {"columns": ["secid", "shortname", "isin"], "data": [["A", "A", 123]]}}

    def search(url, params, timeout):
        if params["start"]:
            result = copy.deepcopy(payload)
            result["securities"]["data"] = []
            return result
        return payload

    with pytest.raises(DataUnavailableError, match="ISIN"):
        MoexISS(transport=search).lookup("A")


def test_light_cash_import():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from simulacre_finance.rates import "
            "simple_accrual_factor; assert 'numpy' not in sys.modules; "
            "assert 'scipy' not in sys.modules",
        ],
        check=True,
    )


def test_real_mcp_normalized_envelope_mapping():
    path = Path(__file__).parents[1] / "examples/mcp_history_mapping.py"
    spec = importlib.util.spec_from_file_location("mcp_mapping", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    envelope = {
        "success": True,
        "engine": "stock",
        "market": "shares",
        "security": "DEMO",
        "session": "3",
        "limit": 100,
        "history": [
            {"BOARDID": "TQBR", "SECID": "DEMO", "TRADEDATE": "2024-01-02", "CLOSE": 105},
            {"BOARDID": "TQBR", "SECID": "DEMO", "TRADEDATE": "2024-01-01", "CLOSE": 100},
        ],
    }
    prices = module.history_prices(envelope, board="TQBR", metadata=META)
    assert prices.returns().values[0, 0] == pytest.approx(0.05)
    assert prices.metadata is META  # explicit caller-supplied provenance
    broken = copy.deepcopy(envelope)
    broken["history"][0]["CLOSE"] = None
    with pytest.raises(ValidationError):
        module.history_prices(broken, board="TQBR", metadata=META)
