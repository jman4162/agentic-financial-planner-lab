"""Financial-independence timeline arithmetic. Deterministic, real-dollar terms."""

import math

from planner_lab.calculators.withdrawal import required_capital


def savings_rate(annual_income: float, annual_expenses: float) -> float:
    """Fraction of income saved. Income must be positive; expenses may exceed income."""
    if annual_income <= 0:
        raise ValueError("annual_income must be > 0")
    if annual_expenses < 0:
        raise ValueError("annual_expenses must be >= 0")
    return (annual_income - annual_expenses) / annual_income


def years_to_fi(
    current_portfolio: float,
    annual_savings: float,
    annual_spending: float,
    real_return: float,
    withdrawal_rate: float = 0.04,
) -> float:
    """Years until the portfolio supports annual_spending at withdrawal_rate.

    Solves for n in: P(1+r)^n + S * ((1+r)^n - 1) / r >= target, with annual
    compounding and end-of-year contributions. Returns 0.0 if already funded,
    math.inf if the target is unreachable (no savings and no growth).
    Rates are real; result is in real terms.
    """
    if current_portfolio < 0:
        raise ValueError("current_portfolio must be >= 0")
    if annual_savings < 0:
        raise ValueError("annual_savings must be >= 0")
    if not -0.5 < real_return < 0.5:
        raise ValueError("real_return must be between -0.5 and 0.5")

    target = required_capital(annual_spending, withdrawal_rate)
    if current_portfolio >= target:
        return 0.0

    if abs(real_return) < 1e-12:
        if annual_savings == 0:
            return math.inf
        return (target - current_portfolio) / annual_savings

    r = real_return
    # Solve (1+r)^n = (target*r + S) / (P*r + S). With r < 0 the portfolio tends
    # to the steady state S/(-r); the target is unreachable when either term of
    # the ratio is non-positive.
    numerator = target * r + annual_savings
    denominator = current_portfolio * r + annual_savings
    if numerator <= 0 or denominator <= 0:
        return math.inf
    years = math.log(numerator / denominator) / math.log1p(r)
    return years if years >= 0 else math.inf
