"""Health-metric and portfolio-diagnostics pipeline tests with fakes."""

from planner_lab.agents.pipeline import run_analysis
from tests.support.fake_adapters import FakeHealthMetric, FakePortfolioEngine
from tests.support.fixtures import make_case
from tests.support.stub_model import StubModel
from tests.test_pipeline_stub import make_draft, passing_findings


class TestPipelineDiagnostics:
    def test_metric_and_portfolio_entries_recorded(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(
            case,
            model=model,
            health_metric=FakeHealthMetric(),
            portfolio_engine=FakePortfolioEngine(),
            confirm=lambda _: True,
        )
        assert result.report.approved
        metric_entries = [e for e in result.ledger.entries if e.entry_id.startswith("metric:")]
        portfolio_entries = [
            e for e in result.ledger.entries if e.entry_id.startswith("portfolio:")
        ]
        assert len(metric_entries) == 3  # one per assumption set
        assert {e.assumptions_label for e in metric_entries} == {
            "base",
            "conservative",
            "optimistic",
        }
        assert metric_entries[0].outputs["cefr"] == 1.4
        assert metric_entries[0].adapter == "fake-metric"
        assert len(portfolio_entries) == 1  # base set only
        assert portfolio_entries[0].outputs["alpha_recommended"] == 0.72

    def test_prompt_carries_diagnostic_guidance_and_sources(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        run_analysis(
            case,
            model=model,
            health_metric=FakeHealthMetric(),
            portfolio_engine=FakePortfolioEngine(),
            confirm=lambda _: True,
        )
        prompt = model.structured_output_calls[0][1]
        assert "fundedness metric (cefr)" in prompt
        assert "Never phrase it as an instruction" in prompt
        assert "ledger:metric:compute_health_metric:" in prompt.replace("source_id=", "")
        assert "#alpha_recommended" in prompt

    def test_metric_value_is_citable(self) -> None:
        from planner_lab.schemas.memo import TracedNumber

        case = make_case(surfaced=False)
        draft = make_draft(case)
        model = StubModel([draft, passing_findings()])
        result = run_analysis(
            case, model=model, health_metric=FakeHealthMetric(), confirm=lambda _: True
        )
        entry = next(e for e in result.ledger.entries if e.entry_id.startswith("metric:"))
        number = TracedNumber(
            label="CEFR (base)",
            value=1.4,
            unit="ratio",
            source_id=f"ledger:{entry.entry_id}#cefr",
        )
        assert result.ledger.resolve(number.source_id, case) == 1.4

    def test_no_flags_no_entries(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert not any(
            e.entry_id.startswith(("metric:", "portfolio:")) for e in result.ledger.entries
        )
