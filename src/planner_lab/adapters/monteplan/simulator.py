"""ScenarioSimulator adapter for the monteplan Monte Carlo engine.

Semantics note (verified against monteplan 0.6.0 source): monteplan's
`expected_annual_returns` are nominal and inflation is modeled separately, so
this adapter converts the case's real return assumption to nominal via the
Fisher relation. Spending uses monteplan's "constant_real" policy, which takes
today's dollars and inflates them along each path.

Account-type mapping (monteplan supports taxable/traditional/roth only):
cash and education and other map to taxable; hsa maps to roth.
"""

from collections.abc import Sequence

from monteplan import (
    AccountConfig,
    MarketAssumptions,
    PlanConfig,
    PolicyBundle,
    SimulationConfig,
    SpendingPolicyConfig,
    simulate,
)
from monteplan.config.schema import AssetClass, StressScenario

from planner_lab.calculators.conversions import real_to_nominal_rate
from planner_lab.protocols import DEFAULT_N_PATHS, DEFAULT_SEED
from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import SimulationSummary

_ACCOUNT_TYPE_MAP = {
    "taxable": "taxable",
    "traditional": "traditional",
    "roth": "roth",
    "cash": "taxable",
    "hsa": "roth",
    "education": "taxable",
    "other": "taxable",
}

# scenario_type -> (duration_months,) applied at retirement age.
_STRESS_DURATIONS = {
    "crash": 12,
    "lost_decade": 120,
    "high_inflation": 60,
    "sequence_risk": 60,
}


class MontePlanSimulator:
    name = "montecarlo"

    def simulate(
        self,
        case: CaseFile,
        assumptions: AssumptionSet,
        *,
        n_paths: int = DEFAULT_N_PATHS,
        seed: int = DEFAULT_SEED,
        stress_scenarios: Sequence[str] = (),
    ) -> SimulationSummary:
        plan = _build_plan(case, assumptions)
        market = _build_market(case, assumptions)
        policies = PolicyBundle(
            spending=SpendingPolicyConfig(
                policy_type="constant_real",
                withdrawal_rate=assumptions.safe_withdrawal_rate,
            )
        )

        base = simulate(plan, market, policies, SimulationConfig(n_paths=n_paths, seed=seed))

        stress_results: dict[str, float] = {}
        for scenario_name in stress_scenarios:
            duration = _STRESS_DURATIONS.get(scenario_name)
            if duration is None:
                raise ValueError(
                    f"unknown stress scenario {scenario_name!r}; "
                    f"choose from {sorted(_STRESS_DURATIONS)}"
                )
            stressed_config = SimulationConfig(
                n_paths=n_paths,
                seed=seed,
                stress_scenarios=[
                    StressScenario(
                        name=scenario_name,
                        scenario_type=scenario_name,
                        start_age=float(plan.retirement_age),
                        duration_months=duration,
                    )
                ],
            )
            stressed = simulate(plan, market, policies, stressed_config)
            stress_results[scenario_name] = stressed.success_probability

        return SimulationSummary(
            success_probability=base.success_probability,
            terminal_wealth_percentiles=dict(base.terminal_wealth_percentiles),
            n_paths=base.n_paths,
            seed=base.seed,
            stress_results=stress_results,
            assumptions_label=assumptions.label,
            engine_metadata={
                "engine": "monteplan",
                "engine_version": base.engine_version,
                "config_hash": base.config_hash,
                "return_basis": "nominal returns derived from real assumption via Fisher",
            },
        )


def _retirement_spending(case: CaseFile) -> float:
    target = case.retirement_spending_target()
    if target is None:
        raise ValueError(
            "case file has no retirement spending target: set "
            "goals[kind=retirement].annual_amount_today or cash_flow.annual_expenses"
        )
    return target


def _build_plan(case: CaseFile, assumptions: AssumptionSet) -> PlanConfig:
    person = case.household.persons[0]
    current_age = person.age_in(case.created.year)
    retirement_age = person.planned_retirement_age or 65
    if retirement_age <= current_age:
        retirement_age = current_age + 1

    accounts = [
        AccountConfig(
            account_type=_ACCOUNT_TYPE_MAP[account.account_type],
            balance=account.balance,
            annual_contribution=account.annual_contribution,
        )
        for account in case.balance_sheet.accounts
    ]
    take_home = case.cash_flow.annual_take_home or 0.0
    return PlanConfig(
        current_age=current_age,
        retirement_age=retirement_age,
        end_age=assumptions.plan_end_age,
        accounts=accounts,
        monthly_income=take_home / 12,
        monthly_spending=_retirement_spending(case) / 12,
    )


def _build_market(case: CaseFile, assumptions: AssumptionSet) -> MarketAssumptions:
    nominal_return = real_to_nominal_rate(assumptions.expected_return_real, assumptions.inflation)
    expense_ratio = 0.0
    if case.portfolio is not None and case.portfolio.weighted_expense_ratio is not None:
        expense_ratio = case.portfolio.weighted_expense_ratio
    return MarketAssumptions(
        assets=[AssetClass(name="Blended portfolio", weight=1.0)],
        expected_annual_returns=[nominal_return],
        annual_volatilities=[assumptions.return_volatility],
        correlation_matrix=[[1.0]],
        inflation_mean=assumptions.inflation,
        inflation_vol=0.01,
        expense_ratio=expense_ratio,
    )
