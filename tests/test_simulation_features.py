"""Spending policies, multi-asset markets, sensitivity, and goal-event mapping."""

import pytest

from planner_lab.schemas.case_file import Account, Goal
from tests.support.fixtures import make_case

pytestmark = pytest.mark.skipif(
    pytest.importorskip("monteplan", reason="planning extra") is None, reason="monteplan"
)


class TestMultiAssetMarket:
    def test_builds_correlated_asset_classes(self) -> None:
        from planner_lab.adapters.monteplan.simulator import _build_market

        case = make_case()  # portfolio 70/25/5
        assert case.assumptions is not None
        market = _build_market(case, case.assumptions.base)
        assert [a.name for a in market.assets] == ["Stocks", "Bonds", "Cash"]
        assert [a.weight for a in market.assets] == pytest.approx([0.70, 0.25, 0.05])
        assert market.annual_volatilities == pytest.approx([0.16, 0.06, 0.01])
        assert market.correlation_matrix[0][1] == pytest.approx(0.1)
        assert market.correlation_matrix[0][0] == 1.0

    def test_blended_fallback_without_per_class_fields(self) -> None:
        from planner_lab.adapters.monteplan.simulator import _build_market

        case = make_case()
        assert case.assumptions is not None
        aset = case.assumptions.base.model_copy(update={"stock_return_real": None})
        market = _build_market(case, aset)
        assert len(market.assets) == 1
        assert market.assets[0].name == "Blended portfolio"

    def test_blended_fallback_without_portfolio(self) -> None:
        from planner_lab.adapters.monteplan.simulator import _build_market

        case = make_case()
        case.portfolio = None
        assert case.assumptions is not None
        market = _build_market(case, case.assumptions.base)
        assert len(market.assets) == 1

    def test_zero_weight_class_dropped(self) -> None:
        from planner_lab.adapters.monteplan.simulator import _build_market
        from planner_lab.schemas.case_file import Portfolio

        case = make_case()
        case.portfolio = Portfolio(stock_pct=0.6, bond_pct=0.4, cash_pct=0.0)
        assert case.assumptions is not None
        market = _build_market(case, case.assumptions.base)
        assert [a.name for a in market.assets] == ["Stocks", "Bonds"]


class TestSpendingPolicies:
    def test_policy_recorded_and_changes_results(self) -> None:
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator

        case = make_case()
        assert case.assumptions is not None
        constant = MontePlanSimulator().simulate(case, case.assumptions.base, n_paths=400, seed=7)
        vpw = MontePlanSimulator().simulate(
            case, case.assumptions.base, n_paths=400, seed=7, spending_policy="vpw"
        )
        assert constant.engine_metadata["spending_policy"] == "constant_real"
        assert vpw.engine_metadata["spending_policy"] == "vpw"
        assert vpw.terminal_wealth_percentiles["p50"] != constant.terminal_wealth_percentiles["p50"]

    def test_pipeline_policy_comparison_entries(self) -> None:
        from planner_lab.agents.pipeline import _run_policy_comparison
        from planner_lab.protocols import SPENDING_POLICIES
        from planner_lab.schemas.results import ComputationLedger

        case = make_case()
        ledger = ComputationLedger(case_id=case.case_id)
        _run_policy_comparison(case, ledger, n_paths=200, seed=7)
        entries = [e for e in ledger.entries if e.tool_name == "spending_policy_comparison"]
        assert [e.outputs["spending_policy"] for e in entries] == list(SPENDING_POLICIES)


class TestSensitivity:
    def test_adapter_satisfies_protocol_and_returns_impacts(self) -> None:
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator
        from planner_lab.protocols import SensitivityAnalyzer

        simulator = MontePlanSimulator()
        assert isinstance(simulator, SensitivityAnalyzer)
        case = make_case()
        assert case.assumptions is not None
        impacts = simulator.analyze_sensitivity(case, case.assumptions.base, n_paths=200, seed=7)
        assert impacts
        assert all(isinstance(v, float) for v in impacts.values())

    def test_pipeline_sensitivity_entry(self) -> None:
        from planner_lab.agents.pipeline import _run_sensitivity
        from planner_lab.schemas.results import ComputationLedger

        case = make_case()
        ledger = ComputationLedger(case_id=case.case_id)
        _run_sensitivity(case, ledger, n_paths=200, seed=7)
        entry = next(e for e in ledger.entries if e.tool_name == "sensitivity_analysis")
        assert any(k.startswith("impact_") for k in entry.outputs)


class TestGoalMapping:
    def _case_with_education(self):  # type: ignore[no-untyped-def]
        case = make_case()
        case.balance_sheet.accounts.append(
            Account(
                account_id="529-1",
                name="College 529",
                account_type="education",
                balance=80_000,
            )
        )
        case.goals.append(
            Goal(
                goal_id="college",
                kind="education",
                description="College for kid",
                target_year=2030,
                annual_amount_today=30_000,
            )
        )
        return case

    def test_retirement_assets_exclude_education(self) -> None:
        case = self._case_with_education()
        assert case.balance_sheet.investable_assets == 950_000
        assert case.balance_sheet.retirement_investable_assets == 870_000

    def test_monteplan_education_events(self) -> None:
        from planner_lab.adapters.monteplan.simulator import _build_plan

        case = self._case_with_education()
        assert case.assumptions is not None
        plan = _build_plan(case, case.assumptions.base)
        education_events = [e for e in plan.discrete_events if "education" in e.description]
        assert len(education_events) == 4  # four college years
        assert all(e.amount == -30_000 for e in education_events)
        # 2030 target year: primary born 1972 -> age 58 at first draw.
        assert education_events[0].age == 58

    def test_fundedness_education_liability(self) -> None:
        pytest.importorskip("fundedness")
        from planner_lab.adapters.fundedness_metric.metric import _build_liabilities

        case = self._case_with_education()
        liabs = _build_liabilities(case, current_age=54, retirement_age=62)
        education = next(li for li in liabs if li.name == "education:college")
        assert education.annual_amount == 30_000
        assert education.start_year == 4  # 2030 - 2026
        assert education.end_year == 8
