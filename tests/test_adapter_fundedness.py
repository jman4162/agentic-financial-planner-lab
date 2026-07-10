import math

import pytest

pytest.importorskip("fundedness")


class TestBuildAssets:
    def test_portfolio_split_three_ways(self) -> None:
        from fundedness.models.assets import AccountType, AssetClass, LiquidityClass

        from planner_lab.adapters.fundedness_metric.metric import _build_assets
        from tests.support.fixtures import make_case

        case = make_case()  # taxable 350k + traditional 520k, portfolio 70/25/5
        assets = _build_assets(case)
        taxable = [a for a in assets if a.name.startswith("Brokerage")]
        assert [a.asset_class for a in taxable] == [
            AssetClass.STOCKS,
            AssetClass.BONDS,
            AssetClass.CASH,
        ]
        assert [a.value for a in taxable] == pytest.approx([245_000, 87_500, 17_500])
        assert all(a.account_type is AccountType.TAXABLE for a in taxable)
        assert all(a.liquidity_class is LiquidityClass.TAXABLE_INDEX for a in taxable)
        trad = [a for a in assets if a.account_type is AccountType.TAX_DEFERRED]
        assert sum(a.value for a in trad) == pytest.approx(520_000)

    def test_cash_account_never_split(self) -> None:
        from fundedness.models.assets import AssetClass, LiquidityClass

        from planner_lab.adapters.fundedness_metric.metric import _build_assets
        from planner_lab.schemas.case_file import Account
        from tests.support.fixtures import make_case

        case = make_case()
        case.balance_sheet.accounts.append(
            Account(account_id="cash-1", name="Savings", account_type="cash", balance=40_000)
        )
        assets = _build_assets(case)
        cash = next(a for a in assets if a.name == "Savings")
        assert cash.asset_class is AssetClass.CASH
        assert cash.liquidity_class is LiquidityClass.CASH
        assert cash.value == 40_000

    def test_no_portfolio_single_asset_per_account(self) -> None:
        from planner_lab.adapters.fundedness_metric.metric import _build_assets
        from tests.support.fixtures import make_case

        case = make_case()
        case.portfolio = None
        assets = _build_assets(case)
        assert len(assets) == len(case.balance_sheet.accounts)


class TestBuildLiabilities:
    def test_retirement_stream_and_debt_amortization(self) -> None:
        from fundedness.models.liabilities import InflationLinkage, LiabilityType

        from planner_lab.adapters.fundedness_metric.metric import _build_liabilities
        from planner_lab.schemas.case_file import Liability as CaseLiability
        from tests.support.fixtures import make_case

        case = make_case()
        case.balance_sheet.liabilities.append(
            CaseLiability(
                liability_id="m1", name="Mortgage", balance=60_000, minimum_annual_payment=12_000
            )
        )
        liabs = _build_liabilities(case, current_age=54, retirement_age=62)
        retirement = liabs[0]
        assert retirement.liability_type is LiabilityType.ESSENTIAL_SPENDING
        assert retirement.annual_amount == 60_000
        assert retirement.start_year == 8
        assert retirement.inflation_linkage is InflationLinkage.CPI
        mortgage = liabs[1]
        assert mortgage.end_year == 5
        assert mortgage.inflation_linkage is InflationLinkage.NONE

    def test_debt_without_payment_becomes_lump(self) -> None:
        from planner_lab.adapters.fundedness_metric.metric import _build_liabilities
        from planner_lab.schemas.case_file import Liability as CaseLiability
        from tests.support.fixtures import make_case

        case = make_case()
        case.balance_sheet.liabilities.append(
            CaseLiability(liability_id="d1", name="Loan", balance=9_000)
        )
        liabs = _build_liabilities(case, current_age=54, retirement_age=62)
        lump = liabs[-1]
        assert lump.annual_amount == 9_000
        assert lump.end_year == 1

    def test_missing_spending_target_rejected(self) -> None:
        from planner_lab.adapters.fundedness_metric.metric import _build_liabilities
        from tests.support.fixtures import make_case

        case = make_case()
        case.goals[0].annual_amount_today = None
        case.cash_flow.annual_expenses = None
        with pytest.raises(ValueError, match="retirement spending target"):
            _build_liabilities(case, current_age=54, retirement_age=62)


class TestCompute:
    def _compute(self, case=None):  # type: ignore[no-untyped-def]
        from planner_lab.adapters.fundedness_metric.metric import FundednessMetric
        from tests.support.fixtures import make_case

        case = case or make_case()
        assert case.assumptions is not None
        return FundednessMetric().compute(case, case.assumptions.base)

    def test_engine_identities_hold(self) -> None:
        from tests.support.fixtures import make_case

        case = make_case()
        result = self._compute(case)
        assert result.metric_name == "cefr"
        assert result.components["gross_assets"] == pytest.approx(
            sum(a.balance for a in case.balance_sheet.accounts)
        )
        assert result.value == pytest.approx(
            result.components["net_assets"] / result.components["liability_pv"]
        )
        assert result.interpretation

    def test_tax_exempt_only_has_zero_tax_haircut(self) -> None:
        from tests.support.fixtures import make_case

        case = make_case()
        for account in case.balance_sheet.accounts:
            account.account_type = "roth"
        result = self._compute(case)
        assert result.components["total_tax_haircut"] == pytest.approx(0.0)

    def test_deterministic(self) -> None:
        assert self._compute().value == self._compute().value

    def test_protocol_satisfied(self) -> None:
        from planner_lab.adapters.fundedness_metric.metric import FundednessMetric
        from planner_lab.protocols import FinancialHealthMetric

        assert isinstance(FundednessMetric(), FinancialHealthMetric)

    def test_inflation_semantics(self) -> None:
        """fundedness discounts in real terms: CPI-linked spending is
        inflation-invariant, while fixed-nominal debt loses real value as the
        inflation assumption rises."""
        from planner_lab.adapters.fundedness_metric.metric import FundednessMetric
        from planner_lab.schemas.case_file import Liability as CaseLiability
        from tests.support.fixtures import make_case

        case = make_case()
        assert case.assumptions is not None
        base = FundednessMetric().compute(case, case.assumptions.base)
        conservative = FundednessMetric().compute(case, case.assumptions.conservative)
        # Only the CPI-linked retirement stream exists: PV is inflation-invariant.
        assert conservative.components["liability_pv"] == pytest.approx(
            base.components["liability_pv"]
        )
        assert not math.isinf(base.value)

        case.balance_sheet.liabilities.append(
            CaseLiability(
                liability_id="m1", name="Mortgage", balance=180_000, minimum_annual_payment=21_600
            )
        )
        base_debt = FundednessMetric().compute(case, case.assumptions.base)
        conservative_debt = FundednessMetric().compute(case, case.assumptions.conservative)
        # The fixed-nominal mortgage stream shrinks in real terms under higher inflation.
        assert conservative_debt.components["liability_pv"] < base_debt.components["liability_pv"]
