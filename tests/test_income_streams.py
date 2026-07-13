"""Guaranteed-income schema, calculator, pipeline, and adapter tests."""

import pytest

from planner_lab.schemas.case_file import IncomeStream, Person
from tests.support.fixtures import make_case


def case_with_ss(monthly: float = 2_800, start_age: int = 67):  # type: ignore[no-untyped-def]
    case = make_case()
    case.income_streams = [
        IncomeStream(
            stream_id="ss-1",
            name="Social Security",
            kind="social_security",
            monthly_amount=monthly,
            start_age=start_age,
        )
    ]
    return case


class TestGuaranteedIncome:
    def test_income_active_only_after_start_age(self) -> None:
        case = case_with_ss()
        assert case.guaranteed_income_at_age(62) == 0.0
        assert case.guaranteed_income_at_age(67) == pytest.approx(2_800 * 12)
        assert case.guaranteed_income_at_age(80) == pytest.approx(2_800 * 12)

    def test_end_age_exclusive(self) -> None:
        case = case_with_ss()
        case.income_streams[0].end_age = 80
        assert case.guaranteed_income_at_age(79) == pytest.approx(2_800 * 12)
        assert case.guaranteed_income_at_age(80) == 0.0

    def test_spouse_stream_uses_own_age(self) -> None:
        case = case_with_ss()
        case.household.persons.append(
            Person(name="Jordan Example", birth_year=1974, planned_retirement_age=62)
        )
        case.income_streams.append(
            IncomeStream(
                stream_id="ss-2",
                name="Spouse SS",
                kind="social_security",
                monthly_amount=2_200,
                start_age=67,
                person_index=1,
            )
        )
        # Primary at 67: spouse (2 years younger) is 65, not yet claiming.
        assert case.guaranteed_income_at_age(67) == pytest.approx(2_800 * 12)
        # Primary at 69: spouse turns 67.
        assert case.guaranteed_income_at_age(69) == pytest.approx((2_800 + 2_200) * 12)

    def test_net_retirement_spending_floors_at_zero(self) -> None:
        case = case_with_ss(monthly=10_000)
        assert case.net_retirement_spending(70) == 0.0

    def test_earliest_retirement_age(self) -> None:
        case = make_case()
        case.household.persons.append(
            Person(name="Jordan Example", birth_year=1974, planned_retirement_age=58)
        )
        assert case.earliest_retirement_age() == 58

    def test_out_of_range_person_index_ignored(self) -> None:
        case = case_with_ss()
        case.income_streams[0].person_index = 5
        assert case.guaranteed_income_at_age(70) == 0.0


class TestPipelineNetEntries:
    def test_gross_and_net_ledger_entries(self) -> None:
        from planner_lab.agents.pipeline import run_analysis
        from tests.support.stub_model import StubModel
        from tests.test_pipeline_stub import make_draft, passing_findings

        # Income must be active at the retirement age (62) for net entries.
        case = case_with_ss(start_age=62)
        case.assumptions.surfaced = False  # type: ignore[union-attr]
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        tools = [e.tool_name for e in result.ledger.entries]
        assert "net_retirement_spending" in tools
        assert tools.count("funded_ratio_net_of_income") == 3  # one per assumption set
        net_entry = next(
            e for e in result.ledger.entries if e.tool_name == "net_retirement_spending"
        )
        assert net_entry.outputs["gross_spending"] == 60_000
        assert net_entry.outputs["guaranteed_income"] == pytest.approx(2_800 * 12)
        assert net_entry.outputs["net_spending"] == pytest.approx(60_000 - 2_800 * 12)

    def test_income_starting_after_retirement_skips_net_entries(self) -> None:
        from planner_lab.agents.pipeline import run_analysis
        from tests.support.stub_model import StubModel
        from tests.test_pipeline_stub import make_draft, passing_findings

        case = case_with_ss(start_age=67)  # retires at 62; no income at 62
        case.assumptions.surfaced = False  # type: ignore[union-attr]
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert not any(e.tool_name == "net_retirement_spending" for e in result.ledger.entries)

    def test_no_streams_no_net_entries(self) -> None:
        from planner_lab.agents.pipeline import run_analysis
        from tests.support.stub_model import StubModel
        from tests.test_pipeline_stub import make_draft, passing_findings

        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert not any(
            e.tool_name in {"net_retirement_spending", "funded_ratio_net_of_income"}
            for e in result.ledger.entries
        )


class TestMontePlanIncomeMapping:
    def test_streams_reach_plan_config(self) -> None:
        pytest.importorskip("monteplan")
        from planner_lab.adapters.monteplan.simulator import _build_plan

        case = case_with_ss()
        case.household.persons.append(
            Person(name="Jordan Example", birth_year=1974, planned_retirement_age=62)
        )
        case.income_streams.append(
            IncomeStream(
                stream_id="ss-2",
                name="Spouse SS",
                kind="social_security",
                monthly_amount=2_200,
                start_age=67,
                person_index=1,
            )
        )
        assert case.assumptions is not None
        plan = _build_plan(case, case.assumptions.base)
        assert len(plan.guaranteed_income) == 2
        primary_stream = plan.guaranteed_income[0]
        assert primary_stream.monthly_amount == 2_800
        assert primary_stream.start_age == 67
        assert primary_stream.cola_rate == 0.0
        # Spouse is 2 years younger: their age-67 start is primary age 69.
        assert plan.guaranteed_income[1].start_age == 69

    def test_income_improves_success_probability(self) -> None:
        pytest.importorskip("monteplan")
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator

        base_case = make_case()
        ss_case = case_with_ss()
        assert base_case.assumptions is not None and ss_case.assumptions is not None
        without = MontePlanSimulator().simulate(
            base_case, base_case.assumptions.base, n_paths=500, seed=7
        )
        with_ss = MontePlanSimulator().simulate(
            ss_case, ss_case.assumptions.base, n_paths=500, seed=7
        )
        assert with_ss.success_probability > without.success_probability


class TestFundednessSegments:
    def test_segments_net_out_income(self) -> None:
        pytest.importorskip("fundedness")
        from planner_lab.adapters.fundedness_metric.metric import (
            _retirement_spending_segments,
        )

        case = case_with_ss()  # retire 62, SS 2800/mo from 67, target 60k
        segments = _retirement_spending_segments(
            case, current_age=54, retirement_age=62, plan_end_age=95
        )
        assert segments == [
            (8, 13, 60_000.0),  # 62-67: full spending
            (13, None, 60_000.0 - 2_800 * 12),  # 67+: net of SS
        ]

    def test_no_streams_single_open_segment(self) -> None:
        pytest.importorskip("fundedness")
        from planner_lab.adapters.fundedness_metric.metric import (
            _retirement_spending_segments,
        )

        case = make_case()
        segments = _retirement_spending_segments(
            case, current_age=54, retirement_age=62, plan_end_age=95
        )
        assert segments == [(8, None, 60_000.0)]

    def test_income_lowers_liability_pv(self) -> None:
        pytest.importorskip("fundedness")
        from planner_lab.adapters.fundedness_metric.metric import FundednessMetric

        base_case = make_case()
        ss_case = case_with_ss()
        assert base_case.assumptions is not None and ss_case.assumptions is not None
        without = FundednessMetric().compute(base_case, base_case.assumptions.base)
        with_ss = FundednessMetric().compute(ss_case, ss_case.assumptions.base)
        assert with_ss.components["liability_pv"] < without.components["liability_pv"]
        assert with_ss.value > without.value


class TestSSComparison:
    def test_comparison_records_three_ages(self) -> None:
        pytest.importorskip("monteplan")
        from planner_lab.agents.pipeline import _run_ss_comparison
        from planner_lab.schemas.results import ComputationLedger

        case = case_with_ss()
        ledger = ComputationLedger(case_id=case.case_id)
        _run_ss_comparison(case, ledger, n_paths=300, seed=7)
        entries = [e for e in ledger.entries if e.tool_name == "ss_claiming_comparison"]
        assert [e.outputs["claiming_age"] for e in entries] == [62, 67, 70]
        benefits = [e.outputs["monthly_benefit_total"] for e in entries]
        assert benefits[0] == pytest.approx(2_800 * 0.70, rel=1e-6)
        assert benefits[1] == pytest.approx(2_800)
        assert benefits[2] == pytest.approx(2_800 * 1.24, rel=1e-6)
        # The original case is untouched.
        assert case.income_streams[0].monthly_amount == 2_800

    def test_no_ss_streams_no_entries(self) -> None:
        pytest.importorskip("monteplan")
        from planner_lab.agents.pipeline import _run_ss_comparison
        from planner_lab.schemas.results import ComputationLedger

        case = make_case()
        ledger = ComputationLedger(case_id=case.case_id)
        _run_ss_comparison(case, ledger, n_paths=300, seed=7)
        assert ledger.entries == []
