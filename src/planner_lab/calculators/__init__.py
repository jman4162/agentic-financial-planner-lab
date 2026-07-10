"""Deterministic calculators. All rates are real (after inflation) unless named nominal.

These are the only source of arithmetic in the system; agents call them as tools
and never compute numbers themselves.
"""

from planner_lab.calculators.conversions import (
    nominal_to_real_rate,
    real_to_nominal_rate,
    today_to_future_dollars,
)
from planner_lab.calculators.fi_timeline import savings_rate, years_to_fi
from planner_lab.calculators.funded_ratio import funded_ratio
from planner_lab.calculators.withdrawal import required_capital, sustainable_spending

__all__ = [
    "funded_ratio",
    "nominal_to_real_rate",
    "real_to_nominal_rate",
    "required_capital",
    "savings_rate",
    "sustainable_spending",
    "today_to_future_dollars",
    "years_to_fi",
]
