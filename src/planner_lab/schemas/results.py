"""Calculator, simulation, and research result types, and the traceability ledger.

Every number that appears in a memo must resolve through `ComputationLedger.resolve`
to either a ledger entry output or a case-file field.
"""

import datetime
from typing import Any

from pydantic import BaseModel, Field

from planner_lab.schemas.case_file import CaseFile, CashFlow


class LedgerEntry(BaseModel):
    entry_id: str
    tool_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    assumptions_label: str | None = None
    adapter: str | None = None


class ComputationLedger(BaseModel):
    case_id: str
    entries: list[LedgerEntry] = []

    def add(
        self,
        tool_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        *,
        assumptions_label: str | None = None,
        adapter: str | None = None,
        kind: str = "calc",
    ) -> str:
        entry_id = f"{kind}:{tool_name}:{len(self.entries) + 1:04d}"
        self.entries.append(
            LedgerEntry(
                entry_id=entry_id,
                tool_name=tool_name,
                inputs=inputs,
                outputs=outputs,
                assumptions_label=assumptions_label,
                adapter=adapter,
            )
        )
        return entry_id

    def get(self, entry_id: str) -> LedgerEntry | None:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def resolve(self, source_id: str, case: CaseFile) -> float | None:
        """Resolve a memo source_id to its numeric value, or None if unresolvable.

        Schemes:
          "ledger:<entry_id>#<output_key>" — an output of a recorded computation
          "case:<dotted.path>"             — a case-file field (list indices allowed)
        """
        if source_id.startswith("ledger:"):
            ref = source_id.removeprefix("ledger:")
            entry_id, sep, key = ref.partition("#")
            entry = self.get(entry_id)
            if entry is None:
                return None
            if not sep:
                # No output key given: unambiguous only when the entry has
                # exactly one numeric output.
                numeric = [v for v in entry.outputs.values() if isinstance(v, (int, float))]
                return float(numeric[0]) if len(numeric) == 1 else None
            value = entry.outputs.get(key)
            return float(value) if isinstance(value, (int, float)) else None
        if source_id.startswith("case:"):
            return _resolve_case_path(case, source_id.removeprefix("case:"))
        if ":" not in source_id and "." in source_id:
            # Models sometimes drop the scheme on case paths.
            return _resolve_case_path(case, source_id)
        return None


def _resolve_case_path(case: CaseFile, dotted: str) -> float | None:
    # Accept bracket indexing ("persons[0].age") as well as dotted ("persons.0.age").
    dotted = dotted.replace("[", ".").replace("]", "")
    node: Any = case
    for part in dotted.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(node, dict):
            if part not in node:
                return None
            node = node[part]
        else:
            if not hasattr(node, part):
                return None
            node = getattr(node, part)
        if node is None:
            return None
    return float(node) if isinstance(node, (int, float)) else None


class SimulationSummary(BaseModel):
    """What any ScenarioSimulator must return."""

    success_probability: float = Field(ge=0, le=1)
    terminal_wealth_percentiles: dict[str, float]
    n_paths: int = Field(gt=0)
    seed: int
    stress_results: dict[str, float] = {}
    assumptions_label: str
    engine_metadata: dict[str, str] = {}


class MetricResult(BaseModel):
    """What any FinancialHealthMetric must return."""

    metric_name: str
    value: float
    components: dict[str, float] = {}
    interpretation: str | None = None


class PortfolioDiagnostics(BaseModel):
    """What any PortfolioAnalyticsEngine must return. Diagnostics, never advice."""

    engine_name: str
    findings: dict[str, float] = {}
    notes: list[str] = []


class CashflowImportResult(BaseModel):
    """What any CashflowImporter must return: the derived cash flow plus the
    provenance (window, exclusions, warnings) that makes it auditable."""

    cash_flow: CashFlow
    window_start: datetime.date
    window_end: datetime.date
    months_covered: int = Field(gt=0)
    total_inflow: float
    total_outflow: float
    excluded_transfer_amount: float = 0.0
    warnings: list[str] = []


class ResearchHit(BaseModel):
    ref: str
    title: str
    url: str | None = None


class ResearchDocument(BaseModel):
    ref: str
    title: str
    text: str
    url: str | None = None
    metadata: dict[str, str] = {}
