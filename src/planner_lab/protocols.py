"""Generic interfaces every integration implements.

Core code depends only on these Protocols; concrete implementations live under
`planner_lab.adapters` and are loaded lazily so the core runs with none installed.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile, CashFlow
from planner_lab.schemas.results import (
    MetricResult,
    PortfolioDiagnostics,
    ResearchDocument,
    ResearchHit,
    SimulationSummary,
)


@runtime_checkable
class ScenarioSimulator(Protocol):
    name: str

    def simulate(
        self,
        case: CaseFile,
        assumptions: AssumptionSet,
        *,
        n_paths: int = 5000,
        seed: int = 42,
        stress_scenarios: Sequence[str] = (),
    ) -> SimulationSummary: ...


@runtime_checkable
class ResearchSource(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 5) -> list[ResearchHit]: ...

    def fetch(self, ref: str) -> ResearchDocument: ...


@runtime_checkable
class FinancialHealthMetric(Protocol):
    name: str

    def compute(self, case: CaseFile, assumptions: AssumptionSet) -> MetricResult: ...


@runtime_checkable
class CashflowImporter(Protocol):
    name: str

    def import_cashflow(self, path: Path) -> CashFlow: ...


@runtime_checkable
class PortfolioAnalyticsEngine(Protocol):
    name: str

    def analyze(self, case: CaseFile, assumptions: AssumptionSet) -> PortfolioDiagnostics: ...
