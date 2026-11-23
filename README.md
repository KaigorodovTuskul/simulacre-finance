# Simulacre Finance

**Portfolio optimization, risk metrics, fixed-cash-flow bonds, and walk-forward backtesting.**

[![Checks](https://github.com/KaigorodovTuskul/simulacre-finance/actions/workflows/release.yml/badge.svg)](https://github.com/KaigorodovTuskul/simulacre-finance/actions/workflows/release.yml)
[![PyPI](https://img.shields.io/pypi/v/simulacre-finance)](https://pypi.org/project/simulacre-finance/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/LICENSE)

A typed Python computation library for reproducible financial research. Run the
entire analytical pipeline offline with your own data. NumPy and SciPy are the
only runtime dependencies; public MOEX ISS access is an optional extra.

Built for [Simulacre AI](https://simulacre-ai.ru/site/) and usable independently
of its website, Telegram bot, MCP server, or accounts.

[Quick start](#quick-start) · [Methods](#what-it-does) · [Examples](#examples) ·
[Methodology](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/methodology.md) · [Integration](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/simulacre-integration.md)

## Install

Python **3.11 or newer**:

```sh
pip install simulacre-finance
# Or add it to a uv project:
uv add simulacre-finance
```

For the optional MOEX HTTP transport:

```sh
pip install "simulacre-finance[http]"
# uv add "simulacre-finance[http]"
```

The distribution is named `simulacre-finance`; import it as `simulacre_finance`.
Source installation is also supported: clone this repository and run `pip install .`.

## What it does

| Area | Available in 0.1.0 |
| --- | --- |
| Data | Validated dated price/return matrices, wide CSV, instrument lookup and paginated MOEX ISS share closes |
| Optimization | Equal weight, global minimum variance, exact equal risk contribution, minimum historical CVaR |
| Risk | Compounded/annualized performance, volatility, Sharpe, drawdown, historical VaR/CVaR, gross turnover |
| Bonds | Explicit dated fixed cash flows, regular fixed-rate bullets, dirty/clean prices, YTM, duration and convexity |
| Backtesting | Rolling training, delayed close execution, drifted holdings, cash, commissions/slippage and rebalance audit logs |
| Integration | Pure Python functions and tested mappings for Simulacre Portfolio Lab and existing MCP history responses |

## Quick start

Supply decimal simple returns, dated oldest first. Every column is one asset;
currency, provenance and annualization are explicit.

```python
from datetime import date

import numpy as np

from simulacre_finance import Metadata, ReturnData, optimize, risk_report

data = ReturnData(
    dates=tuple(date(2024, 1, day) for day in range(1, 5)),
    assets=("SYNTH_A", "SYNTH_B"),
    values=np.array([
        [-0.01, -0.02], [-0.01, 0.02],
        [0.01, -0.02], [0.01, 0.02],
    ]),
    metadata=Metadata("RUB", 252, "authored synthetic", date(2024, 1, 4)),
)

estimate = optimize(data, "minimum_variance")
print(estimate.weights.round(3))  # [0.8 0.2]

# Descriptive IN-SAMPLE risk, not an out-of-sample performance claim.
report = risk_report(
    data.values @ estimate.weights,
    periods_per_year=252,
    annual_risk_free_rate=0.05,
    kind="price",
)
print(report.volatility)
```

For CSV, use `load_csv(path, metadata=...)` with a wide `date,ASSET_A,ASSET_B`
header, then call `.returns()` explicitly. Missing/nonfinite values, duplicate
dates and nonpositive prices raise errors; the library never silently fills them.

## Examples

Clone this repository to run the included offline examples:

```sh
git clone https://github.com/KaigorodovTuskul/simulacre-finance.git
cd simulacre-finance
pip install .
python examples/portfolio.py
python examples/bond.py
```

- [Portfolio research](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/examples/portfolio.py): authored synthetic CSV → all four
  optimizers → walk-forward comparison → realized risk, turnover and costs.
- [Bond valuation](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/examples/bond.py): known fixed coupon schedule → price,
  recovered yield, duration and convexity.
- [Sleeve mapping](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/examples/simulacre_mapping.py) and
  [MCP history mapping](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/examples/mcp_history_mapping.py): adapt existing response
  schemas without adding a network client or private service dependency.

For longer histories, `compare_methods(returns, lookback=60, rebalance_every=20,
execution_lag=1, commission_bps=5, slippage_bps=2)` returns all four methods'
dated equity curves, realized metrics, drifted weights, costs and rebalance logs.

## Financial conventions

- **Units:** `0.05` means 5%; prices, payments and accrued interest are currency
  amounts per supplied notional. Bond prices are not percentages of par.
- **Return provenance:** price-only inputs remain labeled `price`. Total-return
  inputs must already include distributions; coupons/dividends are never inferred.
- **Estimates versus outcomes:** optimizer results describe the training sample.
  Walk-forward results report realized simulated performance separately.
- **Execution:** decisions use trailing observations and execute at a later close.
  Old holdings earn the execution-date return. New weights apply to the next interval.
- **Costs and cash:** initial purchases incur costs; trading is self-financing.
  Residual cash earns zero. The risk-free rate is a metric benchmark only.
- **Exact ERC:** positive-definite covariance is required. If exact equal-risk
  weights violate requested bounds, an explicit infeasibility error is raised.
- **Bonds:** known positive dated flows, nominal periodic yield, explicit settlement
  and day count. Clean price requires caller-supplied accrued interest.

See [methodology and public API](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/methodology.md) for formulas, solver
diagnostics, annualization, tail-risk conventions and full limitations.

## Development and validation

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check src tests examples
python -m ruff format --check src tests examples
python -m mypy
python -m build
python -m twine check dist/*
```

The offline suite has **114 tests**, including analytical optimizer references,
hand-calculated portfolio paths, no-lookahead checks, self-financing fees, provider
pagination failures and bond sensitivity/yield round trips. Fixtures are authored
synthetic data. Core installation and the entire suite were also tested with
Python 3.11, NumPy 1.26.4 and SciPy 1.12.0, without HTTPX.

[CI](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/.github/workflows/release.yml) runs checks before publishing tagged releases.
The [release guide](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/releasing.md) explains versioning and PyPI Trusted Publishing.
Type checks run on Python 3.12; runtime support begins at 3.11.

## Scope and attribution

This is a portfolio research library. Version 0.1 does not model live orders,
taxes, FX conversion, bankruptcy, market impact, nonzero cash yields or historical
universe membership. Calendar/adjustment and point-in-time data selection remain
the caller's responsibility. Floating/optional future bond payments must not be
presented as known fixed cash flows.

[MIT](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/LICENSE). Portfolio formulations are adapted from the audited MIT
[Portfolio Models](https://github.com/KaigorodovTuskul/portfolio-models-agent-skill)
reference; see [NOTICE](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/NOTICE). No exchange datasets or Ziplime code are bundled.
MOEX access does not grant redistribution rights to provider data.

[Changelog](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/CHANGELOG.md) · [Implementation and validation](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/implementation.md) ·
[Independent review record](https://github.com/KaigorodovTuskul/simulacre-finance/blob/main/docs/reviews.md) · [Issues](https://github.com/KaigorodovTuskul/simulacre-finance/issues)
