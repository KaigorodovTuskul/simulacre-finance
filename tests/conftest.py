"""Authored synthetic scenarios; forbid accidental external network in default tests."""

import socket
from datetime import date, timedelta

import numpy as np
import pytest

from simulacre_finance import Metadata, ReturnData


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("External networking is forbidden in the default suite")

    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.fixture
def scenarios():
    rng = np.random.default_rng(19)
    values = rng.normal([0.001, 0.0005, 0.0002], [0.02, 0.01, 0.005], (100, 3))
    days = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(100))
    return ReturnData(
        days, ("A", "B", "C"), values, Metadata("RUB", 252, "authored synthetic", days[-1])
    )
