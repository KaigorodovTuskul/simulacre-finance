# Macro coverage ledger — 0.2.0

Inspected 2026-11-24 against the application's actual `_MACRO_INDICATORS` in
`src/web/macro_service.py` and source implementations, not its older generated
catalog. Hidden forecast definitions are included; duplicate registry codes are
listed once. This is a scope snapshot, not a runtime dependency on that project.

**Available** means a numeric data loader, not the website's chart, explanatory
text, forecast, classification or export interface. **Partial** means the source
levels are available but part of that application's calculation is intentionally
not ported. Deferred items are not necessarily technically impossible or heavy;
they need separate implementation/validation beyond this initial structured-data pass.

No Cbonds-backed source or composite is implemented. No Playwright/Chromium,
PDF/Excel extractor, database, provider credentials or application proxy is bundled.

Additional loaders not represented as standalone application indicators:
`MOEXMacro.imoex`, SNDX `index("RGBITR", ...)`, official CBR USD/EUR/CNY/R-code
exchange rates, CBR correspondent accounts/deposit balances/liquidity-operation
balance, monthly reserve components, and eleven FRED US Treasury yield tenors.

## Application indicator mapping

| Application code | Status | Mapping or reason |
| --- | --- | --- |
| `russia_key_rate_forecast` | Excluded | Depends on Cbonds and application-specific forecasting/interpretation. |
| `russia_usdrub_forecast` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_carry_trade_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_fund_flows_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_capital_flows_by_participant` | Deferred | Application-specific aggregation/context discovery; not a single independently validated public numeric series. |
| `russia_macro_expert_views` | Deferred | Application-specific aggregation/context discovery; not a single independently validated public numeric series. |
| `global_market_heatmap` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `imoex_market_breadth` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_nominal_gdp` | Partial | `FRED.russia_nominal_gdp` and `WorldBank.nominal_gdp` supply nominal levels; no fallback mixing, TTM, growth or manual anchors. |
| `russia_buffett_indicator` | Deferred | Composite needs dated capitalization and GDP/M2 availability alignment; existing back-scaled IMOEX capitalization is an approximation, not copied as actual history. |
| `russia_tax_period_fx_pressure` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `moex_futoi_positions_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_rgbi_ofz_constituents` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_ofz_yield_curve_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_m2_inflation_pressure` | Partial | `CBR.monetary_aggregates` supplies M0/M1/M2/M2X levels; growth rates and pressure scores are not ported. |
| `russia_fx_share_broad_money` | Partial | M2X levels available; FX deposit components/share and FX-adjusted attribution deferred. M2X minus M2 is not used as an FX proxy. |
| `russia_m2_cpi_spread_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_ruble_deposit_structure` | Partial | `CBR.monetary_aggregates` supplies transfer/other ruble deposit levels; no score or ready-made shares. |
| `russia_minfin_fx_pressure_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_minfin_fx_actual_flow` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `russia_minfin_fx_regular_flow_est` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `russia_minfin_fnb_adjustment_est` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `russia_ruble_liquidity` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `russia_bank_liquidity_balance` | Available | `CBR.bank_liquidity`; structural balance and selected components. |
| `russia_cbr_repo_auctions` | Deferred | Source-specific auction schedules and offer/result tables require separate validation; deposit balances are not auction results. |
| `russia_minfin_ofz_auctions` | Deferred | Multi-page publication/document parsing with Telegram/history fallbacks; intentionally deferred rather than importing application infrastructure. |
| `russia_budget_rule_oil_gap` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `russia_usdrub_cross_monitor` | Deferred | Coupled Minfin publication discovery, source fallbacks, historical state and estimates; needs independent parser/units validation. |
| `global_dxy` | Deferred | Yahoo chart availability/rate limits and DXY conventions need a separately tested adapter; not added in this pass. |
| `russia_oil_exports_crea` | Deferred | External analytical dataset, aggregation definitions and access/redistribution conditions require separate review. |
| `russia_key_rate_monitor` | Excluded | Depends on Cbonds and an application-specific composite score. |
| `russia_key_rate` | Available | `CBR.key_rate`; daily published levels, decimal annual rates. |
| `russia_cpi_saar_monitor` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `cbonds_key_rate_curve_monitor` | Excluded | Cbonds is excluded by the task. |
| `moex_key_rate_futures` | Deferred | Current contract selection and implied-rate conventions need dedicated expiry/roll validation; not a continuous key-rate series. |
| `moex_rusfar_repo` | Available | `MOEXMacro.rusfar(tenor="ON")`. |
| `moex_rusfar_curve_monitor` | Partial | `MOEXMacro.rusfar_curve` supplies all five tenors; no key-rate overlay or heuristic signal. |
| `cbr_ruonia` | Available | `CBR.ruonia`; rate and volume. Publication timestamps are not retained. |
| `russia_ruonia_rusfar_spread` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `moex_rusfar_1w` | Available | `MOEXMacro.rusfar(tenor="1W")`. |
| `moex_rusfar_2w` | Available | `MOEXMacro.rusfar(tenor="2W")`. |
| `moex_rusfar_1m` | Available | `MOEXMacro.rusfar(tenor="1M")`. |
| `moex_rusfar_3m` | Available | `MOEXMacro.rusfar(tenor="3M")`. |
| `moex_rgbi` | Available | `MOEXMacro.rgbi`; price index. `index("RGBITR", ...)` separately supplies total return. |
| `moex_ofz_26238` | Available | `MOEXMacro.ofz("SU26238RMFS4", ...)`; clean quote as a fraction of par, not inferred YTM. |
| `frg100_deposits` | Deferred | FRG HTML/publication parser and access behavior require separate validation; no stable structured transport reused yet. |
| `russia_cpi_yoy` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_cpi_mom` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_cpi_seasonality` | Deferred | Composite, constituent snapshot or event study: requires source orchestration and methodology validation; raw loaders are provided where available. |
| `russia_key_rate_decision` | Deferred | Daily levels are available; board meeting calendar and decision events are a separate parser, not inferred from rate changes. |
| `russia_inflation_expectations` | Deferred | Source-specific XLSX workbook/discovery and vintage handling; no Excel reader added in this pass. |
| `russia_unemployment_rate` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_business_price_expectations` | Deferred | Source-specific XLSX workbook/discovery and vintage handling; no Excel reader added in this pass. |
| `russia_trade_balance` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_fx_reserves` | Available, alternate source | `CBR.international_reserves`; official weekly/monthly CBR data instead of Investing releases. |
| `russia_monthly_gdp` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_quarterly_gdp` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_budget_balance_gdp` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_ppi_mom` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_ppi_yoy` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_manufacturing_pmi` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_forex_intervention` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_services_pmi` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_retail_sales_yoy` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_industrial_production_yoy` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_real_wage_growth_yoy` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_business_confidence` | Deferred | Investing calendar scraping/anti-bot/session behavior is not a stable public API; no browser/curl impersonation added. |
| `russia_weekly_cpi` | Deferred | Rosstat PDF/HTML discovery, irregular periods and anti-bot fallback need a separately validated loader; no PDF engine added. |
| `russia_minfin_nwf_monitor` | Excluded | Existing source uses the Cbonds adapter; excluded even though the registry labels it derived. |
| `russia_ofz_26243_26233_spread` | Deferred | Needs matched observed YTM or dated cash flows; approximate coupon-based YTM fallback is not copied. |

Unique application indicator codes inspected: **70**. The ledger
includes hidden/legacy definitions; it is not the public site's indicator count.

## Validation record

Local checks passed: 174 offline tests on Python 3.12 with pandas 3.1.1;
174 on Python 3.11 with NumPy 1.26.4, SciPy 1.12.0, pandas 2.2.0 and HTTPX 0.27.0;
174 against the installed wheel on Python 3.11 with pandas 3.0.6/HTTPX 0.28.1.
Core-only wheel installation had no pandas/HTTPX/defusedxml: 115 tests passed,
with the macro test module skipped; both original offline examples also passed.
Ruff, format checks, strict mypy, wheel-from-sdist build and Twine metadata checks
passed. The [release workflow](../.github/workflows/release.yml) also exercises
the macro extra and minimum dependency versions before publication.

2026-11-24: 24 live dataset variants passed from the development machine, with
TLS verification enabled: seven CBR base methods plus weekly/monthly reserves,
USD/EUR/CNY exchange rates, IMOEX/RGBI/RGBITR, five RUSFAR tenors, OFZ 26238,
FRED Treasury yields/Russian nominal GDP, and World Bank annual GDP. Historical
windows were 2024-01-01..2024-03-01 (GDP 2020..2024). These checks validate
retrieval/schema/units/range, not freshness in 2026 or every historical vintage.

HTTPX's default certificate bundle initially failed MOEX's chain on this machine.
Using the operating system trust store with `ssl.create_default_context()` passed;
this is now the macro transport default. No certificate verification was disabled
and no private/application CA bundle is shipped. Machines lacking required roots
must configure an approved CA bundle via their supplied HTTPX client.

Live checks found and corrected CBR's null M0 measure ID/reporting-year offset,
case-sensitive SOAP `fromDate`, and FRED CSV exports ignoring graph date limits.
Tests use authored synthetic responses; provider datasets are not bundled.
