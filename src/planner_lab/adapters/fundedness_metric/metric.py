"""FinancialHealthMetric adapter for the fundedness package (CEFR).

CEFR = certainty-equivalent funded ratio: assets after tax, liquidity, and
reliability haircuts divided by the present value of future spending streams.

Mapping notes (verified against fundedness 0.2.4 source):
- Asset values are passed GROSS; the engine applies tax haircuts internally,
  so pre-netting traditional balances would double-tax them.
- fundedness Liability objects are spending streams, not debt balances. The
  retirement spending target becomes a CPI-linked essential-spending stream;
  case debts with a minimum payment become fixed streams until paid; debts
  without a payment become a one-year lump so they are never silently ignored.
- Liabilities are discounted at a fixed 2% real rate (the package default,
  a liability-matching convention). Discounting at the portfolio's expected
  return would flatter optimistic scenarios on both sides of the ratio.
- concentration_level is always DIVERSIFIED: the case file carries only a
  free-text concentration note, so single-stock risk is not modeled here.
"""

import math

from fundedness import Asset, BalanceSheet, Household, Liability, Person, compute_cefr
from fundedness.models.assets import AccountType, AssetClass, LiquidityClass
from fundedness.models.liabilities import InflationLinkage, LiabilityType

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import MetricResult

_REAL_DISCOUNT_RATE = 0.02

# our account_type -> (fundedness AccountType, LiquidityClass, default AssetClass)
_ACCOUNT_MAP: dict[str, tuple[AccountType, LiquidityClass, AssetClass]] = {
    "taxable": (AccountType.TAXABLE, LiquidityClass.TAXABLE_INDEX, AssetClass.STOCKS),
    "traditional": (AccountType.TAX_DEFERRED, LiquidityClass.RETIREMENT, AssetClass.STOCKS),
    "roth": (AccountType.TAX_EXEMPT, LiquidityClass.RETIREMENT, AssetClass.STOCKS),
    "hsa": (AccountType.HSA, LiquidityClass.RETIREMENT, AssetClass.STOCKS),
    "cash": (AccountType.TAXABLE, LiquidityClass.CASH, AssetClass.CASH),
    "education": (AccountType.TAX_EXEMPT, LiquidityClass.RETIREMENT, AssetClass.STOCKS),
    "other": (AccountType.TAXABLE, LiquidityClass.TAXABLE_INDEX, AssetClass.STOCKS),
}


def _build_assets(case: CaseFile) -> list[Asset]:
    """One Asset per account, or up to three per non-cash account split by the
    portfolio's stock/bond/cash weights when a portfolio is present (fundedness
    haircuts differ by asset class; all-stocks would overstate the haircut)."""
    assets: list[Asset] = []
    portfolio = case.portfolio
    for account in case.balance_sheet.accounts:
        account_type, liquidity, default_class = _ACCOUNT_MAP[account.account_type]
        if portfolio is None or default_class is AssetClass.CASH:
            assets.append(
                Asset(
                    name=account.name,
                    value=account.balance,
                    account_type=account_type,
                    asset_class=default_class,
                    liquidity_class=liquidity,
                )
            )
            continue
        slices = (
            (AssetClass.STOCKS, portfolio.stock_pct, "stocks"),
            (AssetClass.BONDS, portfolio.bond_pct, "bonds"),
            (AssetClass.CASH, portfolio.cash_pct, "cash"),
        )
        for asset_class, weight, label in slices:
            if weight <= 0:
                continue
            assets.append(
                Asset(
                    name=f"{account.name} ({label})",
                    value=account.balance * weight,
                    account_type=account_type,
                    asset_class=asset_class,
                    liquidity_class=liquidity,
                )
            )
    return assets


def _retirement_spending_segments(
    case: CaseFile, current_age: int, retirement_age: int, plan_end_age: int
) -> list[tuple[int, int | None, float]]:
    """Split retirement spending into (start_year, end_year, net_annual) segments,
    netting out guaranteed income as streams start and stop. compute_cefr does not
    consume income directly, so income enters as reduced spending. All streams are
    treated as real-constant (today's dollars); v1 ignores fixed-nominal erosion."""
    target = case.retirement_spending_target()
    assert target is not None
    boundaries = {retirement_age}
    primary = case.household.persons[0]
    for stream in case.income_streams:
        if stream.person_index >= len(case.household.persons):
            continue
        owner = case.household.persons[stream.person_index]
        offset = owner.birth_year - primary.birth_year
        for age in (stream.start_age, stream.end_age):
            if age is not None and retirement_age <= age + offset <= plan_end_age:
                boundaries.add(age + offset)
    ordered = sorted(boundaries)
    segments: list[tuple[int, int | None, float]] = []
    for start_age, end_age in zip(ordered, ordered[1:] + [None]):
        if end_age is not None and end_age <= start_age:
            continue
        net = max(target - case.guaranteed_income_at_age(start_age), 0.0)
        if net <= 0:
            continue
        segments.append(
            (
                start_age - current_age,
                end_age - current_age if end_age is not None else None,
                net,
            )
        )
    return segments


def _build_liabilities(case: CaseFile, current_age: int, retirement_age: int) -> list[Liability]:
    target = case.retirement_spending_target()
    if target is None:
        raise ValueError(
            "case file has no retirement spending target: set "
            "goals[kind=retirement].annual_amount_today or cash_flow.annual_expenses"
        )
    plan_end_age = 95
    if case.assumptions is not None:
        plan_end_age = case.assumptions.base.plan_end_age
    liabilities = [
        Liability(
            name=f"retirement_spending_{start_year}",
            liability_type=LiabilityType.ESSENTIAL_SPENDING,
            annual_amount=net,
            start_year=max(start_year, 0),
            end_year=end_year,
            inflation_linkage=InflationLinkage.CPI,
        )
        for start_year, end_year, net in _retirement_spending_segments(
            case, current_age, retirement_age, plan_end_age
        )
    ]
    current_year = case.created.year
    for goal in case.goals:
        if goal.kind not in ("education", "purchase"):
            continue
        if goal.annual_amount_today is None or goal.target_year is None:
            continue
        start_year = max(goal.target_year - current_year, 0)
        duration = 4 if goal.kind == "education" else 1
        liabilities.append(
            Liability(
                name=f"{goal.kind}:{goal.goal_id}",
                liability_type=LiabilityType.DISCRETIONARY_SPENDING,
                annual_amount=goal.annual_amount_today,
                start_year=start_year,
                end_year=start_year + duration,
                inflation_linkage=InflationLinkage.CPI,
            )
        )
    for debt in case.balance_sheet.liabilities:
        if debt.balance <= 0:
            continue
        if debt.minimum_annual_payment:
            liabilities.append(
                Liability(
                    name=debt.name,
                    liability_type=LiabilityType.DEBT,
                    annual_amount=debt.minimum_annual_payment,
                    start_year=0,
                    end_year=math.ceil(debt.balance / debt.minimum_annual_payment),
                    inflation_linkage=InflationLinkage.NONE,
                )
            )
        else:
            liabilities.append(
                Liability(
                    name=debt.name,
                    liability_type=LiabilityType.DEBT,
                    annual_amount=debt.balance,
                    start_year=0,
                    end_year=1,
                    inflation_linkage=InflationLinkage.NONE,
                )
            )
    return liabilities


def _build_household(case: CaseFile, assumptions: AssumptionSet) -> Household:
    current_year = case.created.year
    members = []
    for person in case.household.persons:
        age = person.age_in(current_year)
        members.append(
            Person(
                name=person.name,
                age=age,
                retirement_age=person.planned_retirement_age or 65,
                life_expectancy=max(assumptions.plan_end_age, age + 1),
            )
        )
    first = case.household.persons[0]
    current_age = first.age_in(current_year)
    retirement_age = case.earliest_retirement_age()
    return Household(
        members=members,
        balance_sheet=BalanceSheet(assets=_build_assets(case)),
        liabilities=_build_liabilities(case, current_age, retirement_age),
    )


class FundednessMetric:
    name = "funded"

    def compute(self, case: CaseFile, assumptions: AssumptionSet) -> MetricResult:
        household = _build_household(case, assumptions)
        current_age = case.household.persons[0].age_in(case.created.year)
        result = compute_cefr(
            household=household,
            planning_horizon=max(assumptions.plan_end_age - current_age, 1),
            real_discount_rate=_REAL_DISCOUNT_RATE,
            base_inflation=assumptions.inflation,
        )
        return MetricResult(
            metric_name="cefr",
            value=result.cefr,
            components={
                "gross_assets": result.gross_assets,
                "total_tax_haircut": result.total_tax_haircut,
                "total_liquidity_haircut": result.total_liquidity_haircut,
                "total_reliability_haircut": result.total_reliability_haircut,
                "net_assets": result.net_assets,
                "liability_pv": result.liability_pv,
            },
            interpretation=result.get_interpretation(),
        )
