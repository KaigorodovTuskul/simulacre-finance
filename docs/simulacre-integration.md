# Integrating the same pure Python core

## Validated integration in the Simulacre AI host application

Host paths below refer to the separate `KaigorodovTuskul/moex_ai_mcp` application,
not this library repository. The local integration was validated during the initial
implementation; its deployment lifecycle is separate from library releases.

`src/portfolio/cash.py:accrual_factor` delegates its actual ACT/365F calculation
to `simulacre_finance.rates.simple_accrual_factor`. The existing public signature
accepts percentage rates and a financing multiplier; its boundary converts them
to a decimal rate. Calendar-gap and zero-gap behavior remain in the host wrapper.
The engine, instrument engine and futures overlay already call this wrapper, so
all three use the same installed library. Existing cash/engine regression tests
verify the weekend accrual path and portfolio accounting.

The host pyproject declares a local path source in `tool.uv.sources`; `uv sync
--frozen` installs the distribution. Dockerfile.api copies the package before uv
sync, including the API, publisher and Hermes dependency stages. The independent
wheel has no dependency on this repository and no absolute filesystem references.
The host's nonlinear allocation policy, UI and older backtest metrics are unchanged.
This integration is a small verified computation boundary, not a migration of
Portfolio Lab's entire engine to the new backtester.

## Canonical schema at the data boundary

`PriceData(dates, assets, values, metadata)` is a positive float64 matrix: T rows,
N named columns; dates are unique, increasing `datetime.date` (ISO YYYY-MM-DD
strings are also validated at runtime). `ReturnData` has the same shape with
decimal simple interval returns > -1, dated at interval END. `prices.returns()`
is the explicit conversion; its first row uses the first two price observations.

`Metadata(currency='RUB', periods_per_year=252, source='...', as_of=date(...),
kind='price', adjustment='unadjusted', frequency='daily')` applies to ALL columns.
Cross-currency mixing requires upstream conversion. Set kind='total_return' only
when the supplied index/returns already include distributions. An observation
vintage is not the release timestamp of a historical point-in-time dataset.
ReturnData.window preserves the original vintage and never claims to remove
survivorship bias or future corporate-action revisions.

The existing `src.portfolio.engine.run_backtest` accepts
`series: dict[sleeve, dict[ISO_date, index_level]]`, e.g. stocks/OFZ/corporate.
The tested [mapping example](../examples/simulacre_mapping.py) maps exactly that
shape to the canonical matrix and rejects misaligned date sets. It does not inherit
the host engine's implicit carrying of observations. Populate Metadata from the
upstream response's source/as_of/currency/kind, and verify them before combining
series. Preserve point-in-time index membership upstream.

Raw ISS JSON is `{history: {columns: [...], data: [[...]]}}`; `MoexISS` validates
and maps each page of that schema. The actual `tools/get_trading_history.py`
delegates to `src/moex_api/client.py:MOEXClient.get_trading_history`, which returns
`{success: true, security, engine, market, session, from_date, till_date, limit,
history: [{BOARDID, SECID, TRADEDATE, CLOSE, ...}, ...]}`. That MCP envelope does
NOT include currency, source vintage or adjustment metadata. Require those from
the caller's verified context, rather than reading fields that do not exist.
The tested [actual MCP mapping](../examples/mcp_history_mapping.py) filters one
explicit board, sorts observation dates, validates identifier/date/close and maps
the normalized list to PriceData. It never assumes the bounded tool response is
the complete history; fetch/validate the requested window upstream. Unknown
currency or return kind must be resolved before constructing Metadata.

Map TRADEDATE to dates, SECID to the asset column and CLOSE to values with explicit
unadjusted provenance. Candle `begin` timestamps must first
be filtered to completed daily candles and converted using the exchange timezone;
do not silently truncate intraday timestamps into duplicate dates.

## Backend, Portfolio Lab and thin MCP tools

Backend/Portfolio Lab calls `optimize(data, method, bounds=..., budget=...)` for
historical estimates, `walk_forward(data, ...)` for realized research results,
and `bond_analytics(FixedCashflows(...), settlement, nominal_yield, ...)` for
explicit fixed-flow valuation. CPU solvers should run off an async event loop.
Keep provider access, authentication, quotas, data caching and UI formatting in
the host. Never send credentials or private source payloads into the public package.

An existing authenticated FastMCP server can register the tested `optimize_sleeves`
function in the example with `server.tool()(optimize_sleeves)`, after its own input
schema/authorization and Metadata mapping. Convert arrays with `.tolist()`, dates
with `.isoformat()`, dataclasses with `dataclasses.asdict`, and undefined Sharpe
as JSON null. Expose method, solver, objective units, training window, currency,
kind and provenance in responses; do not just return an unexplained weight vector.
Map ValidationError to invalid-input responses and OptimizationError to explicit
failed-analysis results; do not replace errors with fabricated allocations.

Public interface inspected: https://simulacre-ai.ru/site/mcp/ describes schema
discovery (`search_tools`, `describe_dataset`) and authenticated OAuth/personal-key
access at https://simulacre-ai.ru/mcp. No credential was supplied or needed for
this work. No authenticated provider is advertised or implemented: existing hosts
fetch authorized responses, map them, then call this offline library.

