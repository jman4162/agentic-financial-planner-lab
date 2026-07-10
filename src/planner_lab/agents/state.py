"""Shared mutable state for one interactive planning session."""

from dataclasses import dataclass, field

from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import ComputationLedger


@dataclass
class RunState:
    case: CaseFile
    ledger: ComputationLedger
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    research_url: str | None = None

    @property
    def assumptions_surfaced(self) -> bool:
        return self.case.assumptions is not None and self.case.assumptions.surfaced
