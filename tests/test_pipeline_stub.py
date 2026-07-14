"""End-to-end pipeline tests with a scripted model: no network, no Ollama."""

import pytest

from planner_lab import calculators
from planner_lab.agents.llm_critic import LLMCriticFindings, LLMFinding
from planner_lab.agents.memo_writer import MemoDraft
from planner_lab.agents.pipeline import AssumptionsNotConfirmedError, run_analysis
from planner_lab.memo.disclaimer import REQUIRED_DISCLAIMER
from planner_lab.memo.render import MemoRejectedError
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.memo import ScenarioNarrative, TracedNumber
from tests.support.fixtures import make_case
from tests.support.stub_model import StubModel

METHODOLOGY = (
    "Deterministic funded-ratio arithmetic under base, conservative, and optimistic "
    "assumption sets. All figures are real (today's dollars)."
)


def make_draft(case: CaseFile) -> MemoDraft:
    """A draft whose numbers match what the pipeline's ledger will contain."""
    fr = calculators.funded_ratio(case.balance_sheet.investable_assets, 60_000, 0.04)[
        "funded_ratio"
    ]
    return MemoDraft(
        executive_summary="The household is partially funded for its target.",
        inputs_summary=[
            TracedNumber(
                label="Investable assets",
                value=case.balance_sheet.investable_assets,
                unit="usd",
                source_id="case:balance_sheet.investable_assets",
            )
        ],
        missing_data=list(case.missing_fields),
        base_case=ScenarioNarrative(
            label="base",
            narrative="Base assumptions leave a funding gap against the target.",
            key_numbers=[
                TracedNumber(
                    label="Funded ratio (base)",
                    value=round(fr, 3),
                    unit="ratio",
                    source_id="ledger:calc:funded_ratio:0001#funded_ratio",
                )
            ],
        ),
        stress_cases=[],
        risks=["Sequence-of-returns risk early in retirement."],
        trade_offs=["Working longer raises funding at the cost of time."],
        next_questions=["How flexible is the spending target?"],
        methodology=METHODOLOGY,
    )


def passing_findings() -> LLMCriticFindings:
    return LLMCriticFindings(
        findings=[
            LLMFinding(check_id="certainty_not_overstated", passed=True, details="measured tone"),
            LLMFinding(check_id="no_securities_advice", passed=True, details="no advice"),
        ]
    )


def failing_findings() -> LLMCriticFindings:
    return LLMCriticFindings(
        findings=[
            LLMFinding(
                check_id="certainty_not_overstated",
                passed=False,
                details="tone implies certainty",
                evidence=["will succeed"],
            )
        ]
    )


class TestStructuredRetry:
    def test_empty_first_response_retries_once(self) -> None:
        from typing import Any

        from planner_lab.agents.structured import get_structured
        from tests.support.stub_model import StubModel

        class FlakyModel(StubModel):
            def __init__(self, outputs: list[Any]):
                super().__init__(outputs)
                self.calls = 0

            async def structured_output(self, output_model, prompt, system_prompt=None, **kw):  # type: ignore[no-untyped-def]
                self.calls += 1
                if self.calls == 1:
                    yield {"progress": "no output key on first attempt"}
                    return
                async for event in super().structured_output(
                    output_model, prompt, system_prompt, **kw
                ):
                    yield event

        findings = passing_findings()
        model = FlakyModel([findings])
        result = get_structured(model, type(findings), "prompt", "system")
        assert model.calls == 2
        assert result == findings


class TestStructuredTimeout:
    def test_hung_first_attempt_times_out_and_retries(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import asyncio
        from typing import Any

        from planner_lab.agents.structured import get_structured
        from tests.support.stub_model import StubModel

        monkeypatch.setenv("PLANNER_LAB_LLM_TIMEOUT", "0.2")

        class HangingModel(StubModel):
            def __init__(self, outputs: list[Any]):
                super().__init__(outputs)
                self.calls = 0

            async def structured_output(self, output_model, prompt, system_prompt=None, **kw):  # type: ignore[no-untyped-def]
                self.calls += 1
                if self.calls == 1:
                    await asyncio.sleep(60)  # simulates a generation loop
                async for event in super().structured_output(
                    output_model, prompt, system_prompt, **kw
                ):
                    yield event

        findings = passing_findings()
        model = HangingModel([findings])
        result = get_structured(model, type(findings), "prompt", "system")
        assert model.calls == 2
        assert result == findings


class TestPipeline:
    def test_happy_path_produces_approved_memo(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert result.report.approved
        assert result.memo.disclaimer == REQUIRED_DISCLAIMER
        assert result.memo.case_id == case.case_id
        assert case.assumptions is not None and case.assumptions.surfaced
        # Three assumption sets ran three calculators each.
        assert len(result.ledger.entries) == 9
        assert model.structured_output_calls[0][0] is MemoDraft
        assert model.structured_output_calls[1][0] is LLMCriticFindings

    def test_declined_assumptions_stop_the_run(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel()
        with pytest.raises(AssumptionsNotConfirmedError):
            run_analysis(case, model=model, confirm=lambda _: False)
        assert model.structured_output_calls == []

    def test_revision_loop_recovers_once(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel(
            [make_draft(case), failing_findings(), make_draft(case), passing_findings()]
        )
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert result.report.approved
        assert len(model.structured_output_calls) == 4
        # The rewrite prompt carries the critic feedback.
        rewrite_prompt = model.structured_output_calls[2][1]
        assert "reviewer rejected" in rewrite_prompt

    def test_second_rejection_raises(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel(
            [make_draft(case), failing_findings(), make_draft(case), failing_findings()]
        )
        with pytest.raises(MemoRejectedError):
            run_analysis(case, model=model, confirm=lambda _: True)

    def test_untraceable_draft_number_is_caught(self) -> None:
        case = make_case(surfaced=False)
        bad_draft = make_draft(case)
        bad_draft.base_case.key_numbers.append(
            TracedNumber(label="Invented", value=1.23, unit="ratio", source_id="ledger:nope#x")
        )
        model = StubModel([bad_draft, passing_findings(), bad_draft, passing_findings()])
        with pytest.raises(MemoRejectedError) as exc_info:
            run_analysis(case, model=model, confirm=lambda _: True)
        assert any(c.check_id == "numbers_traceable" for c in exc_info.value.report.blockers())
