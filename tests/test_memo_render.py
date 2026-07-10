import pytest

from planner_lab.critic import run_critic
from planner_lab.memo import MemoRejectedError, render_markdown
from tests.support.fixtures import make_case, make_ledger, make_memo

SECTION_ORDER = [
    "## 1. Executive summary",
    "## 2. Inputs used",
    "## 3. Important missing data",
    "## 4. Base-case results",
    "## 5. Stress-case results",
    "## 6. Main risks",
    "## 7. Decision trade-offs",
    "## 8. Suggested next questions",
    "## 9. Methodology and citations",
    "## 10. Disclaimer",
    "## Verification",
]


class TestRender:
    def test_sections_in_mandated_order(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        text = render_markdown(memo, run_critic(memo, ledger, case))
        positions = [text.index(heading) for heading in SECTION_ORDER]
        assert positions == sorted(positions)

    def test_verification_footer_lists_sources(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        text = render_markdown(memo, run_critic(memo, ledger, case))
        for number in memo.all_traced_numbers():
            assert number.source_id in text
        assert "`numbers_traceable` [blocker]: pass" in text

    def test_refuses_unapproved_report(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        memo = make_memo(case, ledger)
        memo.disclaimer = "nope"
        report = run_critic(memo, ledger, case)
        with pytest.raises(MemoRejectedError):
            render_markdown(memo, report)
