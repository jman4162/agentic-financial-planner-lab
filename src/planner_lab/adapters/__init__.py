"""Lazy loaders for optional integrations.

Each loader imports its adapter only on request and raises AdapterUnavailableError
with the exact extra to install when the dependency is missing. Core code calls
these loaders; it never imports adapter modules directly.
"""

from planner_lab.protocols import (
    CashflowImporter,
    FinancialHealthMetric,
    PortfolioAnalyticsEngine,
    ResearchSource,
    ScenarioSimulator,
)


class AdapterUnavailableError(RuntimeError):
    pass


def get_cashflow_importer(fmt: str = "generic") -> CashflowImporter:
    from planner_lab.adapters.csv_import.importer import CsvCashflowImporter
    from planner_lab.adapters.csv_import.mapping import PRESETS

    if fmt not in PRESETS:
        raise AdapterUnavailableError(f"unknown CSV format {fmt!r}; choose from {sorted(PRESETS)}")
    return CsvCashflowImporter(PRESETS[fmt])


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
    try:
        from planner_lab.adapters.mcp_research.source import MCPResearchSource
    except ImportError as e:
        raise AdapterUnavailableError(
            "Research sources require the 'mcp' extra: uv sync --extra mcp"
        ) from e
    return MCPResearchSource(url)


def get_health_metric(name: str = "funded") -> FinancialHealthMetric:
    if name == "funded":
        try:
            from planner_lab.adapters.fundedness_metric.metric import FundednessMetric
        except ImportError as e:
            raise AdapterUnavailableError(
                "Financial-health metrics require the 'planning' extra: uv sync --extra planning"
            ) from e
        return FundednessMetric()
    raise AdapterUnavailableError(f"unknown health metric {name!r}")


def get_portfolio_engine(name: str = "lifecycle") -> PortfolioAnalyticsEngine:
    if name == "lifecycle":
        try:
            from planner_lab.adapters.lifecycle.allocation import LifecycleAllocationEngine
        except ImportError as e:
            raise AdapterUnavailableError(
                "Portfolio analytics require the 'portfolio' extra: uv sync --extra portfolio"
            ) from e
        return LifecycleAllocationEngine()
    raise AdapterUnavailableError(f"unknown portfolio engine {name!r}")
