"""PortfolioAnalyticsEngine adapter for the lifecycle-allocation package.

Produces a Merton-style model-implied stock share with human-capital
adjustment, as a DIAGNOSTIC benchmark against the current allocation — never a
recommendation to trade. lifecycle-allocation's rates are real by default,
matching this project's real-rate convention.
"""

from lifecycle_allocation import (
    InvestorProfile,
    recommended_stock_share,
)
from lifecycle_allocation import (
    MarketAssumptions as LifecycleMarketAssumptions,  # monteplan defines the same class name
)

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import PortfolioDiagnostics

_REAL_RISK_FREE = 0.02  # the case file carries no risk-free assumption; documented constant
_DEFAULT_RISK_TOLERANCE = 5  # 1-10 scale; the case file carries no risk-preference field
_DIAGNOSTIC_NOTE = (
    "Diagnostic comparison of a lifecycle-model benchmark against the current "
    "allocation; not a recommendation to change the allocation."
)


class LifecycleAllocationEngine:
    name = "lifecycle"

    def analyze(self, case: CaseFile, assumptions: AssumptionSet) -> PortfolioDiagnostics:
        person = case.household.persons[0]
        age = person.age_in(case.created.year)
        retirement_age = person.planned_retirement_age or 65
        if retirement_age <= age:
            retirement_age = age + 1
        wealth = case.balance_sheet.investable_assets
        if wealth <= 0:
            raise ValueError("lifecycle allocation needs investable assets > 0")

        profile = InvestorProfile(
            age=age,
            retirement_age=retirement_age,
            investable_wealth=wealth,
            after_tax_income=case.cash_flow.annual_take_home,
            risk_tolerance=_DEFAULT_RISK_TOLERANCE,
        )
        market = LifecycleMarketAssumptions(
            mu=assumptions.expected_return_real,
            r=_REAL_RISK_FREE,
            sigma=assumptions.return_volatility,
            real=True,
        )
        result = recommended_stock_share(profile, market)

        findings: dict[str, float] = {
            "alpha_recommended": result.alpha_recommended,
            "alpha_star": result.alpha_star,
            "alpha_unconstrained": result.alpha_unconstrained,
            "human_capital": result.human_capital,
            "hw_ratio": float(result.components["hw_ratio"]),
            "gamma": float(result.components["gamma"]),
        }
        if case.portfolio is not None:
            findings["current_stock_pct"] = case.portfolio.stock_pct
        return PortfolioDiagnostics(
            engine_name=self.name,
            findings=findings,
            notes=[result.explain, _DIAGNOSTIC_NOTE],
        )
