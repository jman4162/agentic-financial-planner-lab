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
from planner_lab.protocols import (
    DEFAULT_N_PATHS,
    DEFAULT_SEED,
    SPENDING_POLICIES,
    FinancialHealthMetric,
    PortfolioAnalyticsEngine,
    ResearchSource,
    SensitivityAnalyzer,
    SpendingPolicy,
)
from planner_lab.schemas.assumptions import AssumptionsBundle, default_assumptions
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.critic import CriticReport
from planner_lab.schemas.memo import PlanningMemo
from planner_lab.schemas.results import ComputationLedger, ResearchDocument

ConfirmFn = Callable[[str], bool]

_BASE_STRESS_SCENARIOS = ("crash", "sequence_risk")
_MAX_RESEARCH_DOCS = 2
_METHODOLOGY_QUERIES = ("safe withdrawal rate",)


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
    portfolio = case.balance_sheet.retirement_investable_assets
    spending = case.retirement_spending_target()
    savings = case.cash_flow.effective_savings()
    if savings is None:
        savings = case.balance_sheet.annual_contributions

    retirement_age = case.earliest_retirement_age()
    guaranteed_income = case.guaranteed_income_at_age(retirement_age)
    net_spending = case.net_retirement_spending(retirement_age)

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
        if guaranteed_income > 0 and net_spending is not None and net_spending > 0:
            fr_net = calculators.funded_ratio(portfolio, net_spending, rate)
            ledger.add(
                "funded_ratio_net_of_income",
                {
                    "portfolio_value": portfolio,
                    "net_annual_spending": net_spending,
                    "withdrawal_rate": rate,
                },
                fr_net,
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

    if spending is not None and guaranteed_income > 0 and net_spending is not None:
        ledger.add(
            "net_retirement_spending",
            {"gross_spending": spending, "at_age": retirement_age},
            {
                "guaranteed_income": guaranteed_income,
                "net_spending": net_spending,
                "gross_spending": spending,
            },
        )


def _run_simulations(
    case: CaseFile,
    ledger: ComputationLedger,
    *,
    n_paths: int,
    seed: int,
    spending_policy: SpendingPolicy = "constant_real",
) -> None:
    assert case.assumptions is not None
    simulator = get_simulator()
    for aset in case.assumptions.all_sets():
        stress = _BASE_STRESS_SCENARIOS if aset.label == "base" else ()
        summary = simulator.simulate(
            case,
            aset,
            n_paths=n_paths,
            seed=seed,
            stress_scenarios=stress,
            spending_policy=spending_policy,
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
                "spending_policy": spending_policy,
            },
            outputs,
            assumptions_label=aset.label,
            adapter=simulator.name,
            kind="sim",
        )


def _run_policy_comparison(
    case: CaseFile, ledger: ComputationLedger, *, n_paths: int, seed: int
) -> None:
    """Simulate the base set once per spending policy. Comparison only: dynamic
    policies trade income stability for portfolio survival, and the memo should
    present that trade-off rather than pick a winner."""
    assert case.assumptions is not None
    simulator = get_simulator()
    base = case.assumptions.base
    for policy in SPENDING_POLICIES:
        summary = simulator.simulate(case, base, n_paths=n_paths, seed=seed, spending_policy=policy)
        ledger.add(
            "spending_policy_comparison",
            {"spending_policy": policy, "n_paths": n_paths, "seed": seed},
            {
                "spending_policy": policy,
                "success_probability": summary.success_probability,
                "terminal_wealth_p50": summary.terminal_wealth_percentiles.get("p50", 0.0),
            },
            assumptions_label=base.label,
            adapter=simulator.name,
            kind="sim",
        )


def _run_sensitivity(case: CaseFile, ledger: ComputationLedger, *, n_paths: int, seed: int) -> None:
    assert case.assumptions is not None
    simulator = get_simulator()
    if not isinstance(simulator, SensitivityAnalyzer):
        raise RuntimeError(f"simulator {simulator.name!r} does not support sensitivity analysis")
    impacts = simulator.analyze_sensitivity(case, case.assumptions.base, n_paths=n_paths, seed=seed)
    ledger.add(
        "sensitivity_analysis",
        {"perturbation": "10% per parameter", "n_paths": n_paths, "seed": seed},
        {f"impact_{name}": impact for name, impact in impacts.items()},
        assumptions_label="base",
        adapter=simulator.name,
        kind="sim",
    )


def _run_health_metric(
    case: CaseFile, ledger: ComputationLedger, metric: FinancialHealthMetric
) -> None:
    """Compute the health metric under every assumption set (closed-form, cheap)."""
    assert case.assumptions is not None
    current_age = case.household.persons[0].age_in(case.created.year)
    for aset in case.assumptions.all_sets():
        result = metric.compute(case, aset)
        ledger.add(
            "compute_health_metric",
            {
                "metric": result.metric_name,
                "base_inflation": aset.inflation,
                "planning_horizon": max(aset.plan_end_age - current_age, 1),
            },
            {
                result.metric_name: result.value,
                **result.components,
                "interpretation": result.interpretation or "",
            },
            assumptions_label=aset.label,
            adapter=metric.name,
            kind="metric",
        )


def _run_portfolio_diagnostics(
    case: CaseFile, ledger: ComputationLedger, engine: PortfolioAnalyticsEngine
) -> None:
    """One diagnostic benchmark under the base set only; three alphas would
    invite the memo to average them."""
    assert case.assumptions is not None
    aset = case.assumptions.base
    diagnostics = engine.analyze(case, aset)
    ledger.add(
        "portfolio_diagnostics",
        {
            "engine": diagnostics.engine_name,
            "mu": aset.expected_return_real,
            "sigma": aset.return_volatility,
        },
        {**diagnostics.findings, "notes": diagnostics.notes},
        assumptions_label=aset.label,
        adapter=engine.name,
        kind="portfolio",
    )


# SSA-style claiming factors relative to a full retirement age of 67; v1
# approximation for the comparison table, documented in the memo methodology.
_SS_CLAIMING_FACTORS = {
    62: 0.70,
    63: 0.75,
    64: 0.80,
    65: 0.867,
    66: 0.933,
    67: 1.0,
    68: 1.08,
    69: 1.16,
    70: 1.24,
}
_SS_COMPARISON_AGES = (62, 67, 70)


def _run_ss_comparison(
    case: CaseFile, ledger: ComputationLedger, *, n_paths: int, seed: int
) -> None:
    """Simulate the base assumption set once per Social Security claiming age,
    scaling every SS stream's benefit by the SSA-style factor relative to its
    stated start age. Comparison only; the memo must not advise a claiming age."""
    assert case.assumptions is not None
    ss_streams = [s for s in case.income_streams if s.kind == "social_security"]
    if not ss_streams:
        return
    simulator = get_simulator()
    base = case.assumptions.base
    for claiming_age in _SS_COMPARISON_AGES:
        variant = case.model_copy(deep=True)
        scaled_total_monthly = 0.0
        for stream in variant.income_streams:
            if stream.kind != "social_security":
                continue
            stated = min(max(stream.start_age, 62), 70)
            factor = _SS_CLAIMING_FACTORS[claiming_age] / _SS_CLAIMING_FACTORS[stated]
            stream.monthly_amount = stream.monthly_amount * factor
            stream.start_age = claiming_age
            scaled_total_monthly += stream.monthly_amount
        summary = simulator.simulate(variant, base, n_paths=n_paths, seed=seed)
        ledger.add(
            "ss_claiming_comparison",
            {"claiming_age": claiming_age, "n_paths": n_paths, "seed": seed},
            {
                "claiming_age": claiming_age,
                "monthly_benefit_total": round(scaled_total_monthly, 2),
                "success_probability": summary.success_probability,
            },
            assumptions_label=base.label,
            adapter=simulator.name,
            kind="sim",
        )


def _run_research(
    case: CaseFile,
    ledger: ComputationLedger,
    source: ResearchSource,
    *,
    max_docs: int = _MAX_RESEARCH_DOCS,
) -> list[ResearchDocument]:
    """Deterministic research plan: search the case question plus fixed
    methodology queries, fetch the top distinct hits, record everything."""
    refs: list[str] = []
    titles: dict[str, str] = {}
    for query in (case.question, *_METHODOLOGY_QUERIES):
        hits = source.search(query, limit=5)
        ledger.add(
            "search_research",
            {"query": query, "limit": 5},
            {"refs": [h.ref for h in hits]},
            adapter=source.name,
            kind="research",
        )
        for hit in hits[:1]:
            if hit.ref not in refs:
                refs.append(hit.ref)
                titles[hit.ref] = hit.title
    docs: list[ResearchDocument] = []
    for ref in refs[:max_docs]:
        doc = source.fetch(ref)
        ledger.add(
            "fetch_research",
            {"ref": ref},
            {"ref": doc.ref, "title": doc.title, "url": doc.url or ""},
            adapter=source.name,
            kind="research",
        )
        docs.append(doc)
    return docs


def run_analysis(
    case: CaseFile,
    *,
    model: Model | None = None,
    simulate: bool = False,
    spending_policy: SpendingPolicy = "constant_real",
    compare_spending_policies: bool = False,
    sensitivity: bool = False,
    ss_comparison: bool = False,
    research_source: ResearchSource | None = None,
    health_metric: FinancialHealthMetric | None = None,
    portfolio_engine: PortfolioAnalyticsEngine | None = None,
    confirm: ConfirmFn | None = None,
    n_paths: int = DEFAULT_N_PATHS,
    seed: int = DEFAULT_SEED,
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
        _run_simulations(case, ledger, n_paths=n_paths, seed=seed, spending_policy=spending_policy)
    if compare_spending_policies:
        _run_policy_comparison(case, ledger, n_paths=n_paths, seed=seed)
    if sensitivity:
        _run_sensitivity(case, ledger, n_paths=n_paths, seed=seed)
    if ss_comparison:
        _run_ss_comparison(case, ledger, n_paths=n_paths, seed=seed)
    if health_metric is not None:
        _run_health_metric(case, ledger, health_metric)
    if portfolio_engine is not None:
        _run_portfolio_diagnostics(case, ledger, portfolio_engine)
    docs: list[ResearchDocument] = []
    source_name = "research"
    if research_source is not None:
        docs = _run_research(case, ledger, research_source)
        source_name = research_source.name

    llm_checks = make_llm_checks(model)
    memo = write_memo(case, ledger, model, research=docs, research_source_name=source_name)
    report = run_critic(memo, ledger, case, llm_checks=llm_checks)
    if not report.approved:
        memo = write_memo(
            case, ledger, model, feedback=report, research=docs, research_source_name=source_name
        )
        report = run_critic(memo, ledger, case, llm_checks=llm_checks)
        if not report.approved:
            raise MemoRejectedError(report)
    return AnalysisResult(memo, report, ledger)
