# v0.1 scope and implementation record

## Phase 1: audit and public API

The existing host repository is a non-distributable application (`tool.uv.package=false`).
The initial distribution was implemented under packages/simulacre-finance without
replacing the host metadata/source. It is now maintained in the independent public
KaigorodovTuskul/simulacre-finance repository.
Core dependencies: NumPy + SciPy. HTTPX is an optional transport extra; no Pandas,
optimizer framework, LLM client, backend, service or credential dependency.

Public modules: `data` (Metadata, PriceData, ReturnData, load_csv), `providers`
(MoexISS, Instrument), `portfolio` (optimize, OptimizationResult), `risk`
(risk_report, historical_tail_risk, turnover), `bonds` (CashFlow, FixedCashflows,
fixed_rate_bullet, bond_analytics, yield_to_maturity), `backtest` (walk_forward,
compare_methods, BacktestResult), `rates` (simple_accrual_factor), and exceptions.
Every module is callable offline; only MoexISS's default HTTP transport needs network.

Portfolio Models stable cf90e1f was inspected (models.py, advanced_models.py, tests).
GMV quadratic minimization, ERC convex log-barrier and Rockafellar-Uryasev CVaR LP
are adapted under MIT. Equal weight is the same mathematical baseline. Public APIs,
input validation, execution engine and bond cash-flow implementation are new.
The host's multi-asset allocator embeds synthetic assumptions and special policy caps,
so it is not copied into a general-purpose numerical package.

Public Simulacre portal and MCP documentation were inspected. They publish snapshots
and schema discovery; authenticated remote MCP requires OAuth/personal keys. We do
not introduce an unverified authenticated client. Plain functions remain the boundary.
Ziplime supplied architectural lessons (execution lag, costs, no future observations),
not code. See NOTICE and LICENSE for attribution and dependency licenses.

Scope: CSV + MOEX ISS historical closes, four long-only portfolio methods, realized
risk, explicit fixed cash-flow valuation, fixed-rate bullet convenience schedules,
and walk-forward portfolios with costs. Out of scope: brokers/live orders, taxes,
FX conversion, bankruptcy, floating/optional cash flows, forecasting and web UI.

## Completed checkpoints

| Phase | Delivered checkpoint and evidence |
| --- | --- |
| 1. Scope/audit | Existing host application and Portfolio Models algorithms/tests/licenses inspected; contracts and independent package boundary fixed above |
| 2. Distribution | PEP 621 src layout, MIT/NOTICE, typed public exports, py.typed, editable installation and wheel/sdist builds |
| 3. Data | Strict dated matrices and CSV, ISS search/share closes with bounded pagination/retries; deterministic offline fixtures; live public ISIN lookup and four-day SBER close history also verified |
| 4. Portfolio/risk | Four methods, bounds/budget/diagnostics, numerical-scale normalization, realized metrics; analytic GMV/ERC, CVaR grid and tail-risk reference tests |
| 5. Bonds | Explicit fixed dated flows, regular bullet schedules, PV/YTM/durations/convexity, clean-price boundary; hand calculations and finite-difference/round-trip tests |
| 6. Backtesting | Rolling chronological windows, delayed close execution, drift/cash accounting, self-financing fees, all-method comparison and audit logs; hand paths, no-lookahead and scale tests |
| 7. Integration/examples | CSV/portfolio/backtest/risk and bond examples; actual host cash calculation delegation; tested sleeve and normalized MCP history mappings, no unverified authenticated provider |
| 8. Release/review | 114 offline tests, Ruff/format, strict mypy, metadata/content validation, installed-wheel checks and two independent review rounds; final mean 9.1/10 |

## Release validation record

- Editable installation: `uv pip install --python .venv/Scripts/python.exe -e '.[dev]'`
  (equivalent to the README pip command).
- Main environment: Python 3.12.4, NumPy 2.5.5, SciPy 1.18.1; **114 tests pass**.
- Fresh wheel environment: Python 3.11.6, NumPy 1.26.4, SciPy 1.12.0; installed
  from the built wheel (not editable), **114 tests pass**, `pip check` passes.
  Imports resolve to site-packages; HTTPX is absent. This verifies the minimum
  declared numerical versions as well as core independence from network extras.
- `python -m ruff check src tests examples`, `ruff format --check` and
  `python -m mypy` pass. All Python source also parses as Python 3.11 syntax.
- Isolated `python -m build` and `python -m build --no-isolation` both succeed;
  the latter uses the same installed Hatchling 1.27 backend. Wheel is built from
  the sdist, so missing source files do not get hidden by an in-tree wheel build.
- Twine validates wheel/sdist Metadata 2.4; contents include py.typed, LICENSE,
  NOTICE and public modules. Sdist additionally includes tests, fixtures, both
  offline examples, authored CSV and integration documentation. No environment,
  credentials, application source or exchange data are included.
- Both examples execute reproducibly from the installed wheel under isolated
  Python, with an unrelated working directory. Package tests block sockets.
- Host regression scope: **23 tests pass** in cash, sleeve engine, instrument
  engine and futures overlay; `uv lock --check` and `git diff --check` pass.
- Three independent review perspectives: **9.2 finance, 9.1 package, 9.0 reuse**.
  Findings, fixes and scope of each check are in [reviews.md](reviews.md).

This validation record was captured before public repository extraction. Release
publication is documented in releasing.md and the GitHub/PyPI release records.
No production deployment was part of this library validation. A full Docker image
build and unrelated host application tests were not run; changed calculation
callers were tested as listed.

## Financial methodology references

- Rockafellar & Uryasev, Optimization of Conditional Value-at-Risk:
  https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf
- SciPy solver contracts: https://docs.scipy.org/doc/scipy/reference/optimize.html
- MOEX ISS endpoint reference: https://iss.moex.com/iss/reference/
- Portfolio Models source and MIT attribution: see NOTICE.
