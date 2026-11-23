"""Four long-only methods adapted from the MIT Portfolio Models reference (NOTICE)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from scipy import sparse
from scipy.optimize import LinearConstraint, linprog, minimize

from .data import FloatArray, ReturnData, frozen_array
from .exceptions import InfeasibleError, OptimizationError, ValidationError
from .risk import historical_tail_risk

Method = Literal["equal_weight", "minimum_variance", "equal_risk_contribution", "minimum_cvar"]
METHODS: tuple[Method, ...] = (
    "equal_weight",
    "minimum_variance",
    "equal_risk_contribution",
    "minimum_cvar",
)


@dataclass(frozen=True)
class OptimizationResult:
    """In-sample result. objective units: variance, risk-budget error or loss CVaR."""

    assets: tuple[str, ...]
    weights: FloatArray
    method: Method
    objective: float
    solver: str
    message: str
    iterations: int
    budget_residual: float
    risk_fractions: FloatArray | None = None


def optimize(
    data: ReturnData,
    method: Method = "minimum_variance",
    *,
    bounds: tuple[tuple[float, float], ...] | None = None,
    budget: float = 1.0,
    confidence: float = 0.95,
) -> OptimizationResult:
    """Optimize historical scenarios; never implies a forecast or realized performance.

    bounds are per-asset long-only capital bounds; budget in (0,1] leaves zero-return
    cash. ERC solves the exact positive risk-budget log-barrier problem. If its
    unique normalized solution violates bounds, raise InfeasibleError rather than
    relabel a constrained approximation as equal risk contribution.
    """
    if method not in METHODS:
        raise ValidationError(f"method must be one of {METHODS}")
    a = data.values
    t, n = a.shape
    if t < 2:
        raise ValidationError("Optimization needs at least two return observations")
    if not math.isfinite(budget) or not 0 < budget <= 1:
        raise ValidationError("Long-only budget must lie in (0,1]")
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValidationError("confidence must lie in (0,1)")
    limits = frozen_array(bounds if bounds is not None else [(0.0, budget)] * n)
    if limits.shape != (n, 2) or np.any(limits[:, 0] < 0) or np.any(limits[:, 1] < limits[:, 0]):
        raise ValidationError(
            "bounds must be N finite (lower, upper) pairs with 0 <= lower <= upper"
        )
    if np.any(limits[:, 0] > budget * (1 + 1e-10)):
        raise InfeasibleError("Bounds cannot satisfy the capital budget")
    # Solve in unit-budget coordinates; absolute solver tolerances must not erase
    # small capital budgets. Upper bounds above the entire budget are redundant.
    limits = np.column_stack((limits[:, 0] / budget, np.minimum(limits[:, 1], budget) / budget))
    lower, upper = limits[:, 0], limits[:, 1]
    if lower.sum() > 1 + 1e-10 or upper.sum() < 1 - 1e-10:
        raise InfeasibleError("Bounds cannot satisfy the capital budget")
    # Normalize scenarios before covariance/LP construction to preserve tiny
    # returns and avoid squaring huge raw inputs inside NumPy's covariance.
    scenario_scale = float(np.max(np.abs(a))) or 1.0
    scenarios = a / scenario_scale
    cov = np.atleast_2d(np.cov(scenarios, rowvar=False, ddof=1))
    cov = (cov + cov.T) / 2
    scale = float(np.max(np.abs(cov)))
    s = cov / scale if scale > 0 else cov.copy()

    def variance(x: FloatArray) -> float:
        return float(x @ s @ x)

    def variance_gradient(x: FloatArray) -> FloatArray:
        return np.asarray(2 * s @ x, dtype=np.float64)

    message, solver, iterations = "Analytical weights", "analytical", 0
    fractions = None
    if method == "equal_weight":
        w = np.full(n, 1 / n)
        objective = float(w @ cov @ w)
    elif method == "minimum_variance":
        if np.allclose(lower.sum(), 1, rtol=0, atol=1e-12):
            w = lower.copy()
        elif np.allclose(upper.sum(), 1, rtol=0, atol=1e-12):
            w = upper.copy()
        else:
            x0 = lower + (1 - lower.sum()) * (upper - lower) / (upper - lower).sum()
            answer = minimize(
                variance,
                x0,
                jac=variance_gradient,
                method="SLSQP",
                bounds=limits,
                constraints=LinearConstraint(np.ones((1, n)), 1.0, 1.0),
                options={"ftol": 1e-12, "maxiter": 2000},
            )
            if not answer.success:
                raise OptimizationError(f"SLSQP failed: {answer.message}")
            w = answer.x
            solver, message, iterations = "SLSQP", str(answer.message), int(answer.nit)
        objective = float(w @ cov @ w)
    elif method == "equal_risk_contribution":
        if np.linalg.eigvalsh(s).min() <= 1e-12:
            raise ValidationError("Exact ERC requires a positive-definite sample covariance")
        b = np.full(n, 1 / n)

        def risk_budget_objective(y: FloatArray) -> float:
            return float(0.5 * y @ s @ y - b @ np.log(y))

        def risk_budget_gradient(y: FloatArray) -> FloatArray:
            return np.asarray(s @ y - b / y, dtype=np.float64)

        erc_answer = minimize(
            risk_budget_objective,
            np.sqrt(b / np.diag(s)),
            jac=risk_budget_gradient,
            method="L-BFGS-B",
            bounds=[(1e-12, None)] * n,
            options={"maxiter": 3000, "ftol": 1e-15, "gtol": 1e-10},
        )
        # Older SciPy may report a line-search precision stop at the optimum.
        # Accept it only with independently verified first-order stationarity;
        # the risk-fraction residual below is a second financial check.
        stationary = float(np.max(np.abs(risk_budget_gradient(erc_answer.x)))) <= 1e-7
        if not erc_answer.success and not stationary:
            raise OptimizationError(f"ERC solver failed: {erc_answer.message}")
        w = erc_answer.x / erc_answer.x.sum()
        fractions = frozen_array(w * (s @ w) / (w @ s @ w))
        objective = float(np.max(np.abs(fractions - b)))
        if objective > 5e-5:
            raise OptimizationError(f"ERC risk-budget residual: {objective}")
        solver, message, iterations = "L-BFGS-B", str(erc_answer.message), int(erc_answer.nit)
        if not erc_answer.success:
            message += "; accepted after stationarity and risk-fraction verification"
    else:
        # Rockafellar-Uryasev LP: n weights, free eta, t nonnegative excess losses.
        # A tail smaller than one observation equals the maximum scenario loss.
        tail_mass = max(1.0, (1 - confidence) * t)
        c = np.r_[np.zeros(n), 1.0, np.full(t, 1 / tail_mass)]
        inequalities = sparse.hstack(
            (-sparse.csr_matrix(scenarios), -sparse.csr_matrix(np.ones((t, 1))), -sparse.eye(t))
        )
        lp_bounds: list[tuple[float | None, float | None]] = (
            [(float(lo), float(hi)) for lo, hi in limits] + [(None, None)] + [(0, None)] * t
        )
        # scipy-stubs omits sparse LP matrices accepted by the public HiGHS API.
        lp_answer = linprog(
            c,
            A_ub=cast(Any, inequalities),
            b_ub=np.zeros(t),
            A_eq=cast(Any, sparse.csr_matrix(np.r_[np.ones(n), np.zeros(t + 1)][None, :])),
            b_eq=[1.0],
            bounds=lp_bounds,
            method="highs",
        )
        if not lp_answer.success:
            error = InfeasibleError if lp_answer.status == 2 else OptimizationError
            raise error(f"HiGHS failed: {lp_answer.message}")
        if lp_answer.x is None or lp_answer.fun is None:
            raise OptimizationError("HiGHS returned success without a solution")
        w = lp_answer.x[:n]
        objective = historical_tail_risk(scenarios @ w, confidence=confidence)[1]
        if not np.isclose(objective, lp_answer.fun, atol=1e-7, rtol=1e-7):
            raise OptimizationError("CVaR objective verification failed")
        solver, message, iterations = "HiGHS", str(lp_answer.message), int(lp_answer.nit)
    residual = float(abs(w.sum() - 1))
    if not np.isfinite(w).all() or residual > 1e-7:
        raise OptimizationError("Solver returned nonfinite weights or violated budget")
    if np.any(w < lower - 1e-7) or np.any(w > upper + 1e-7):
        if method in ("equal_weight", "equal_risk_contribution"):
            raise InfeasibleError(f"Exact {method} solution violates the requested bounds")
        raise OptimizationError("Solver returned weights outside requested bounds")
    # Do not clip or renormalize: that can silently violate active constraints.
    if method in ("equal_weight", "minimum_variance"):
        # sqrt first: avoids an intermediate scale**2 overflow when the final
        # objective itself is still representable with a small capital budget.
        volatility = math.sqrt(max(0.0, objective)) * (scenario_scale * budget)
        objective = volatility * volatility
    elif method == "minimum_cvar":
        objective *= scenario_scale * budget
    if not math.isfinite(objective):
        raise OptimizationError("Optimization objective exceeds representable numeric limits")
    return OptimizationResult(
        data.assets,
        frozen_array(w * budget),
        method,
        objective,
        solver,
        message,
        iterations,
        residual * budget,
        fractions,
    )
