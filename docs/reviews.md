# Independent release reviews

The author requested independent subagent scoring from several perspectives,
followed by fixes and another round until the arithmetic mean exceeds 8.5/10.
Reviewers were told to challenge the implementation and not inflate scores.
Scores are review judgments, not a guarantee of investment performance or safety.

## Round 1

| Perspective | Score | Evidence and material findings |
| --- | --- | --- |
| Finance correctness | 8.2 | 79 tests passed; independently found budget/scenario scale sensitivity, a tiny-confidence indexing error and nonfinite derived values |
| Public API/package quality | 7.8 | 79 tests, Ruff, formatting, strict mypy passed; incomplete ISS pagination accepted, complex values silently cast, metadata/provider type validation gaps |
| Simulacre reuse | 8.2 | 79 library + 23 host tests and uv lock check passed; real cash integration verified; documented MCP history schema mismatched actual normalized envelope |

Arithmetic mean: **8.067/10**. This round did not meet the requested threshold.

Changes after this round:

- Solve portfolios at unit budget and normalized scenario scale, then restore
  capital/objective units; verify relative constraints. Add analytic tiny-budget
  and tiny-return regressions for GMV, ERC and CVaR.
- Handle full-sample fractional-tail boundaries, stable-scale risk calculations,
  and explicit errors for unrepresentable results; avoid bond sensitivity overflow.
- Enforce ISS cursor totals, expected page lengths and cursor continuity before
  accepting completion. Add premature-empty/short/changing-total/missing-cursor tests.
- Reject complex values/overflow at numeric boundaries and malformed provider
  ISIN/name fields; validate currency/frequency before requesting history.
- Document/test the actual normalized MCP history envelope separately from raw
  ISS JSON; require caller-supplied currency and vintage.
- Lazy public exports preserve typed API while keeping the cash path free of
  NumPy/SciPy imports. Exclude test/build temporary directories from distribution
  staging and Docker context.

Further checks added explicit LP failure/no-solution and metadata/return rejection
tests. Minimum-version testing found an older-SciPy ERC precision stop at a valid
optimum: a stopped iterate is accepted only after independent stationarity and
risk-fraction verification. Fee solving now uses a dimensionless NAV fraction;
capital-scale tests include 1e-300, 1e-12 and 1e12. The suite contains 114 tests.

## Round 2

| Perspective | Score | Independent evidence |
| --- | --- | --- |
| Finance correctness | 9.2 | 114 tests; 40 generated GMV analytical comparisons at three budgets; independent CVaR allocation grids; irregular bond PV/yield; fee invariance across capital scales up to 1e250 |
| Public API/package quality | 9.1 | 114 tests, Ruff/format/mypy; round-one reproductions fixed; artifact contents/Twine and isolated installed-wheel examples inspected |
| Simulacre reuse | 9.0 | Host regression/lock checks; real MCP mapping; cheap cash imports; independent wheel operation without HTTPX/services |

Arithmetic mean: **9.1/10**, exceeding the requested **8.5** threshold. No remaining
material or release-blocking finding was reported. The finance reviewer reconfirmed
the score after the final dimensionless fee-root change, testing repeated multiasset
rebalances at capital scales 1e-300, 1e-12, 1e12 and 1e250 against unit capital.
The package reviewer required a final artifact refresh/install/test after that edit;
the final release gate is recorded in implementation.md.

The initial package-review round-two attempt hit an account usage limit and returned
no score. It was retried after the user resumed work; only the completed review's
9.1 score is counted. Scores from different versions were not mixed.

