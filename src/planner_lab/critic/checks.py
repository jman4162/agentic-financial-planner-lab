"""Deterministic critic checks: pure functions from memo/ledger/case to CriticCheck.

Each check inspects exactly one invariant so test fixtures can violate them one
at a time. Blockers stop memo emission; warnings are surfaced but do not.
"""

import math
import re

from planner_lab.memo.disclaimer import REQUIRED_DISCLAIMER
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticCheck
from planner_lab.schemas.memo import PlanningMemo
from planner_lab.schemas.results import ComputationLedger

# Verbs of individualized trade advice near a ticker-like token or fund name.
_ADVICE_PATTERN = re.compile(
    r"\b(buy|sell|short|dump|load up on)\b[^.]{0,40}?"
    r"(\$[A-Z]{1,5}\b|\b[A-Z]{2,5}\b(?=\s+(?:stock|shares|fund|ETF))|\betf\b|\bshares of\b)",
    re.IGNORECASE,
)

_CERTAINTY_PATTERN = re.compile(
    r"\b(guaranteed|guarantee[sd]?|risk[- ]free|certainly will|cannot fail|"
    r"will definitely|assured of)\b",
    re.IGNORECASE,
)

# "not guaranteed", "no guarantee", "nothing is guaranteed" are anti-certainty
# statements, not violations.
_NEGATION_BEFORE = re.compile(
    r"\b(not?|nothing|never|cannot|can't|isn't|aren't|without|no)\b[\w\s']{0,20}$",
    re.IGNORECASE,
)


def _is_negated(prose: str, match: re.Match[str]) -> bool:
    return _NEGATION_BEFORE.search(prose[: match.start()]) is not None


def check_numbers_traceable(
    memo: PlanningMemo, ledger: ComputationLedger, case: CaseFile
) -> CriticCheck:
    """Every TracedNumber must resolve and match its source within rounding tolerance."""
    failures: list[str] = []
    for number in memo.all_traced_numbers():
        resolved = ledger.resolve(number.source_id, case)
        if resolved is None:
            failures.append(f"{number.label}: source_id {number.source_id!r} does not resolve")
        elif not math.isclose(number.value, resolved, rel_tol=0.005, abs_tol=0.51):
            failures.append(f"{number.label}: memo value {number.value} != source value {resolved}")
    return CriticCheck(
        check_id="numbers_traceable",
        passed=not failures,
        severity="blocker",
        details=(
            "all traced numbers resolve to ledger or case-file sources"
            if not failures
            else f"{len(failures)} number(s) failed to trace"
        ),
        evidence=failures,
    )


def check_no_securities_advice(memo: PlanningMemo) -> CriticCheck:
    hits = [m.group(0) for prose in memo.all_prose() for m in _ADVICE_PATTERN.finditer(prose)]
    return CriticCheck(
        check_id="no_securities_advice",
        passed=not hits,
        severity="blocker",
        details=(
            "no individualized securities advice detected"
            if not hits
            else "memo contains buy/sell language about specific securities"
        ),
        evidence=hits,
    )


def check_disclaimer_present(memo: PlanningMemo) -> CriticCheck:
    present = REQUIRED_DISCLAIMER in memo.disclaimer
    return CriticCheck(
        check_id="disclaimer_present",
        passed=present,
        severity="blocker",
        details=(
            "required disclaimer present verbatim"
            if present
            else "memo.disclaimer does not contain the required disclaimer verbatim"
        ),
    )


def check_assumptions_disclosed(memo: PlanningMemo, case: CaseFile) -> CriticCheck:
    problems: list[str] = []
    bundle = case.assumptions
    if bundle is None or not bundle.surfaced:
        problems.append("assumptions were never surfaced to the user")
    methodology = memo.methodology.lower()
    for label in ("base", "conservative", "optimistic"):
        if label not in methodology:
            problems.append(f"methodology does not mention the {label!r} assumption set")
    return CriticCheck(
        check_id="assumptions_disclosed",
        passed=not problems,
        severity="blocker",
        details=(
            "assumptions surfaced and all three labels disclosed in methodology"
            if not problems
            else "assumption disclosure incomplete"
        ),
        evidence=problems,
    )


def check_missing_inputs_flagged(memo: PlanningMemo, case: CaseFile) -> CriticCheck:
    memo_text = "\n".join(memo.missing_data).lower()
    undisclosed = [
        field
        for field in case.missing_fields
        if field.lower() not in memo_text
        and field.split(".")[-1].replace("_", " ") not in memo_text
    ]
    return CriticCheck(
        check_id="missing_inputs_flagged",
        passed=not undisclosed,
        severity="blocker",
        details=(
            "every case-file gap appears in the memo's missing-data section"
            if not undisclosed
            else "case-file gaps absent from the memo's missing-data section"
        ),
        evidence=undisclosed,
    )


def check_citations_present(memo: PlanningMemo, ledger: ComputationLedger) -> CriticCheck:
    research_entries = [e for e in ledger.entries if e.entry_id.startswith("research:")]
    if not research_entries:
        return CriticCheck(
            check_id="citations_present",
            passed=True,
            severity="blocker",
            details="no research sources were used; citation check not applicable",
        )
    problems: list[str] = []
    if not memo.citations:
        problems.append("research was fetched but the memo cites nothing")
    fetched_refs = {
        str(e.outputs.get("ref")) for e in research_entries if e.outputs.get("ref") is not None
    }
    for citation in memo.citations:
        if citation.ref not in fetched_refs:
            problems.append(f"citation {citation.ref!r} was never fetched")
    return CriticCheck(
        check_id="citations_present",
        passed=not problems,
        severity="blocker",
        details=(
            "citations correspond to fetched research"
            if not problems
            else "citation set inconsistent with fetched research"
        ),
        evidence=problems,
    )


def check_nominal_real_consistent(memo: PlanningMemo, ledger: ComputationLedger) -> CriticCheck:
    methodology = memo.methodology.lower()
    states_terms = "real" in methodology or "today's dollars" in methodology
    problems: list[str] = []
    if not states_terms:
        problems.append("methodology does not state whether figures are real or nominal")
    used_nominal = any(e.tool_name == "real_to_nominal_rate" for e in ledger.entries)
    if used_nominal and ("nominal" not in methodology or "real" not in methodology):
        problems.append(
            "nominal conversion was used but methodology does not label both real "
            "and nominal figures"
        )
    return CriticCheck(
        check_id="nominal_real_consistent",
        passed=not problems,
        severity="warning",
        details=(
            "real/nominal terms stated" if not problems else "real/nominal labeling incomplete"
        ),
        evidence=problems,
    )


_IMPERATIVE_ALLOCATION = re.compile(
    r"\b(should|must|need to|recommend(?:ed)?)\b[^.]{0,60}"
    r"\b(allocation|stock share|equity exposure|rebalanc\w+)\b",
    re.IGNORECASE,
)


def check_diagnostic_framing(memo: PlanningMemo, ledger: ComputationLedger) -> CriticCheck:
    """Allocation diagnostics must stay comparative; imperative allocation
    prose is flagged. Warning severity: legitimate trade-off prose can match."""
    ran_diagnostics = any(e.entry_id.startswith("portfolio:") for e in ledger.entries)
    if not ran_diagnostics:
        return CriticCheck(
            check_id="diagnostic_framing",
            passed=True,
            severity="warning",
            details="no portfolio diagnostics were run; framing check not applicable",
        )
    hits = [
        m.group(0) for prose in memo.all_prose() for m in _IMPERATIVE_ALLOCATION.finditer(prose)
    ]
    return CriticCheck(
        check_id="diagnostic_framing",
        passed=not hits,
        severity="warning",
        details=(
            "allocation diagnostics framed comparatively"
            if not hits
            else "memo phrases allocation diagnostics as instructions"
        ),
        evidence=hits,
    )


def check_certainty_not_overstated(memo: PlanningMemo) -> CriticCheck:
    hits = [
        m.group(0)
        for prose in memo.all_prose()
        for m in _CERTAINTY_PATTERN.finditer(prose)
        if not _is_negated(prose, m)
    ]
    return CriticCheck(
        check_id="certainty_not_overstated",
        passed=not hits,
        severity="blocker",
        details=(
            "no absolute-certainty language detected"
            if not hits
            else "memo uses absolute-certainty language"
        ),
        evidence=hits,
    )
