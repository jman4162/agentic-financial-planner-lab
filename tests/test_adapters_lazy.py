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

    def test_unknown_names_raise(self) -> None:
        with pytest.raises(AdapterUnavailableError):
            get_health_metric("nonexistent")
        with pytest.raises(AdapterUnavailableError):
            get_portfolio_engine("nonexistent")

    def test_health_metric_error_names_extra_when_missing(self) -> None:
        try:
            metric = get_health_metric()
        except AdapterUnavailableError as e:
            assert "planning" in str(e)
        else:
            from planner_lab.protocols import FinancialHealthMetric

            assert isinstance(metric, FinancialHealthMetric)

    def test_portfolio_engine_error_names_extra_when_missing(self) -> None:
        try:
            engine = get_portfolio_engine()
        except AdapterUnavailableError as e:
            assert "portfolio" in str(e)
        else:
            from planner_lab.protocols import PortfolioAnalyticsEngine

            assert isinstance(engine, PortfolioAnalyticsEngine)

    def test_research_source_error_names_extra_when_missing(self) -> None:
        try:
            source = get_research_source("http://unused.invalid/mcp")
        except AdapterUnavailableError as e:
            assert "mcp" in str(e)
        else:
            from planner_lab.protocols import ResearchSource

            assert isinstance(source, ResearchSource)

    def test_simulator_error_names_extra_when_missing(self) -> None:
        try:
            simulator = get_simulator()
        except AdapterUnavailableError as e:
            assert "planning" in str(e)
        else:
            # monteplan installed: the adapter satisfies the protocol.
            from planner_lab.protocols import ScenarioSimulator

            assert isinstance(simulator, ScenarioSimulator)
