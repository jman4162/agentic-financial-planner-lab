import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from planner_lab.calculators import (
    funded_ratio,
    nominal_to_real_rate,
    real_to_nominal_rate,
    required_capital,
    savings_rate,
    sustainable_spending,
    today_to_future_dollars,
    years_to_fi,
)

portfolios = st.floats(min_value=0, max_value=1e9, allow_nan=False)
spendings = st.floats(min_value=1_000, max_value=1e7, allow_nan=False)
rates = st.floats(min_value=0.01, max_value=0.20, allow_nan=False)
scales = st.floats(min_value=0.1, max_value=100, allow_nan=False)


class TestFundedRatio:
    @given(portfolio=portfolios, spending=spendings, rate=rates, k=scales)
    def test_scale_invariance(
        self, portfolio: float, spending: float, rate: float, k: float
    ) -> None:
        base = funded_ratio(portfolio, spending, rate)["funded_ratio"]
        scaled = funded_ratio(portfolio * k, spending * k, rate)["funded_ratio"]
        assert math.isclose(base, scaled, rel_tol=1e-9)

    @given(spending=spendings, rate=rates)
    def test_monotone_in_portfolio(self, spending: float, rate: float) -> None:
        low = funded_ratio(100_000, spending, rate)["funded_ratio"]
        high = funded_ratio(200_000, spending, rate)["funded_ratio"]
        assert high > low

    def test_golden_value(self) -> None:
        result = funded_ratio(900_000, 50_000, 0.04)
        assert math.isclose(result["funded_ratio"], 0.72)
        assert math.isclose(result["required_capital"], 1_250_000)

    def test_rejects_bad_inputs(self) -> None:
        with pytest.raises(ValueError):
            funded_ratio(-1, 50_000)
        with pytest.raises(ValueError):
            funded_ratio(100_000, 0)
        with pytest.raises(ValueError):
            funded_ratio(100_000, 50_000, withdrawal_rate=0.5)
        with pytest.raises(ValueError):
            funded_ratio(100_000, 50_000, withdrawal_rate=0)


class TestWithdrawal:
    @given(spending=spendings, rate=rates)
    def test_round_trip(self, spending: float, rate: float) -> None:
        capital = required_capital(spending, rate)
        assert math.isclose(sustainable_spending(capital, rate), spending, rel_tol=1e-9)


class TestFiTimeline:
    def test_already_funded(self) -> None:
        assert years_to_fi(2_000_000, 10_000, 50_000, 0.04) == 0.0

    def test_zero_return_linear(self) -> None:
        # Needs 1,250,000; has 250,000; saves 100,000/yr with no growth.
        assert math.isclose(years_to_fi(250_000, 100_000, 50_000, 0.0), 10.0)

    def test_unreachable(self) -> None:
        assert math.isinf(years_to_fi(0, 0, 50_000, 0.04))
        # Negative growth, savings below steady-state requirement.
        assert math.isinf(years_to_fi(100_000, 1_000, 50_000, -0.10))

    @given(
        portfolio=st.floats(min_value=0, max_value=500_000),
        spending=st.floats(min_value=10_000, max_value=200_000),
        ret=st.floats(min_value=0.0, max_value=0.10),
    )
    def test_decreasing_in_savings(self, portfolio: float, spending: float, ret: float) -> None:
        slow = years_to_fi(portfolio, 10_000, spending, ret)
        fast = years_to_fi(portfolio, 50_000, spending, ret)
        assert fast <= slow

    def test_savings_rate(self) -> None:
        assert math.isclose(savings_rate(100_000, 60_000), 0.4)
        with pytest.raises(ValueError):
            savings_rate(0, 10_000)


class TestConversions:
    @given(
        rate=st.floats(min_value=-0.2, max_value=0.2),
        inflation=st.floats(min_value=-0.02, max_value=0.15),
    )
    def test_round_trip_identity(self, rate: float, inflation: float) -> None:
        assert math.isclose(
            nominal_to_real_rate(real_to_nominal_rate(rate, inflation), inflation),
            rate,
            abs_tol=1e-9,
        )

    def test_future_dollars(self) -> None:
        assert math.isclose(today_to_future_dollars(100, 0.03, 10), 100 * 1.03**10)
        with pytest.raises(ValueError):
            today_to_future_dollars(100, 0.03, -1)
