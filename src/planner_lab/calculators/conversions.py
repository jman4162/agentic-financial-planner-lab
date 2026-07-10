"""Nominal/real conversions: the only place nominal figures enter the system."""


def nominal_to_real_rate(nominal_rate: float, inflation: float) -> float:
    """Fisher relation: real = (1 + nominal) / (1 + inflation) - 1."""
    if inflation <= -1:
        raise ValueError("inflation must be > -1")
    return (1 + nominal_rate) / (1 + inflation) - 1


def real_to_nominal_rate(real_rate: float, inflation: float) -> float:
    """Fisher relation: nominal = (1 + real) * (1 + inflation) - 1."""
    if inflation <= -1:
        raise ValueError("inflation must be > -1")
    return (1 + real_rate) * (1 + inflation) - 1


def today_to_future_dollars(amount_today: float, inflation: float, years: float) -> float:
    """Nominal dollars in `years` that match amount_today's purchasing power."""
    if inflation <= -1:
        raise ValueError("inflation must be > -1")
    if years < 0:
        raise ValueError("years must be >= 0")
    return float(amount_today * (1 + inflation) ** years)
