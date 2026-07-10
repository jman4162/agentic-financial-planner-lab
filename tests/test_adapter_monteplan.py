import importlib.util

import pytest

_has_monteplan = importlib.util.find_spec("monteplan") is not None

pytestmark = pytest.mark.skipif(not _has_monteplan, reason="monteplan not installed")


class TestMontePlanSimulator:
    def _simulate(self, **kwargs: object) -> object:
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator
        from tests.support.fixtures import make_case

        case = make_case()
        assert case.assumptions is not None
        return MontePlanSimulator().simulate(
            case,
            case.assumptions.base,
            n_paths=500,
            seed=7,
            **kwargs,  # type: ignore[arg-type]
        )

    def test_satisfies_protocol(self) -> None:
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator
        from planner_lab.protocols import ScenarioSimulator

        assert isinstance(MontePlanSimulator(), ScenarioSimulator)

    def test_returns_summary_with_percentiles(self) -> None:
        from planner_lab.schemas.results import SimulationSummary

        summary = self._simulate()
        assert isinstance(summary, SimulationSummary)
        assert 0 <= summary.success_probability <= 1
        assert {"p5", "p25", "p50", "p75", "p95"} <= set(summary.terminal_wealth_percentiles)
        assert summary.assumptions_label == "base"
        assert summary.seed == 7

    def test_deterministic_under_fixed_seed(self) -> None:
        first = self._simulate()
        second = self._simulate()
        assert first == second

    def test_stress_scenarios_reduce_or_match_success(self) -> None:
        from planner_lab.schemas.results import SimulationSummary

        summary = self._simulate(stress_scenarios=("crash",))
        assert isinstance(summary, SimulationSummary)
        assert "crash" in summary.stress_results
        assert summary.stress_results["crash"] <= summary.success_probability + 0.05

    def test_unknown_stress_scenario_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown stress scenario"):
            self._simulate(stress_scenarios=("meteor",))

    def test_missing_spending_target_rejected(self) -> None:
        from planner_lab.adapters.monteplan.simulator import MontePlanSimulator
        from tests.support.fixtures import make_case

        case = make_case()
        case.goals[0].annual_amount_today = None
        case.cash_flow.annual_expenses = None
        assert case.assumptions is not None
        with pytest.raises(ValueError, match="retirement spending target"):
            MontePlanSimulator().simulate(case, case.assumptions.base, n_paths=100, seed=1)

    def test_nominal_conversion_recorded(self) -> None:
        from planner_lab.schemas.results import SimulationSummary

        summary = self._simulate()
        assert isinstance(summary, SimulationSummary)
        assert "nominal" in summary.engine_metadata["return_basis"]
