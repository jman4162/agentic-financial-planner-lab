import pytest

from planner_lab.adapters import (
    AdapterUnavailableError,
    get_health_metric,
    get_portfolio_engine,
    get_research_source,
    get_simulator,
)


class TestLazyLoaders:
    def test_unknown_simulator_names_error(self) -> None:
        with pytest.raises(AdapterUnavailableError):
            get_simulator("nonexistent")

    def test_placeholder_loaders_raise(self) -> None:
        with pytest.raises(AdapterUnavailableError):
            get_research_source("http://localhost/mcp")
        with pytest.raises(AdapterUnavailableError):
            get_health_metric()
        with pytest.raises(AdapterUnavailableError):
            get_portfolio_engine()

    def test_simulator_error_names_extra_when_missing(self) -> None:
        try:
            simulator = get_simulator()
        except AdapterUnavailableError as e:
            assert "planning" in str(e)
        else:
            # monteplan installed: the adapter satisfies the protocol.
            from planner_lab.protocols import ScenarioSimulator

            assert isinstance(simulator, ScenarioSimulator)
