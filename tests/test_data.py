from datetime import date

import numpy as np
import pytest

from simulacre_finance import Metadata, PriceData, ReturnData, ValidationError, load_csv
from simulacre_finance.data import iso_date

META = Metadata("RUB", 252, "synthetic", date(2024, 2, 1))


def test_csv_returns_and_input_copy(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("date,A,B\n2024-01-01,100,200\n2024-01-04,110,180\n", encoding="utf-8")
    prices = load_csv(path, metadata=META)
    np.testing.assert_allclose(prices.returns().values, [[0.1, -0.1]])
    assert prices.returns().metadata.kind == "price"
    assert not prices.values.flags.writeable
    values = np.ones((2, 1))
    data = PriceData(prices.dates, ("X",), values, META)
    values[:] = 999
    assert data.values[0, 0] == 1


@pytest.mark.parametrize(
    "dates,assets,values",
    [
        (("2024-01-01", "2024-01-01"), ("A",), [[1], [2]]),
        (("2024-01-02", "2024-01-01"), ("A",), [[1], [2]]),
        (("2024-01-01",), ("A", "A"), [[1, 2]]),
        (("2024-01-01",), ("A",), [[np.nan]]),
        (("2024-01-01",), ("A",), [[0]]),
        (("2024-01-01",), ("A",), [[-2]]),
        ((), ("A",), []),
        (("2024-03-01",), ("A",), [[1]]),
    ],
)
def test_bad_prices(dates, assets, values):
    with pytest.raises(ValidationError):
        PriceData(dates, assets, values, META)


@pytest.mark.parametrize("value", ["20240101", "2024-1-1", "2024-01-01T10:00:00", "2024-02-31"])
def test_strict_date(value):
    with pytest.raises(ValidationError):
        iso_date(value)


@pytest.mark.parametrize(
    "text",
    ["date,A\n2024-01-01,\n", "date,A,B\n2024-01-01,1\n", "date,A\n2024-01-01,1,2\n", "date,A\n"],
)
def test_bad_csv(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_csv(path, metadata=META)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"periods_per_year": 0},
        {"periods_per_year": 2.5},
        {"source": ""},
        {"kind": "adjusted_maybe"},
        {"as_of": "2024-01-01T00:00:00"},
    ],
)
def test_metadata_validation(kwargs):
    fields = {
        "currency": "RUB",
        "periods_per_year": 252,
        "source": "synthetic",
        "as_of": date(2024, 1, 1),
    }
    with pytest.raises(ValidationError):
        Metadata(**{**fields, **kwargs})


@pytest.mark.parametrize("value", [-1, -2, np.inf, np.nan])
def test_return_data_rejects_bankruptcy_or_nonfinite(value):
    with pytest.raises(ValidationError):
        ReturnData((date(2024, 1, 1),), ("A",), [[value]], META)
