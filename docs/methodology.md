# API conventions and financial methodology

## Conventions

All returns, yields, rates and weights are decimals: 0.05 means 5%.
Dated matrices are rows of observations, columns of named assets. Dates are strictly
increasing ISO dates. Currency, observation frequency, annualization count, source,
data vintage, adjustment policy and price/total-return classification are explicit.
Inputs with missing/nonfinite values, duplicate dates or prices <= 0 are rejected.
No filling, currency conversion, corporate action or coupon inference takes place.

See [the integration guide](simulacre-integration.md) for product boundaries and
[the implementation audit](implementation.md) for scope and reuse decisions.

## Minimal offline example

```python
from datetime import date
import numpy as np
from simulacre_finance import Metadata, ReturnData, optimize, risk_report

data = ReturnData(
    dates=(date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)),
    assets=("SYNTH_A", "SYNTH_B"),
    values=np.array([[-0.01, -0.02], [-0.01, 0.02], [0.01, -0.02], [0.01, 0.02]]),
    metadata=Metadata("RUB", 252, "authored synthetic", date(2024, 1, 4)),
)
estimate = optimize(data, "minimum_variance")
assert np.allclose(estimate.weights, [0.8, 0.2])
# In-sample descriptive metrics; this is NOT an out-of-sample performance claim.
report = risk_report(data.values @ estimate.weights, periods_per_year=252,
                     annual_risk_free_rate=0.05, kind="price")
print(estimate.weights, report.volatility)
```

## Modules and exact methods

| Module | Public operations | Assumptions |
| --- | --- | --- |
| data | Metadata, PriceData, ReturnData, load_csv | Wide UTF-8 CSV `date,A,B`; positive prices; no implicit filling |
| providers | MoexISS.lookup, MoexISS.history | Public ISS stock/share CLOSE, explicit board/currency, bounded pagination/retries |
| portfolio | optimize, OptimizationResult, METHODS | Long-only bounds, capital budget in (0,1], residual cash earns zero |
| risk | risk_report, historical_tail_risk, turnover | Decimal simple returns, explicit frequency and effective annual risk-free rate |
| bonds | CashFlow, FixedCashflows, fixed_rate_bullet, bond_analytics, yield_to_maturity, year_fraction | Known positive flows, nominal periodic yield; ACT/365F, ACT/360 or 30E/360 |
| backtest | walk_forward, compare_methods, BacktestResult, Rebalance | Rolling training, close fills after explicit lag, costs on gross trades |
| rates | simple_accrual_factor | Simple ACT/365F or ACT/360 cash interest; decimal rate |

`optimize(data, method, bounds=None, budget=1.0, confidence=0.95)` supports:

- `equal_weight`: budget/N; rejects bounds incompatible with exact equal weight.
- `minimum_variance`: minimize w' sample_covariance w (ddof=1), SciPy SLSQP.
- `equal_risk_contribution`: exact equal variance risk fractions from the convex
  log-barrier formulation, SciPy L-BFGS-B; requires positive-definite covariance.
  If exact ERC violates bounds it raises InfeasibleError. It never substitutes
  inverse volatility or a capped approximate portfolio under the same name.
- `minimum_cvar`: minimize empirical loss CVaR with the Rockafellar-Uryasev
  linear program, SciPy HiGHS and sparse constraints. VaR is unrestricted in sign.

Results include asset order, read-only weights, objective, solver/message/iterations,
budget residual and ERC fractions when relevant. Objectives are in-sample variance
(equal weight/GMV), maximum absolute equal-risk-fraction error (ERC), or one-period
decimal loss CVaR. Solver failures raise; no silent clipping or normalization occurs.
An ERC line-search precision stop is accepted only when both stationarity and
equal-risk-fraction residuals pass independent checks; the solver message records it.

RiskReport distinguishes `cumulative_return` (compounded observed performance) from
data `kind='total_return'` (distributions included upstream). Annualization uses
the explicit observation count, not inferred calendar time: growth^(frequency/T)-1.
Volatility uses ddof=1. Sharpe uses arithmetic period excess return and a geometric
per-period risk-free rate. A zero-volatility Sharpe is None. Max drawdown includes
initial wealth. Historical VaR uses the left empirical inverse CDF; CVaR integrates
the worst tail with fractional boundary mass. Both use signed losses, with no
zero floor. `turnover` is gross L1 risky-asset turnover; a full switch is 2.

## Walk-forward accounting

```python
from simulacre_finance import compare_methods

# Use a longer history, e.g. the 60-row synthetic CSV in examples/.
# results = compare_methods(prices.returns(), lookback=12, rebalance_every=5,
#                           execution_lag=1, commission_bps=5, slippage_bps=2)
```

Evaluation starts in cash at the last date of the initial training window. Each
decision uses only its trailing `lookback` returns, executes `execution_lag >= 1`
observed closes later, and applies new holdings to the NEXT interval's return.
Rebalance schedules count observations (not exchange business days). Between
rebalances, weights drift. A fill at a close uses that supplied observed price;
there is no promise that a real order would fill at that price or size.

Fees = (commission_bps + slippage_bps)/10000 times actual gross asset trades.
Initial purchases incur fees. The engine solves the post-fee capital allocation
with SciPy Brent, so fees do not create borrowing. Residual cash earns zero;
the risk-free rate is a metric benchmark only. The same constraints, periods and
costs apply to all four methods; any infeasible method raises explicitly.
BacktestResult contains dated equity, drifted post-close risky/cash weights,
realized returns, turnover/costs, drawdown, rebalance audit records and risk metrics.

## Bonds

`fixed_rate_bullet` constructs only complete regular fixed-coupon schedules with
maturity anchoring and month-end preservation. Coupons are face*rate/frequency.
No stub, holiday rolling, ex-coupon, floating reset, embedded option or unknown
principal assumption is invented. For known amortization/irregular payments,
supply complete explicit FixedCashflows instead.

PV discounts future payments strictly after settlement using
CF/(1+y/m)^(m*t). Yield y is nominal annual compounded m times, t is the selected
day-count fraction. YTM uses a positive-flow monotone price/yield inversion.
Macaulay duration is PV-weighted t, modified duration divides by (1+y/m), and
convexity is the exact second yield derivative/P. Prices and accrued interest
are amounts in the contract currency per supplied notional, never percent of par.
Clean price is absent unless accrued_interest is explicitly supplied under the
caller's instrument convention; clean = dirty - accrued. YTM takes a dirty price.

## Examples, tests and release gate

```sh
python examples/portfolio.py
python examples/bond.py
python -m pytest -q
python -m ruff check src tests examples
python -m ruff format --check src tests examples
python -m mypy
python -m build
python -m twine check dist/*
python -m venv .venv-wheel
# Windows: replace .venv-wheel/bin/python with .venv-wheel/Scripts/python.exe
.venv-wheel/bin/python -m pip install dist/simulacre_finance-0.1.0-py3-none-any.whl
.venv-wheel/bin/python -I -c "import simulacre_finance; print(simulacre_finance.__version__)"
.venv-wheel/bin/python -I examples/portfolio.py
.venv-wheel/bin/python -I examples/bond.py
```

All fixtures are authored synthetic numbers and marked as such. The default suite
blocks sockets, requires no credentials and checks hand-calculated portfolio paths,
known optimizer solutions, fractional-tail risk, no look-ahead, fees/cash accounting,
bond sensitivities and yield round trips. Type checks target Python 3.12 (matching
current NumPy/SciPy stubs); runtime support begins at 3.11. Runtime dependencies
resolve to releases compatible with the chosen Python version.

## Provenance, integration and limitations

The MIT [Portfolio Models source](https://github.com/KaigorodovTuskul/portfolio-models-agent-skill)
was audited and adapted; full attribution is in NOTICE and LICENSE. SciPy supplies
numerical solvers. No exchange datasets or Ziplime code are bundled. MOEX transport
uses the [official ISS interface](https://iss.moex.com/iss/reference/); access does
not grant data redistribution rights. It loads unadjusted observed share closes,
requires asserted currency and defaults to error on null closes. Explicitly
`missing='drop'` skips null closes; it never fills missing sessions. Lookup returns
identifiers, not trade eligibility or financial advice. No live network check is
required for default tests.

Backtests do not model survivorship, delistings/bankruptcy, taxes, financing,
nonzero cash yields, order-book liquidity, FX, or point-in-time universe selection.
Those are caller/data responsibilities, not implied engine features. Price-only
results omit distributions. Statistical annualization assumes comparable periods;
irregular dates are accepted but not annualized by elapsed calendar time. A user's
as_of vintage does not prove historical point-in-time availability.

[Simulacre integration](simulacre-integration.md) documents the actual cash
calculation delegation, sleeve-data mapping and thin MCP tool boundary. No OAuth
client, LLM, credentials or running server is needed by the library. This version
is a research computation package, not a live trading or execution system.

Independent financial, package and integration reviews reached a mean **9.1/10**
after fixes. See [review findings and validation evidence](reviews.md).

