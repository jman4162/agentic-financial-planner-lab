"""Assemble the critic report from deterministic checks plus optional LLM findings."""

import datetime
from collections.abc import Callable

from planner_lab.critic import checks
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticCheck, CriticReport
from planner_lab.schemas.memo import PlanningMemo
from planner_lab.schemas.results import ComputationLedger

LLMChecks = Callable[[PlanningMemo], list[CriticCheck]]


def run_critic(
    memo: PlanningMemo,
    ledger: ComputationLedger,
    case: CaseFile,
    llm_checks: LLMChecks | None = None,
) -> CriticReport:
    """Run every deterministic check, then merge optional LLM critic findings.

    When the LLM critic reports on a check_id the deterministic pass also covers,
    both results are kept: a failure from either fails the combined view because
    CriticReport.approved requires every blocker to pass.
    """
    results: list[CriticCheck] = [
        checks.check_numbers_traceable(memo, ledger, case),
        checks.check_no_securities_advice(memo),
        checks.check_disclaimer_present(memo),
        checks.check_assumptions_disclosed(memo, case),
        checks.check_missing_inputs_flagged(memo, case),
        checks.check_citations_present(memo, ledger),
        checks.check_nominal_real_consistent(memo, ledger),
        checks.check_certainty_not_overstated(memo),
    ]
    if llm_checks is not None:
        results.extend(llm_checks(memo))
    return CriticReport(checks=results, reviewed_at=datetime.datetime.now(datetime.UTC))
