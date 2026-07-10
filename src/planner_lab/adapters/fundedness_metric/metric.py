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


def _build_liabilities(case: CaseFile, current_age: int, retirement_age: int) -> list[Liability]:
    target = case.retirement_spending_target()
    if target is None:
        raise ValueError(
            "case file has no retirement spending target: set "
            "goals[kind=retirement].annual_amount_today or cash_flow.annual_expenses"
        )
    liabilities = [
        Liability(
            name="retirement_spending",
            liability_type=LiabilityType.ESSENTIAL_SPENDING,
            annual_amount=target,
            start_year=max(retirement_age - current_age, 0),
            end_year=None,
            inflation_linkage=InflationLinkage.CPI,
        )
    ]
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
    retirement_age = first.planned_retirement_age or 65
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
