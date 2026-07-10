"""Funded ratio: portfolio value versus the capital needed to support spending."""

from planner_lab.calculators.withdrawal import required_capital


def funded_ratio(
    portfolio_value: float,
    annual_spending: float,
    withdrawal_rate: float = 0.04,
) -> dict[str, float]:
    """Compute portfolio value divided by the capital that supports annual spending.

    A ratio of 1.0 means the portfolio exactly covers the spending target at the
    given withdrawal rate; below 1.0 means a shortfall. Point-in-time diagnostic,
    not a guarantee of retirement success.

    Returns a dict with keys "funded_ratio", "required_capital", "withdrawal_rate".
    Raises ValueError on implausible inputs.
    """
    if portfolio_value < 0:
        raise ValueError("portfolio_value must be >= 0")
    capital = required_capital(annual_spending, withdrawal_rate)
    return {
        "funded_ratio": portfolio_value / capital,
        "required_capital": capital,
        "withdrawal_rate": withdrawal_rate,
    }
