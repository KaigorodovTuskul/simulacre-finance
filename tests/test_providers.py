import copy
import json
from datetime import date
from pathlib import Path

import pytest

from simulacre_finance import DataUnavailableError
from simulacre_finance.providers import MoexISS

PAGE = json.loads((Path(__file__).parent / "fixtures/iss_history.json").read_text())


def test_paginated_fixture_enters_same_pipeline():
    calls = []

    def transport(url, params, timeout):
        calls.append((url, params["start"], timeout))
        if params["start"] == 0:
            return PAGE
        out = copy.deepcopy(PAGE)
        out["history"]["data"] = [["TQBR", "2024-01-05", "DEMO", 103]]
        out["history.cursor"]["data"] = [[2, 3, 2]]
        return out

    prices = MoexISS(transport=transport).history(
        "DEMO", "2024-01-01", "2024-01-05", currency="RUB"
    )
    assert len(calls) == 2
    assert [x[1] for x in calls] == [0, 2]
    assert prices.dates[-1] == date(2024, 1, 5)
    assert prices.returns().values[0, 0] == pytest.approx(0.02)
    assert "unadjusted" == prices.metadata.adjustment


def test_retries_timeout_then_success():
    calls = []

    def transport(*args):
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("synthetic timeout")
        return {"securities": {"columns": ["secid", "shortname", "isin"], "data": []}}

    assert MoexISS(transport=transport, backoff=0).lookup("DEMO") == ()
    assert len(calls) == 3


def test_bounds_and_repeated_pages_never_truncate():
    with pytest.raises(DataUnavailableError, match="bound"):
        MoexISS(transport=lambda *args: PAGE, max_pages=1).history(
            "DEMO", "2024-01-01", "2024-01-05", currency="RUB"
        )
    with pytest.raises(DataUnavailableError, match="repeated"):
        MoexISS(transport=lambda *args: PAGE).history(
            "DEMO", "2024-01-01", "2024-01-05", currency="RUB"
        )


@pytest.mark.parametrize("failure", ["null", "duplicate", "wrong_board", "cursor", "malformed"])
def test_provider_validation(failure):
    payload = copy.deepcopy(PAGE)
    payload["history.cursor"]["data"] = [[0, 2, 2]]
    if failure == "null":
        payload["history"]["data"][0][-1] = None
    elif failure == "duplicate":
        payload["history"]["data"][1][1] = "2024-01-01"
    elif failure == "wrong_board":
        payload["history"]["data"][0][0] = "BAD"
    elif failure == "cursor":
        payload["history.cursor"]["data"] = [[1, 2, 2]]
    else:
        payload["history"]["columns"] = ["X"]
    provider = MoexISS(transport=lambda *args: payload)
    with pytest.raises(DataUnavailableError):
        provider.history("DEMO", "2024-01-01", "2024-01-05", currency="RUB")
    if failure == "null":
        assert (
            len(
                provider.history(
                    "DEMO", "2024-01-01", "2024-01-05", currency="RUB", missing="drop"
                ).dates
            )
            == 1
        )
