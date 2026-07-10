"""End-to-end retirement-readiness analysis with deterministic control flow.

The LLM appears at exactly two points: drafting the memo and the qualitative
critic pass. Everything else — assumptions, calculators, simulation, checks —
is plain Python, so the flow is testable with a stubbed model and no network.
"""

from collections.abc import Callable
from typing import NamedTuple

from rich.console import Console
from rich.table import Table
from strands.models.model import Model

from planner_lab import calculators
from planner_lab.adapters import get_simulator
from planner_lab.agents.llm_critic import make_llm_checks
from planner_lab.agents.memo_writer import write_memo
from planner_lab.critic import run_critic
from planner_lab.memo.render import MemoRejectedError
from planner_lab.schemas.assumptions import AssumptionsBundle, default_assumptions
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticReport
from planner_lab.schemas.memo import PlanningMemo
from planner_lab.schemas.results import ComputationLedger

ConfirmFn = Callable[[str], bool]

_BASE_STRESS_SCENARIOS = ("crash", "sequence_risk")


class AnalysisResult(NamedTuple):
    memo: PlanningMemo
    report: CriticReport
    ledger: ComputationLedger


class AssumptionsNotConfirmedError(RuntimeError):
    pass


def assumptions_table(bundle: AssumptionsBundle) -> Table:
    table = Table(title="Assumptions (all rates real, after inflation)")
    table.add_column("Set")
    table.add_column("Real return")
    table.add_column("Volatility")
    table.add_column("Inflation")
    table.add_column("Withdrawal rate")
    table.add_column("Plan end age")
    for aset in bundle.all_sets():
        table.add_row(
            aset.label,
            f"{aset.expected_return_real:.1%}",
            f"{aset.return_volatility:.0%}",
            f"{aset.inflation:.1%}",
            f"{aset.safe_withdrawal_rate:.1%}",
            str(aset.plan_end_age),
        )
    return table


def surface_assumptions(case: CaseFile, confirm: ConfirmFn, console: Console | None = None) -> None:
    """Show the assumption sets and require explicit confirmation before any
    simulation or memo work. Flips bundle.surfaced on approval."""
    if case.assumptions is None:
        case.assumptions = default_assumptions()
    (console or Console()).print(assumptions_table(case.assumptions))
    if not confirm("Proceed with these assumptions?"):
        raise AssumptionsNotConfirmedError("user did not confirm the assumption sets")
    case.assumptions.surfaced = True


def _run_calculators(case: CaseFile, ledger: ComputationLedger) -> None:
    assert case.assumptions is not None
    portfolio = case.balance_sheet.investable_assets
    spending = case.retirement_spending_target()
    savings = case.cash_flow.effective_savings()
    if savings is None:
        savings = case.balance_sheet.annual_contributions

    for aset in case.assumptions.all_sets():
        if spending is None:
            continue
        rate = aset.safe_withdrawal_rate
        fr = calculators.funded_ratio(portfolio, spending, rate)
        ledger.add(
            "funded_ratio",
            {"portfolio_value": portfolio, "annual_spending": spending, "withdrawal_rate": rate},
            fr,
            assumptions_label=aset.label,
        )
        years = calculators.years_to_fi(
            portfolio, savings, spending, aset.expected_return_real, rate
        )
        if years != float("inf"):
            ledger.add(
                "years_to_fi",
                {
                    "current_portfolio": portfolio,
                    "annual_savings": savings,
                    "annual_spending": spending,
                    "real_return": aset.expected_return_real,
                    "withdrawal_rate": rate,
                },
                {"years_to_fi": years},
                assumptions_label=aset.label,
            )
        ledger.add(
            "sustainable_spending",
            {"portfolio_value": portfolio, "withdrawal_rate": rate},
            {"sustainable_spending": calculators.sustainable_spending(portfolio, rate)},
            assumptions_label=aset.label,
        )


def _run_simulations(case: CaseFile, ledger: ComputationLedger, *, n_paths: int, seed: int) -> None:
    assert case.assumptions is not None
    simulator = get_simulator()
    for aset in case.assumptions.all_sets():
        stress = _BASE_STRESS_SCENARIOS if aset.label == "base" else ()
        summary = simulator.simulate(
            case, aset, n_paths=n_paths, seed=seed, stress_scenarios=stress
        )
        outputs: dict[str, float | int | str] = {
            "success_probability": summary.success_probability,
            "n_paths": summary.n_paths,
            "seed": summary.seed,
        }
        for pct, value in summary.terminal_wealth_percentiles.items():
            outputs[f"terminal_wealth_{pct}"] = value
        for scenario, prob in summary.stress_results.items():
            outputs[f"stress_{scenario}_success_probability"] = prob
        ledger.add(
            "run_simulation",
            {
                "assumptions_label": aset.label,
                "n_paths": n_paths,
                "seed": seed,
                "stress_scenarios": list(stress),
            },
            outputs,
            assumptions_label=aset.label,
            adapter=simulator.name,
            kind="sim",
        )


def run_analysis(
    case: CaseFile,
    *,
    model: Model | None = None,
    simulate: bool = False,
    confirm: ConfirmFn | None = None,
    n_paths: int = 2000,
    seed: int = 42,
    console: Console | None = None,
) -> AnalysisResult:
    """Full flow: assumptions -> calculators -> optional simulation -> memo -> critic.

    `confirm` decides assumption approval; pass `lambda _: True` for
    non-interactive runs. One memo revision is attempted when the critic
    rejects; a second rejection raises MemoRejectedError.
    """
    if model is None:
        from planner_lab.agents.models import build_model

        model = build_model()
    if confirm is None:
        confirm = lambda _: True  # noqa: E731

    surface_assumptions(case, confirm, console)
    ledger = ComputationLedger(case_id=case.case_id)
    _run_calculators(case, ledger)
    if simulate:
        _run_simulations(case, ledger, n_paths=n_paths, seed=seed)

    llm_checks = make_llm_checks(model)
    memo = write_memo(case, ledger, model)
    report = run_critic(memo, ledger, case, llm_checks=llm_checks)
    if not report.approved:
        memo = write_memo(case, ledger, model, feedback=report)
        report = run_critic(memo, ledger, case, llm_checks=llm_checks)
        if not report.approved:
            raise MemoRejectedError(report)
    return AnalysisResult(memo, report, ledger)
