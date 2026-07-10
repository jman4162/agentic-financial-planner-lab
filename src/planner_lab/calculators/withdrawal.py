"""Withdrawal-rate arithmetic. Rates are annual decimal fractions."""

_RATE_MIN = 0.01
_RATE_MAX = 0.20


def _validate_rate(withdrawal_rate: float) -> None:
    if not _RATE_MIN <= withdrawal_rate <= _RATE_MAX:
        raise ValueError(
            f"withdrawal_rate={withdrawal_rate} is outside the plausible range "
            f"{_RATE_MIN}-{_RATE_MAX}"
        )


def required_capital(annual_spending: float, withdrawal_rate: float = 0.04) -> float:
    """Capital needed to support annual_spending at the given withdrawal rate."""
    if annual_spending <= 0:
        raise ValueError("annual_spending must be > 0")
    _validate_rate(withdrawal_rate)
    return annual_spending / withdrawal_rate


def sustainable_spending(portfolio_value: float, withdrawal_rate: float = 0.04) -> float:
    """Annual spending the portfolio supports at the given withdrawal rate."""
    if portfolio_value < 0:
        raise ValueError("portfolio_value must be >= 0")
    _validate_rate(withdrawal_rate)
    return portfolio_value * withdrawal_rate
