import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from simulacre_finance import Metadata, ValidationError, simple_accrual_factor

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_actual_sleeve_contract_mapping():
    spec = importlib.util.spec_from_file_location("mapping", EXAMPLES / "simulacre_mapping.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    series = {
        "stocks": {"2024-01-01": 100, "2024-01-02": 105, "2024-01-03": 98},
        "ofz": {"2024-01-01": 100, "2024-01-02": 101, "2024-01-03": 101.5},
    }
    meta = Metadata("RUB", 252, "synthetic sleeve fixture", date(2024, 1, 3), kind="total_return")
    weights = module.optimize_sleeves(series, metadata=meta)
    assert sum(weights.values()) == pytest.approx(1)
    assert weights["ofz"] > 0.9
    del series["ofz"]["2024-01-02"]
    with pytest.raises(ValidationError):
        module.sleeve_prices(series, metadata=meta)


@pytest.mark.parametrize("name", ["portfolio", "bond"])
def test_examples_reproducible_from_outside_repo(name, tmp_path):
    def run():
        return subprocess.run(
            [sys.executable, str(EXAMPLES / f"{name}.py")],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    first, second = run(), run()
    assert first == second
    assert json.loads(first)


def test_cash_primitive():
    assert simple_accrual_factor(0.1, 3) == pytest.approx(1 + 0.1 * 3 / 365)
    assert simple_accrual_factor(0.1, 360, basis=360) == pytest.approx(1.1)
    with pytest.raises(ValidationError):
        simple_accrual_factor(float("nan"), 2)
