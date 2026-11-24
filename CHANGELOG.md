# Changelog

## 0.2.0 — 2026-11-24

- Optional `[macro]` extra: public CBR XML/JSON, MOEX ISS daily macro candles,
  FRED CSV and World Bank GDP loaders returning pandas DataFrames.
- Typed sorted dates, explicit units/provenance, bounded retries/pagination,
  safe XML parsing and injectable HTTPX clients. Core dependencies are unchanged.
- No Cbonds, browser automation, PDF/Excel parsers or private service dependency.
- See [macro data guide](docs/macro.md) for available datasets and exclusions.

## 0.1.0 — 2026-11-23

First public release of Simulacre Finance, extracted into an independent MIT
Python package from the Simulacre AI implementation effort.

- Validated dated price/return matrices, explicit currency/frequency/provenance,
  offline CSV and optional public MOEX ISS lookup/share-history transport.
- Equal weight, global minimum variance, exact equal risk contribution and minimum
  historical CVaR, with bounds, budget, diagnostics and numerical-scale validation.
- Realized risk/performance, historical VaR/CVaR, drawdown, Sharpe and gross turnover.
- Explicit dated fixed cash flows, regular fixed-rate bullet schedules, PV/YTM,
  Macaulay/modified duration, convexity and explicit clean/dirty price handling.
- Deterministic rolling walk-forward portfolios with delayed close execution,
  drifting holdings, cash, self-financing costs and rebalance audit logs.
- Reproducible offline examples, tested Simulacre/MCP schema mappings, typed exports
  and an offline suite of 114 numerical/validation tests.

Known scope limits and financial assumptions are documented in the README and
methodology. No exchange data, credentials, live trading or authenticated MCP
client are bundled.
