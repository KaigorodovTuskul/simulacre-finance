"""Authored synthetic provider responses; no live network calls in the test suite."""

from datetime import date

import pytest

pd = pytest.importorskip("pandas")
httpx = pytest.importorskip("httpx")
pytest.importorskip("defusedxml")

from simulacre_finance import CBR, FRED, DataUnavailableError, MOEXMacro, ValidationError, WorldBank  # noqa: E402  # noqa: E402


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def soap(method, rows):
    return (
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<s:Body><{method}Response xmlns="http://web.cbr.ru/"><{method}Result>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="not_a_row" /></xs:schema>'
        '<d:diffgram xmlns:d="urn:schemas-microsoft-com:xml-diffgram-v1">'
        f'<Data xmlns="">{rows}</Data></d:diffgram>'
        f"</{method}Result></{method}Response></s:Body></s:Envelope>"
    )


def test_key_rate_realistic_soap_shape_units_dates_and_client_ownership():
    def handler(request):
        assert request.method == "POST"
        assert request.headers["SOAPAction"] == '"http://web.cbr.ru/KeyRate"'
        assert b"<fromDate>2024-01-01T00:00:00</fromDate>" in request.content
        return httpx.Response(
            200,
            text=soap(
                "KeyRate",
                (
                    "<KR><DT>2024-01-10T00:00:00+03:00</DT><Rate>16</Rate></KR>"
                    "<KR><DT>2024-01-09T00:00:00+03:00</DT><Rate>15.5</Rate></KR>"
                ),
            ),
        )

    with client(handler) as connection:
        df = CBR(client=connection).key_rate("2024-01-01", "2024-01-10")
        assert not connection.is_closed
    assert str(df.date.dtype) == "datetime64[ns]"
    assert df.date.dt.date.tolist() == [date(2024, 1, 9), date(2024, 1, 10)]
    assert df.rate.tolist() == [0.155, 0.16]
    assert df.attrs["units"] == {"rate": "decimal annual rate"}
    assert "not publication" in df.attrs["date_semantics"]


@pytest.mark.parametrize(
    "method,operation,date_key,values,kwargs",
    [
        ("ruonia", "Ruonia", "D0", {"ruo": "16", "vol": "100"}, {}),
        ("international_reserves", "mrrf7D", "D0", {"val": "600000"}, {}),
        (
            "international_reserves",
            "mrrf",
            "D0",
            {"p1": "600000", "p6": "100000"},
            {"frequency": "monthly"},
        ),
        ("bank_liquidity", "Bliquidity", "DT", {"StrLiDefNew": "-500", "StrLiDef": "-600"}, {}),
        ("liquidity_operations", "Saldo", "Dt", {"DEADLINEBS": "-500"}, {}),
        ("correspondent_accounts", "OstatDynamic", "DateOst", {"InRuss": "4500000"}, {}),
        ("bank_deposits", "OstatDepoNew", "DT", {"TOTAL": "3500000"}, {}),
    ],
)
def test_cbr_other_datasets_and_optional_components(method, operation, date_key, values, kwargs):
    row = (
        f"<row><{date_key}>2024-01-09T00:00:00+03:00</{date_key}>"
        + "".join(f"<{key}>{value}</{key}>" for key, value in values.items())
        + "</row>"
    )
    with client(lambda request: httpx.Response(200, text=soap(operation, row))) as connection:
        df = getattr(CBR(client=connection), method)("2024-01-01", "2024-01-31", **kwargs)
    assert len(df) == 1
    assert df.iloc[0, 1] == pytest.approx(
        float(next(iter(values.values()))) * (0.01 if method == "ruonia" else 1)
    )
    if method == "bank_deposits":
        assert pd.isna(df.auction_1w.iloc[0])


@pytest.mark.parametrize(
    "body",
    [
        "<html>access denied</html>",
        (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body><s:Fault /></s:Body></s:Envelope>"
        ),
        soap("KeyRate", "<KR><DT>2024-01-09</DT><Rate>NaN</Rate></KR>"),
        soap("KeyRate", "<KR><DT>2024-01-09</DT><Rate>inf</Rate></KR>"),
        soap("KeyRate", "<KR><DT>2024-01-09</DT><Other>16</Other></KR>"),
        soap("KeyRate", "<KR><Rate>16</Rate></KR>"),
        soap("KeyRate", "<KR><DT>2024-02-30</DT><Rate>16</Rate></KR>"),
        soap("KeyRate", "<KR><DT>2025-01-09</DT><Rate>16</Rate></KR>"),
        soap("KeyRate", "<KR><DT>2024-01-09</DT><Rate>16</Rate></KR>" * 2),
        '<!DOCTYPE foo [<!ENTITY secret SYSTEM "file:///not-read">]><foo>&secret;</foo>',
    ],
)
def test_cbr_malformed_blocked_duplicate_and_unsafe_responses_raise(body):
    with client(lambda request: httpx.Response(200, text=body)) as connection:
        with pytest.raises(DataUnavailableError):
            CBR(client=connection).key_rate("2024-01-01", "2024-01-31")


def test_valid_empty_interval_has_typed_columns():
    with client(lambda request: httpx.Response(200, text=soap("KeyRate", ""))) as connection:
        df = CBR(client=connection).key_rate("2024-01-06", "2024-01-07")
    assert df.empty and list(df) == ["date", "rate"]
    assert str(df.date.dtype) == "datetime64[ns]" and str(df.rate.dtype) == "float64"


def test_currency_nominal_normalization_and_input_validation():
    xml = (
        '<ValCurs ID="R01375"><Record Date="09.01.2024" Id="R01375">'
        "<Nominal>10</Nominal><Value>125,00</Value></Record></ValCurs>"
    )

    def handler(request):
        assert request.url.params["VAL_NM_RQ"] == "R01375"
        return httpx.Response(200, text=xml)

    with client(handler) as connection:
        source = CBR(client=connection)
        assert source.exchange_rates("CNY", "2024-01-01", "2024-01-31").rate.iloc[0] == 12.5
        with pytest.raises(ValidationError):
            source.exchange_rates("USD&evil=1", "2024-01-01", "2024-01-31")
    with client(lambda request: httpx.Response(200, text=xml.replace("R01375", "R01235"))) as c:
        with pytest.raises(DataUnavailableError):
            CBR(client=c).exchange_rates("CNY", "2024-01-01", "2024-01-31")


def money_rows():
    return [
        {
            "date": "2024-01-01T00:00:00",
            "indicator_id": code,
            "measure2_id": None if code == 5 else 12,
            "unit_id": 3,
            "periodicity": "month",
            "obs_val": value,
        }
        for code, value in [(5, 10), (6, 30), (7, 100), (8, 120)]
    ]


@pytest.mark.parametrize("failure", [None, "duplicate", "incomplete", "unit", "nan", "shape"])
def test_monetary_aggregates_validate_levels_and_derive_deposits(failure):
    rows = money_rows()
    if failure == "duplicate":
        rows.append(dict(rows[0]))
    elif failure == "incomplete":
        rows.pop()
    elif failure == "unit":
        rows[0]["unit_id"] = 99
    elif failure == "nan":
        rows[0]["obs_val"] = "NaN"
    payload = {"RowData": rows} if failure != "shape" else {"error": "blocked"}
    with client(lambda request: httpx.Response(200, json=payload)) as connection:
        provider = CBR(client=connection)
        if failure:
            with pytest.raises(DataUnavailableError):
                provider.monetary_aggregates("2024-01-01", "2024-01-31")
        else:
            df = provider.monetary_aggregates("2024-01-01", "2024-01-31")
            assert df.transfer_deposits.iloc[0] == 20
            assert df.other_ruble_deposits.iloc[0] == 70
            assert set(df.attrs["units"].values()) == {"RUB billion"}


def test_retry_transient_errors_only_and_do_not_close_user_client():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, text=soap("KeyRate", ""))

    with client(handler) as connection:
        CBR(client=connection, backoff=0).key_rate("2024-01-01", "2024-01-02")
        assert len(calls) == 3 and not connection.is_closed
    calls.clear()
    with client(lambda request: calls.append(request) or httpx.Response(403)) as connection:
        with pytest.raises(DataUnavailableError):
            CBR(client=connection, backoff=0).key_rate("2024-01-01", "2024-01-02")
        assert len(calls) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": 0},
        {"timeout": float("nan")},
        {"retries": -1},
        {"retries": True},
        {"backoff": -1},
    ],
)
def test_invalid_transport_configuration(kwargs):
    with pytest.raises(ValidationError):
        CBR(**kwargs)


@pytest.mark.parametrize(
    "start,end",
    [
        ("2024-02-01", "2024-01-01"),
        ("2024-01-01T00:00", "2024-02-01"),
        ("2024-02-30", "2024-03-01"),
    ],
)
def test_dates_rejected_before_network(start, end):
    with client(lambda request: pytest.fail("No network expected")) as connection:
        with pytest.raises(ValidationError):
            CBR(client=connection).key_rate(start, end)


def test_moex_pagination_decimal_rates_and_ofz_price_convention():
    calls = []

    def handler(request):
        offset = int(request.url.params["start"])
        calls.append(offset)
        rows = [["2024-01-09 00:00:00", 15]] if offset == 0 else []
        return httpx.Response(200, json={"candles": {"columns": ["begin", "close"], "data": rows}})

    with client(handler) as connection:
        source = MOEXMacro(client=connection)
        assert source.rusfar("2024-01-01", "2024-01-31").rate.iloc[0] == 0.15
        assert calls == [0, 1]
        df = source.ofz("SU26238RMFS4", "2024-01-01", "2024-01-31")
        assert df.price.iloc[0] == 0.15 and df.attrs["units"]["price"] == "fraction of par"
        assert source.rgbi("2024-01-01", "2024-01-31").value.iloc[0] == 15


@pytest.mark.parametrize("failure", ["repeat", "bound", "null", "duplicate", "date", "shape"])
def test_moex_incomplete_or_invalid_candles_never_return_partial_data(failure):
    rows = [["2024-01-09 00:00:00", 15]]
    if failure == "null":
        rows[0][1] = None
    elif failure == "date":
        rows[0][0] = "2023-01-01 00:00:00"
    elif failure == "duplicate":
        rows *= 2

    def handler(request):
        data = rows if request.url.params["start"] == "0" or failure in ("repeat", "bound") else []
        payload = {"candles": {"columns": ["begin", "close"], "data": data}}
        return httpx.Response(200, json=payload if failure != "shape" else {"message": "blocked"})

    with client(handler) as connection:
        with pytest.raises(DataUnavailableError):
            MOEXMacro(client=connection, max_pages=1 if failure == "bound" else 100).rgbi(
                "2024-01-01", "2024-01-31"
            )


def test_rusfar_curve_keeps_missing_dates_instead_of_forward_filling():
    def handler(request):
        is_on = "/RUSFAR/" in str(request.url)
        day = "2024-01-09" if is_on else "2024-01-10"
        rows = [[day + " 00:00:00", 15]] if request.url.params["start"] == "0" else []
        return httpx.Response(200, json={"candles": {"columns": ["begin", "close"], "data": rows}})

    with client(handler) as connection:
        df = MOEXMacro(client=connection).rusfar_curve("2024-01-01", "2024-01-31")
    assert len(df) == 2 and pd.isna(df.rusfar_on.iloc[1]) and pd.isna(df.rusfar_1w.iloc[0])


def test_fred_missing_observations_and_gdp_semantics():
    csv = "observation_date,NGDPNSAXDCRUQ\n2024-01-01,100\n2024-04-01,.\n"
    with client(lambda request: httpx.Response(200, text=csv)) as connection:
        df = FRED(client=connection).russia_nominal_gdp("2024-01-01", "2024-06-30")
    assert list(df) == ["date", "gdp"] and pd.isna(df.gdp.iloc[1])
    assert df.attrs["units"] == {"gdp": "RUB million"}
    assert df.attrs["seasonally_adjusted"] is False


@pytest.mark.parametrize(
    "csv",
    [
        "<html>blocked</html>",
        "DATE,WRONG_SERIES\n2024-01-01,1\n",
        "DATE,NGDPNSAXDCRUQ\n2024-01-01,1,2\n",
        "DATE,NGDPNSAXDCRUQ\n2024-01-01\n",
        "DATE,NGDPNSAXDCRUQ\n2024-01-01,inf\n",
        "DATE,NGDPNSAXDCRUQ\n2024-01-01,1\n2024-01-01,2\n",
    ],
)
def test_invalid_fred_csv_is_not_an_empty_or_partial_success(csv):
    with client(lambda request: httpx.Response(200, text=csv)) as connection:
        with pytest.raises(DataUnavailableError):
            FRED(client=connection).russia_nominal_gdp("2024-01-01", "2024-12-31")


def test_treasury_yields_are_decimal_and_preserve_zero_and_negative_values():
    ids = "DGS1MO,DGS3MO,DGS6MO,DGS1,DGS2,DGS3,DGS5,DGS7,DGS10,DGS20,DGS30"
    csv = f"DATE,{ids}\n2024-01-09,0,-0.1,5,5,5,5,5,5,5,5,.\n"
    with client(lambda request: httpx.Response(200, text=csv)) as connection:
        df = FRED(client=connection).treasury_yields("2024-01-01", "2024-01-31")
    assert df.DGS1MO.iloc[0] == 0 and df.DGS3MO.iloc[0] == -0.001
    assert df.DGS10.iloc[0] == 0.05 and pd.isna(df.DGS30.iloc[0])


def test_fred_can_return_full_history_despite_requested_date_bounds():
    csv = "DATE,NGDPNSAXDCRUQ\n1990-01-01,1\n2024-01-01,100\n2025-01-01,200\n"
    with client(lambda request: httpx.Response(200, text=csv)) as connection:
        df = FRED(client=connection).russia_nominal_gdp("2024-01-01", "2024-12-31")
    assert len(df) == 1 and df.gdp.iloc[0] == 100


def test_monetary_year_request_includes_january_and_filters_extra_years():
    rows = money_rows()
    rows.extend([{**row, "date": "2023-12-01T00:00:00"} for row in money_rows()])

    def handler(request):
        assert request.url.params["y1"] == "2023"
        assert request.url.params["y2"] == "2024"
        assert request.url.params.get_list("i_ids") == ["5", "6", "7", "8"]
        return httpx.Response(200, json={"RowData": rows})

    with client(handler) as connection:
        df = CBR(client=connection).monetary_aggregates("2024-01-01", "2024-01-31")
    assert len(df) == 1 and df.date.iloc[0].date() == date(2024, 1, 1)


def test_unsafe_utf16_xml_is_rejected_too():
    xml = '<!DOCTYPE foo [<!ENTITY secret SYSTEM "file:///not-read">]><foo>&secret;</foo>'
    with client(lambda request: httpx.Response(200, content=xml.encode("utf-16"))) as connection:
        with pytest.raises(DataUnavailableError, match="unsafe"):
            CBR(client=connection).key_rate("2024-01-01", "2024-01-31")


@pytest.mark.parametrize("failure", [None, "country", "pages", "missing", "date"])
def test_world_bank_checks_identity_completeness_and_keeps_nulls(failure):
    items = [
        {
            "countryiso3code": "RUS",
            "indicator": {"id": "NY.GDP.MKTP.CN"},
            "date": "2024",
            "value": None,
        }
    ]
    meta = {"pages": 1, "total": 1}
    if failure == "country":
        items[0]["countryiso3code"] = "USA"
    elif failure == "pages":
        meta["pages"] = 2
    elif failure == "missing":
        meta["total"] = 2
    elif failure == "date":
        items[0]["date"] = "2025"
    with client(lambda request: httpx.Response(200, json=[meta, items])) as connection:
        if failure:
            with pytest.raises(DataUnavailableError):
                WorldBank(client=connection).nominal_gdp(2020, 2024)
        else:
            df = WorldBank(client=connection).nominal_gdp(2020, 2024)
            assert pd.isna(df.gdp.iloc[0]) and df.attrs["frequency"] == "annual"
