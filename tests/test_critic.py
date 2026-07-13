"""Each test violates exactly one critic check and asserts only that check fails."""

from planner_lab.critic import run_critic
from planner_lab.schemas.critic import CheckId, CriticCheck, CriticReport
from planner_lab.schemas.memo import Citation, TracedNumber
from tests.support.fixtures import make_case, make_ledger, make_memo


def failing_ids(report: CriticReport) -> set[CheckId]:
    return {c.check_id for c in report.checks if not c.passed}


class TestCriticPasses:
    def test_clean_memo_approved(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        report = run_critic(make_memo(case, ledger), ledger, case)
        assert report.approved
        assert failing_ids(report) == set()


class TestEachCheckFailsAlone:
    def test_numbers_traceable_unresolvable(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.base_case.key_numbers.append(
            TracedNumber(label="Invented", value=42.0, unit="ratio", source_id="ledger:fake#x")
        )
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"numbers_traceable"}
        assert not report.approved

    def test_numbers_traceable_value_mismatch(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.base_case.key_numbers[0].value = 9.99
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"numbers_traceable"}

    def test_no_securities_advice(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.risks.append("You should sell VTSAX shares and buy QQQ stock tomorrow.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"no_securities_advice"}

    def test_disclaimer_missing(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.disclaimer = "For education only."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"disclaimer_present"}

    def test_assumptions_not_surfaced(self) -> None:
        case = make_case(surfaced=False)
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"assumptions_disclosed"}

    def test_assumption_labels_absent_from_methodology(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.methodology = "Deterministic arithmetic. All figures are real."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"assumptions_disclosed"}

    def test_missing_inputs_not_flagged(self) -> None:
        case = make_case()
        case.missing_fields = ["cash_flow.annual_expenses"]
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.missing_data = []
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"missing_inputs_flagged"}

    def test_citations_missing_when_research_used(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        ledger.add(
            "fetch",
            {"ref": "some-guide"},
            {"ref": "some-guide", "title": "Some guide"},
            kind="research",
        )
        memo = make_memo(case, ledger)
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"citations_present"}

    def test_citation_never_fetched(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        ledger.add(
            "fetch",
            {"ref": "some-guide"},
            {"ref": "some-guide", "title": "Some guide"},
            kind="research",
        )
        memo = make_memo(case, ledger)
        memo.citations = [Citation(source_name="research", ref="other-guide", title="Other")]
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"citations_present"}

    def test_nominal_real_warning_does_not_block(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.methodology = "Deterministic arithmetic under base, conservative, and optimistic sets."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"nominal_real_consistent"}
        assert report.approved  # warning only

    def test_certainty_overstated(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.executive_summary = "Retirement at 62 is guaranteed to succeed."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"certainty_not_overstated"}

    def test_diagnostic_framing_flags_imperative_allocation(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        ledger.add(
            "portfolio_diagnostics",
            {"engine": "x"},
            {"alpha_recommended": 0.7},
            kind="portfolio",
        )
        memo = make_memo(case, ledger)
        memo.risks.append("You should increase your allocation to stocks this year.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"diagnostic_framing"}
        assert report.approved  # warning only

    def test_diagnostic_framing_inert_without_portfolio_entries(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.risks.append("You should increase your allocation to stocks this year.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()

    def test_negated_certainty_language_allowed(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.risks.append("Success is not guaranteed; there is no risk-free path.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()


class TestProseNumbers:
    def test_invented_dollar_figure_blocks(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.executive_summary = "You will have roughly $9.9M at retirement."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"prose_numbers_traceable"}
        assert not report.approved

    def test_invented_percentage_blocks(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.risks.append("There is an 83.7% chance this works out.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == {"prose_numbers_traceable"}

    def test_rounded_ledger_value_passes(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        capital = ledger.entries[0].outputs["required_capital"]  # 1,500,000
        memo.base_case.narrative = (
            f"The target requires about ${capital / 1e6:.1f}M of capital."
        )
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()

    def test_assumption_rates_in_prose_pass(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.base_case.narrative = (
            "The base case assumes a 4% real return with 2.5% inflation and a "
            "4% withdrawal rate."
        )
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()

    def test_case_file_dollars_in_prose_pass(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.risks.append("Current expenses of $88,000 exceed the sustainable level.")
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()

    def test_bare_durations_not_scanned(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.base_case.narrative = "Over a 30-year horizon starting at age 62."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()

    def test_ratio_stated_as_percent_passes(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        fr = ledger.entries[0].outputs["funded_ratio"]
        memo.base_case.narrative = f"The plan is about {fr * 100:.0f}% funded."
        report = run_critic(memo, ledger, case)
        assert failing_ids(report) == set()


class TestLLMChecksMerge:
    def test_llm_findings_appended(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)

        def fake_llm_checks(m: object) -> list[CriticCheck]:
            return [
                CriticCheck(
                    check_id="certainty_not_overstated",
                    passed=False,
                    severity="blocker",
                    details="tone implies certainty",
                )
            ]

        report = run_critic(memo, ledger, case, llm_checks=fake_llm_checks)
        assert not report.approved
        assert failing_ids(report) == {"certainty_not_overstated"}
