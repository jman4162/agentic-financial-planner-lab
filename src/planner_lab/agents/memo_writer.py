"""Memo writer: the first of the two LLM call sites.

The model drafts prose and picks numbers from an explicit menu of ledger and
case-file sources; everything deterministic (case id, assumptions table,
disclaimer, missing-data floor) is enforced in code afterward, so the LLM can
only affect narrative, selection, and framing — all of which the critic reviews.
"""

import json
from collections.abc import Sequence

from pydantic import BaseModel
from strands.models.model import Model

from planner_lab.agents.structured import get_structured
from planner_lab.memo.disclaimer import REQUIRED_DISCLAIMER
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticReport
from planner_lab.schemas.memo import Citation, PlanningMemo, ScenarioNarrative, TracedNumber
from planner_lab.schemas.results import ComputationLedger, ResearchDocument

_EXCERPT_BUDGET = 1500

_SYSTEM_PROMPT = """\
You write educational financial planning memos. Hard rules:
- Never perform arithmetic. Use only the numbers listed in the prompt, copied
  exactly, each with its given source_id.
- Every dollar amount and percentage you write in prose sentences must also be
  copied from the number menu or the assumption sets. Never derive new figures
  (no computed differences, shares of a total, or per-month conversions). If a
  comparison matters, state the two menu numbers side by side instead of the
  computed gap.
- When a simulation success probability is 100%, write "all simulated paths
  succeeded under these assumptions"; never present any probability as a
  guarantee of outcomes.
- Never recommend buying or selling any specific security, fund, or ticker.
- Never use absolute-certainty language (guaranteed, risk-free, certainly will).
- State clearly that outcomes depend on assumptions.
- Mention the base, conservative, and optimistic assumption sets by name in the
  methodology section, and state that figures are real (today's dollars).
- When citable sources are provided, ground methodology claims in them and list
  the supporting refs in citation_refs. Never list a ref that was not provided.
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
    citation_refs: list[str] = []


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
    lines.append(
        f"- source_id=case:balance_sheet.retirement_investable_assets "
        f"value={case.balance_sheet.retirement_investable_assets}"
    )
    lines.append(f"- source_id=case:balance_sheet.net_worth value={case.balance_sheet.net_worth}")
    for field in ("annual_expenses", "annual_savings", "annual_gross_income"):
        value = getattr(case.cash_flow, field)
        if value is not None:
            lines.append(f"- source_id=case:cash_flow.{field} value={value}")
    for i, person in enumerate(case.household.persons):
        if person.planned_retirement_age is not None:
            lines.append(
                f"- source_id=case:household.persons.{i}.planned_retirement_age "
                f"value={person.planned_retirement_age}"
            )
    for i, goal in enumerate(case.goals):
        if goal.annual_amount_today is not None:
            lines.append(
                f"- source_id=case:goals.{i}.annual_amount_today value={goal.annual_amount_today}"
            )
    for i, stream in enumerate(case.income_streams):
        lines.append(
            f"- source_id=case:income_streams.{i}.monthly_amount "
            f"value={stream.monthly_amount} ({stream.name}, monthly, from age "
            f"{stream.start_age})"
        )
    return "\n".join(lines)


def _citable_sources(research: Sequence[ResearchDocument]) -> str:
    refs = [doc.ref for doc in research]
    lines = [
        "Citable sources. citation_refs is REQUIRED: it must contain at least one of "
        f"{refs} and nothing else.",
    ]
    for doc in research:
        lines.append(f"- ref={doc.ref} title={doc.title}")
        lines.append(f"  excerpt: {doc.text[:_EXCERPT_BUDGET]}")
    return "\n".join(lines)


def _build_prompt(
    case: CaseFile,
    ledger: ComputationLedger,
    feedback: CriticReport | None,
    research: Sequence[ResearchDocument] = (),
) -> str:
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
    if any(e.tool_name == "net_retirement_spending" for e in ledger.entries):
        sections += [
            "",
            "Guaranteed income (Social Security or pensions) is recorded. Present",
            "both the gross funded ratio and the net-of-income funded ratio, and",
            "explain that guaranteed income covers part of the spending target.",
        ]
    if any(e.tool_name == "spending_policy_comparison" for e in ledger.entries):
        sections += [
            "",
            "A spending-policy comparison is in the menu (constant-real, guardrails,",
            "VPW, floor-ceiling, percent-of-portfolio). Present it as a trade-off:",
            "dynamic policies raise portfolio survival by varying annual income.",
            "Never declare one policy correct for the household.",
        ]
    if any(e.tool_name == "sensitivity_analysis" for e in ledger.entries):
        sections += [
            "",
            "Sensitivity impacts are in the menu (success-probability change from a",
            "10% perturbation of each parameter). Name the one or two largest",
            "impacts in the risks section.",
        ]
    if any(e.tool_name == "ss_claiming_comparison" for e in ledger.entries):
        sections += [
            "",
            "A Social Security claiming-age comparison is in the menu (ages 62, 67,",
            "70). Present it as a table of trade-offs in the stress or trade_offs",
            "section. Never advise a specific claiming age; note the factors are",
            "SSA-style approximations relative to a full retirement age of 67.",
        ]
    if any(e.entry_id.startswith("metric:") for e in ledger.entries):
        sections += [
            "",
            "A comprehensive fundedness metric (cefr) is in the number menu: reference",
            "it in the executive summary and discuss its haircut components in risks.",
        ]
    if any(e.entry_id.startswith("portfolio:") for e in ledger.entries):
        sections += [
            "",
            "Allocation diagnostics are in the menu. In risks or trade_offs, compare",
            "current_stock_pct with alpha_recommended strictly as a diagnostic model",
            "comparison. Never phrase it as an instruction to change the allocation.",
        ]
    if research:
        sections += ["", _citable_sources(research)]
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
    research: Sequence[ResearchDocument] = (),
    research_source_name: str = "research",
) -> PlanningMemo:
    if case.assumptions is None:
        raise ValueError("case has no assumptions; build and surface them first")
    if not ledger.entries:
        raise ValueError("ledger is empty; run calculators before drafting a memo")

    draft = get_structured(
        model, MemoDraft, _build_prompt(case, ledger, feedback, research), _SYSTEM_PROMPT
    )

    docs_by_ref = {doc.ref: doc for doc in research}
    citations = [
        Citation(source_name=research_source_name, ref=ref, title=docs_by_ref[ref].title)
        for ref in dict.fromkeys(draft.citation_refs)
        if ref in docs_by_ref
    ]
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
        citations=citations,
        disclaimer=REQUIRED_DISCLAIMER,
    )
