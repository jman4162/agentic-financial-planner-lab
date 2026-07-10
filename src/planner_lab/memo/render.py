"""Render an approved PlanningMemo to markdown with a verification footer."""

from planner_lab.schemas.critic import CriticReport
from planner_lab.schemas.memo import PlanningMemo, ScenarioNarrative, TracedNumber


class MemoRejectedError(RuntimeError):
    def __init__(self, report: CriticReport):
        self.report = report
        blockers = "; ".join(c.details for c in report.blockers())
        super().__init__(f"memo rejected by critic: {blockers}")


def _format_number(n: TracedNumber) -> str:
    if n.unit == "usd":
        value = f"${n.value:,.0f}"
    elif n.unit == "percent":
        value = f"{n.value:.1%}"
    elif n.unit == "ratio":
        value = f"{n.value:.2f}"
    elif n.unit == "years":
        value = f"{n.value:.1f} years"
    else:
        value = f"{n.value:.0f}"
    return f"- **{n.label}:** {value}"


def _render_scenario(scenario: ScenarioNarrative, heading: str) -> list[str]:
    lines = [f"### {heading}", "", scenario.narrative, ""]
    lines.extend(_format_number(n) for n in scenario.key_numbers)
    if scenario.key_numbers:
        lines.append("")
    return lines


def render_markdown(memo: PlanningMemo, report: CriticReport) -> str:
    """Render the memo in the mandated section order. Raises MemoRejectedError
    if the critic report has failing blockers."""
    if not report.approved:
        raise MemoRejectedError(report)

    lines: list[str] = [
        f"# Planning memo: {memo.case_id}",
        "",
        "## 1. Executive summary",
        "",
        memo.executive_summary,
        "",
        "## 2. Inputs used",
        "",
        *(_format_number(n) for n in memo.inputs_summary),
        "",
        "## 3. Important missing data",
        "",
    ]
    if memo.missing_data:
        lines.extend(f"- {item}" for item in memo.missing_data)
    else:
        lines.append("- None identified.")
    lines += ["", "## 4. Base-case results", ""]
    lines.extend(_render_scenario(memo.base_case, memo.base_case.label)[2:])
    lines += ["## 5. Stress-case results", ""]
    if memo.stress_cases:
        for scenario in memo.stress_cases:
            lines.extend(_render_scenario(scenario, scenario.label))
    else:
        lines += ["No stress scenarios were run.", ""]
    lines += ["## 6. Main risks", ""]
    lines.extend(f"- {risk}" for risk in memo.risks)
    lines += ["", "## 7. Decision trade-offs", ""]
    lines.extend(f"- {item}" for item in memo.trade_offs)
    lines += ["", "## 8. Suggested next questions", ""]
    lines.extend(f"- {q}" for q in memo.next_questions)
    lines += ["", "## 9. Methodology and citations", "", memo.methodology, ""]
    if memo.citations:
        lines.extend(f"- {c.title} ({c.source_name}: `{c.ref}`)" for c in memo.citations)
        lines.append("")
    lines += ["### Assumptions", ""]
    lines += [
        "| Set | Real return | Volatility | Inflation | Withdrawal rate | Plan end age |",
        "|-----|-------------|------------|-----------|-----------------|--------------|",
    ]
    for aset in memo.assumptions_table.all_sets():
        lines.append(
            f"| {aset.label} | {aset.expected_return_real:.1%} | "
            f"{aset.return_volatility:.0%} | {aset.inflation:.1%} | "
            f"{aset.safe_withdrawal_rate:.1%} | {aset.plan_end_age} |"
        )
    lines += ["", "## 10. Disclaimer", "", memo.disclaimer, ""]

    lines += ["---", "", "## Verification", "", "Critic checks:", ""]
    for check in report.checks:
        status = "pass" if check.passed else "FAIL"
        lines.append(f"- `{check.check_id}` [{check.severity}]: {status} — {check.details}")
    lines += ["", "Traced numbers:", ""]
    for number in memo.all_traced_numbers():
        lines.append(f"- {number.label} = {number.value} (source: `{number.source_id}`)")
    lines.append("")
    return "\n".join(lines)
