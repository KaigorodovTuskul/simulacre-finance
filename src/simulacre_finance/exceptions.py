"""Stable exceptions for input, provider and numerical failures."""


class FinanceError(Exception):
    """Base library error."""


class ValidationError(FinanceError, ValueError):
    """Inputs violate a documented contract."""


class DataUnavailableError(FinanceError):
    """A provider could not supply a complete, valid response."""


class OptimizationError(FinanceError):
    """Numerical solver failed or returned an invalid solution."""


class InfeasibleError(OptimizationError):
    """No portfolio satisfies the requested constraints."""
