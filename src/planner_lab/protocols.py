"""Generic interfaces every integration implements.

Core code depends only on these Protocols; concrete implementations live under
`planner_lab.adapters` and are loaded lazily so the core runs with none installed.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import (
    CashflowImportResult,
    MetricResult,
    PortfolioDiagnostics,
    ResearchDocument,
    ResearchHit,
    SimulationSummary,
)


DEFAULT_N_PATHS = 2000
DEFAULT_SEED = 42

SpendingPolicy = Literal[
    "constant_real", "guardrails", "vpw", "floor_ceiling", "percent_of_portfolio"
]
SPENDING_POLICIES: tuple[SpendingPolicy, ...] = (
    "constant_real",
    "guardrails",
    "vpw",
    "floor_ceiling",
    "percent_of_portfolio",
)


@runtime_checkable
class ScenarioSimulator(Protocol):
    name: str

    def simulate(
        self,
        case: CaseFile,
        assumptions: AssumptionSet,
        *,
        n_paths: int = DEFAULT_N_PATHS,
        seed: int = DEFAULT_SEED,
        stress_scenarios: Sequence[str] = (),
        spending_policy: SpendingPolicy = "constant_real",
    ) -> SimulationSummary: ...


@runtime_checkable
class SensitivityAnalyzer(Protocol):
    """Optional capability: which assumption moves the outcome most."""

    name: str

    def analyze_sensitivity(
        self,
        case: CaseFile,
        assumptions: AssumptionSet,
        *,
        n_paths: int = DEFAULT_N_PATHS,
        seed: int = DEFAULT_SEED,
    ) -> dict[str, float]: ...


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

    def import_cashflow(self, path: Path) -> CashflowImportResult: ...


@runtime_checkable
class PortfolioAnalyticsEngine(Protocol):
    name: str

    def analyze(self, case: CaseFile, assumptions: AssumptionSet) -> PortfolioDiagnostics: ...
