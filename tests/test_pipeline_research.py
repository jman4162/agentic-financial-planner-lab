"""Research-enabled pipeline tests with fake source and scripted model."""

import pytest

from planner_lab.agents.pipeline import run_analysis
from planner_lab.memo.render import MemoRejectedError
from tests.support.fake_adapters import make_fake_research_source
from tests.support.fixtures import make_case
from tests.support.stub_model import StubModel
from tests.test_pipeline_stub import make_draft, passing_findings


def draft_with_citation(case):  # type: ignore[no-untyped-def]
    draft = make_draft(case)
    draft.citation_refs = ["doc-1"]
    return draft


class TestPipelineResearch:
    def test_research_entries_and_citations(self) -> None:
        case = make_case(surfaced=False)
        source = make_fake_research_source()
        model = StubModel([draft_with_citation(case), passing_findings()])
        result = run_analysis(case, model=model, research_source=source, confirm=lambda _: True)
        assert result.report.approved
        research_entries = [e for e in result.ledger.entries if e.entry_id.startswith("research:")]
        assert any(e.tool_name == "search_research" for e in research_entries)
        fetches = [e for e in research_entries if e.tool_name == "fetch_research"]
        assert fetches and fetches[0].outputs["ref"] == "doc-1"
        assert [c.ref for c in result.memo.citations] == ["doc-1"]
        assert result.memo.citations[0].source_name == "fake"
        assert result.memo.citations[0].title == "Withdrawal rates explained"
        # Both configured queries were searched.
        assert source.search_calls == [case.question, "safe withdrawal rate"]

    def test_prompt_contains_truncated_citable_sources(self) -> None:
        case = make_case(surfaced=False)
        source = make_fake_research_source()
        model = StubModel([draft_with_citation(case), passing_findings()])
        run_analysis(case, model=model, research_source=source, confirm=lambda _: True)
        from planner_lab.agents.memo_writer import _EXCERPT_BUDGET

        prompt = model.structured_output_calls[0][1]
        assert "Citable sources" in prompt
        assert "ref=doc-1" in prompt
        doc_text = source._docs["doc-1"].text
        assert doc_text[:_EXCERPT_BUDGET] in prompt
        assert doc_text[: _EXCERPT_BUDGET + 1] not in prompt

    def test_missing_citations_fail_then_recover(self) -> None:
        case = make_case(surfaced=False)
        source = make_fake_research_source()
        # First draft cites nothing -> citations_present blocker -> revision cites.
        model = StubModel(
            [
                make_draft(case),
                passing_findings(),
                draft_with_citation(case),
                passing_findings(),
            ]
        )
        result = run_analysis(case, model=model, research_source=source, confirm=lambda _: True)
        assert result.report.approved
        assert [c.ref for c in result.memo.citations] == ["doc-1"]
        rewrite_prompt = model.structured_output_calls[2][1]
        assert "citations_present" in rewrite_prompt

    def test_unknown_refs_dropped_and_rejected(self) -> None:
        case = make_case(surfaced=False)
        source = make_fake_research_source()
        bad = make_draft(case)
        bad.citation_refs = ["invented-ref"]
        model = StubModel([bad, passing_findings(), bad, passing_findings()])
        with pytest.raises(MemoRejectedError) as exc_info:
            run_analysis(case, model=model, research_source=source, confirm=lambda _: True)
        assert any(c.check_id == "citations_present" for c in exc_info.value.report.blockers())

    def test_no_research_keeps_previous_behavior(self) -> None:
        case = make_case(surfaced=False)
        model = StubModel([make_draft(case), passing_findings()])
        result = run_analysis(case, model=model, confirm=lambda _: True)
        assert result.report.approved
        assert result.memo.citations == []
        assert not any(e.entry_id.startswith("research:") for e in result.ledger.entries)
