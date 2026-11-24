# Public macro data API (0.2.0)

These are synchronous, direct-to-provider loaders returning `pandas.DataFrame`.
They are independent of Simulacre AI's private API, database, credentials, proxy
servers and update scheduler. Available from version 0.2.0.

## Install and use

From PyPI:

```sh
pip install "simulacre-finance[macro]"
uv add "simulacre-finance[macro]"
```

Core dependencies remain NumPy and SciPy. `[macro]` adds HTTPX, pandas and
defusedxml (safe XML parsing). It adds no Chromium/Playwright, PDF extraction,
Excel reader, SOAP framework, Cbonds SDK, database or web server.

For a local checkout use `pip install -e ".[macro]"` from the repository, or
`uv add G:/production/simulacre-finance --extra macro` from another uv project.

```python
from simulacre_finance import CBR, FRED, MOEXMacro, WorldBank

cbr = CBR(timeout=20, retries=2, backoff=0.5)
df = cbr.key_rate(start="2024-01-01", end="2024-12-31")
print(df.tail())
print(df.attrs)

ruonia = cbr.ruonia("2024-01-01", "2024-12-31")
fx = cbr.exchange_rates("CNY", "2024-01-01", "2024-12-31")
money = cbr.monetary_aggregates("2024-01-01", "2024-12-31")
ofz = MOEXMacro().ofz("SU26238RMFS4", "2024-01-01", "2024-12-31")
gdp_quarterly = FRED().russia_nominal_gdp("2020-01-01", "2024-12-31")
gdp_annual = WorldBank().nominal_gdp(2020, 2024, country="RUS")
```

`start` and `end` are inclusive ISO `YYYY-MM-DD` strings or Python `date` values.
Timestamps and reversed intervals raise `ValidationError` before any request.
World Bank uses inclusive integer years, 1960 and later.

## Return contract

- One `date` column (`datetime64[ns]`, timezone-naive, ascending, unique) and named
  numeric columns (`float64`). This is the provider's local observation date.
- Dates do **not** imply publication or availability on that date. GDP dates are
  period labels, not release timestamps. These latest-vintage datasets are not
  suitable for an unbiased historical macro strategy without release/vintage data.
- No implicit resampling, weekend filling, interpolation or cross-source alignment.
- A structurally valid empty interval returns an empty DataFrame with typed columns.
  Source-declared missing components and FRED/World Bank nulls stay `NaN`.
  A malformed response, unknown schema, duplicate date, missing monetary total or
  incomplete ISS pagination raises `DataUnavailableError`.
- Rates are **decimal annual rates**: `0.16` means 16%. Shares are not prices.
  Index levels and money amounts keep their explicit units; no automatic FX conversion.
- `df.attrs`: `source`, `units` (column-to-unit mapping), `frequency`, UTC
  `retrieved_at`, `date_semantics`, `vintage`. These attrs may be lost in external
  serialization or pandas transformations; retain them separately when needed.

## CBR

All methods below take `(start, end)` unless noted. Documentation and XSDs:
[CBR daily web service](https://www.cbr.ru/development/DWS/),
[currency XML service](https://www.cbr.ru/development/SXML/).

| Method | Numeric columns | Units / meaning |
| --- | --- | --- |
| `key_rate` | `rate` | Decimal annual rate; published daily observations, not a decision calendar |
| `ruonia` | `rate`, `volume` | Decimal annual rate; transaction volume in RUB billion |
| `international_reserves(..., frequency="weekly")` | `reserves` | USD million |
| `international_reserves(..., frequency="monthly")` | `reserves`, `fx_reserves`, `foreign_exchange`, `sdr`, `imf_position`, `gold` | USD million; components within FX reserves are nested, do not add all columns |
| `bank_liquidity` | `liquidity_balance`, `liquidity_balance_excl_corr`, `claims`, `liabilities`, `correspondent_accounts`, `required_reserves`, `net_cbr_claims` | RUB billion; source signs, no signal classification |
| `liquidity_operations` | `balance` | RUB billion; CBR provision/absorption balance (`Saldo`) |
| `correspondent_accounts` | `russia`, `moscow` | RUB million; Moscow is a subset, not an additional total |
| `bank_deposits` | `total`, `auction_1w`, `fine_tuning`, `standing_facilities` | RUB million; absent components are unknown, not zero |
| `exchange_rates(currency, start, end)` | `rate` | RUB per **one** foreign currency unit, normalized from CBR's nominal |
| `monetary_aggregates` | `m0`, `m1`, `m2`, `m2x`, `transfer_deposits`, `other_ruble_deposits` | RUB billion; monthly balances |

`exchange_rates` accepts `USD`, `EUR`, `CNY`, or an explicit CBR identifier such as
`R01235`. It returns official rates, not exchange quotes, and does not synthesize
weekends. CBR may change identifiers/nominals historically: choose the appropriate
identifier for the period. There is no automatic stitching across currency reforms.

`monetary_aggregates` uses the public JSON endpoint behind
[CBR monetary aggregates](https://www.cbr.ru/statistics/macro_itm/dkfs/monetary_agg/),
category 5, indicators 5/6/7/8, unit 3 (RUB billion). M0 has a null measure ID;
other totals use measure 12. API years refer to reporting periods, so one preceding
year is requested to include January balances; exact dates are filtered locally.
`transfer_deposits = M1 - M0`, `other_ruble_deposits = M2 - M1`.
M2X−M2 is **not** reported as FX deposits: certificates and other definitional
differences must be handled separately. No estimates or XLSX fallback are bundled.

SOAP is sent directly over HTTPS; a full SOAP framework is unnecessary. Request
parameter `fromDate` is case-sensitive (the web documentation uses inconsistent
capitalization; the WSDL and live service specify lowercase `fromDate`). Embedded
XSD elements are ignored; only current diffgram rows become observations. XML
entities/DTDs are rejected by defusedxml.

## MOEXMacro

Uses [MOEX ISS](https://iss.moex.com/iss/reference/) and the library's existing
bounded paginator; `max_pages=100` by default. A repeated page, changed/missing
cursor, invalid close, duplicate date or page bound raises instead of truncating.
The request uses daily candles (`interval=24`) and continues until the final page.

| Method | Numeric columns | Meaning |
| --- | --- | --- |
| `imoex(start, end)` | `value` | IMOEX price index, index points |
| `rgbi(start, end)` | `value` | RGBI price index, index points |
| `index(security, start, end)` | `value` | Other SNDX indices; e.g. `RGBITR` for total return |
| `rusfar(start, end, tenor="ON")` | `rate` | Decimal annual rate, MMIX board; ON/1W/2W/1M/3M |
| `rusfar_curve(start, end)` | `rusfar_on`, `rusfar_1w`, `rusfar_2w`, `rusfar_1m`, `rusfar_3m` | Five dated term rates, outer join, no filling |
| `ofz(security, start, end)` | `price` | TQOB clean price, fraction of par: `0.8` means 80% of par |

An OFZ quote is not a yield, currency amount or total-return series. Coupons,
accrued interest, amortization and bond schedules are not inferred. RUSFAR is a
rate, not an asset price to pass directly to a return calculation. Historical
access and availability remain subject to MOEX rules; no redistribution rights
are granted by the library.

## FRED and World Bank

- `FRED().treasury_yields(start, end)`: eleven constant-maturity US Treasury series
  `DGS1MO,DGS3MO,DGS6MO,DGS1,DGS2,DGS3,DGS5,DGS7,DGS10,DGS20,DGS30`, in decimal annual
  rates, one column per series. Holidays/missing quotes remain `NaN`. Zero and
  negative yields are valid. [FRED example series](https://fred.stlouisfed.org/series/DGS10).
- `FRED().russia_nominal_gdp(start, end)`: `gdp` in RUB million, quarterly,
  not seasonally adjusted, period-start labels. This is nominal GDP, not the
  application's separate real GDP growth release indicator. The series can lag
  official releases or stop updating. [Series metadata](https://fred.stlouisfed.org/series/NGDPNSAXDCRUQ).
- `WorldBank().nominal_gdp(start_year, end_year, country="RUS")`: `gdp` in current
  local currency, annual, year-start labels. Missing published years stay `NaN`;
  no built-in anchors or cross-provider substitution. The default RUS currency is
  RUB. [Indicator](https://data.worldbank.org/indicator/NY.GDP.MKTP.CN),
  [API documentation](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures).

FRED's public CSV export requires no API key and can ignore graph date bounds;
the requested interval is filtered locally. World Bank is requested with a
single-country page large enough for the entire supported interval; its advertised
page count/total and each row's country/indicator are checked for completeness.

## Networks, errors and storage

```python
import httpx
import ssl
from simulacre_finance import CBR, DataUnavailableError

# Default transport verifies TLS against the system trust store.
# For additional trusted roots, use your own CA bundle; do not disable verification.
context = ssl.create_default_context(cafile="/path/to/approved-ca-bundle.pem")
with httpx.Client(verify=context) as client:
    try:
        rates = CBR(client=client).key_rate("2024-01-01", "2024-12-31")
        rates.to_csv("key_rate.csv", index=False)
    except DataUnavailableError as error:
        print(error)
```

Supplied HTTPX clients can also configure a user-managed proxy and remain open
after calls. No provider IP, credentials, private CA bundle or Simulacre SSH tunnel
is embedded in this package. Default transport has a per-request timeout (20s),
up to two retries on transport failures/408/429/selected 5xx, exponential backoff,
and no retries for parsing errors or 403. Retry count is bounded to 0..10.
Long paginated requests can take longer than one timeout; there is no total-job SLA.

Every method loads on demand. There is no automatic polling, persistent cache or
silent stale fallback. Cache/store results in the calling application; CBR
[recommends intermediate storage and fewer requests](https://www.cbr.ru/development/).
Do not treat a successful request as evidence the series is fresh: inspect its
last observation date and the provider's expected publication schedule.

## Coverage and validation

[Coverage ledger](macro-coverage.md) records the current application's indicators
individually, including partial mappings and explicit exclusions. Source-specific
business scores, LLM summaries and graphical cards are not data loaders.

Offline tests use authored synthetic XML/CSV/JSON and cover malformed/blocked
responses, unsafe XML, units/FX nominal conversion, missing observations, duplicate
dates, transport retries and complete pagination. The core-only suite works with
the optional dependencies absent. Live checks are recorded separately in the
coverage ledger and are not part of ordinary `pytest` or wheel installation.
