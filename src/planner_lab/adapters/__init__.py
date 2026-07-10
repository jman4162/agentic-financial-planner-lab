"""Lazy loaders for optional integrations.

Each loader imports its adapter only on request and raises AdapterUnavailableError
with the exact extra to install when the dependency is missing. Core code calls
these loaders; it never imports adapter modules directly.
"""

from planner_lab.protocols import (
    FinancialHealthMetric,
    PortfolioAnalyticsEngine,
    ResearchSource,
    ScenarioSimulator,
)


class AdapterUnavailableError(RuntimeError):
    pass


def get_simulator(name: str = "montecarlo") -> ScenarioSimulator:
    if name == "montecarlo":
        try:
            from planner_lab.adapters.monteplan.simulator import MontePlanSimulator
        except ImportError as e:
            raise AdapterUnavailableError(
                "Monte Carlo simulation requires the 'planning' extra: "
                "uv sync --extra planning (needs Python >= 3.11)"
            ) from e
        return MontePlanSimulator()
    raise AdapterUnavailableError(f"unknown simulator {name!r}")


def get_research_source(url: str) -> ResearchSource:
    raise AdapterUnavailableError(
        "Research sources arrive in a later phase; none is available yet."
    )


def get_health_metric(name: str = "funded") -> FinancialHealthMetric:
    raise AdapterUnavailableError(
        "Financial-health metrics arrive in a later phase; none is available yet."
    )


def get_portfolio_engine(name: str = "lifecycle") -> PortfolioAnalyticsEngine:
    raise AdapterUnavailableError(
        "Portfolio analytics engines arrive in a later phase; none is available yet."
    )
