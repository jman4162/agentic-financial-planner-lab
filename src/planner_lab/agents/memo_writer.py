"""Memo writer: the first of the two LLM call sites.

The model drafts prose and picks numbers from an explicit menu of ledger and
case-file sources; everything deterministic (case id, assumptions table,
disclaimer, missing-data floor) is enforced in code afterward, so the LLM can
only affect narrative, selection, and framing — all of which the critic reviews.
"""

import json

from pydantic import BaseModel
from strands.models.model import Model

from planner_lab.agents.structured import get_structured
from planner_lab.memo.disclaimer import REQUIRED_DISCLAIMER
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticReport
from planner_lab.schemas.memo import PlanningMemo, ScenarioNarrative, TracedNumber
from planner_lab.schemas.results import ComputationLedger

_SYSTEM_PROMPT = """\
You write educational financial planning memos. Hard rules:
- Never perform arithmetic. Use only the numbers listed in the prompt, copied
  exactly, each with its given source_id.
- Never recommend buying or selling any specific security, fund, or ticker.
- Never use absolute-certainty language (guaranteed, risk-free, certainly will).
- State clearly that outcomes depend on assumptions.
- Mention the base, conservative, and optimistic assumption sets by name in the
  methodology section, and state that figures are real (today's dollars).
"""


class MemoDraft(BaseModel):
    """The parts of the memo the LLM is allowed to draft."""

    executive_summary: str
    inputs_summary: list[TracedNumber]
    missing_data: list[str]
    base_case: ScenarioNarrative
    stress_cases: list[ScenarioNarrative]
    risks: list[str]
    trade_offs: list[str]
    next_questions: list[str]
    methodology: str


def _number_menu(case: CaseFile, ledger: ComputationLedger) -> str:
    lines = ["Available numbers (cite each with its exact source_id and value):"]
    for entry in ledger.entries:
        for key, value in entry.outputs.items():
            if isinstance(value, (int, float)):
                label = entry.assumptions_label or ""
                lines.append(
                    f"- source_id=ledger:{entry.entry_id}#{key} value={value} "
                    f"({entry.tool_name} {label})".rstrip()
                )
    lines.append(
        f"- source_id=case:balance_sheet.investable_assets "
        f"value={case.balance_sheet.investable_assets}"
    )
    lines.append(f"- source_id=case:balance_sheet.net_worth value={case.balance_sheet.net_worth}")
    for field in ("annual_expenses", "annual_savings", "annual_gross_income"):
        value = getattr(case.cash_flow, field)
        if value is not None:
            lines.append(f"- source_id=case:cash_flow.{field} value={value}")
    return "\n".join(lines)


def _build_prompt(case: CaseFile, ledger: ComputationLedger, feedback: CriticReport | None) -> str:
    assert case.assumptions is not None
    sections = [
        f"Planning question: {case.question}",
        "",
        "Case file (synthetic household):",
        json.dumps(case.model_dump(mode="json", exclude={"assumptions"}), indent=None),
        "",
        "Assumption sets (already confirmed with the user):",
        json.dumps(case.assumptions.model_dump(mode="json"), indent=None),
        "",
        _number_menu(case, ledger),
        "",
        "Draft the planning memo. The base_case scenario must be labeled 'base' and",
        "cite its key numbers from the menu. Add one stress_cases entry labeled",
        "'conservative' using the conservative-set numbers. If the menu contains",
        "simulation success probabilities, cite them too. Copy every value exactly",
        "as given. missing_data must include every entry from the case file's",
        f"missing_fields list: {case.missing_fields}.",
    ]
    if feedback is not None:
        problems = [f"{c.check_id}: {c.details} {c.evidence}" for c in feedback.blockers()]
        sections += [
            "",
            "A reviewer rejected the previous draft. Fix these specific problems:",
            *problems,
        ]
    return "\n".join(sections)


def write_memo(
    case: CaseFile,
    ledger: ComputationLedger,
    model: Model,
    feedback: CriticReport | None = None,
) -> PlanningMemo:
    if case.assumptions is None:
        raise ValueError("case has no assumptions; build and surface them first")
    if not ledger.entries:
        raise ValueError("ledger is empty; run calculators before drafting a memo")

    draft = get_structured(model, MemoDraft, _build_prompt(case, ledger, feedback), _SYSTEM_PROMPT)

    missing = sorted(set(draft.missing_data) | set(case.missing_fields))
    return PlanningMemo(
        case_id=case.case_id,
        executive_summary=draft.executive_summary,
        inputs_summary=draft.inputs_summary,
        missing_data=missing,
        assumptions_table=case.assumptions,
        base_case=draft.base_case,
        stress_cases=draft.stress_cases,
        risks=draft.risks,
        trade_offs=draft.trade_offs,
        next_questions=draft.next_questions,
        methodology=draft.methodology,
        citations=[],
        disclaimer=REQUIRED_DISCLAIMER,
    )
