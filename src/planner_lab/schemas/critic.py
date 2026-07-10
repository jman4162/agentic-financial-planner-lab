"""Critic check and report types. A memo is emitted only when the report approves it."""

import datetime
from typing import Literal

from pydantic import BaseModel

CheckId = Literal[
    "numbers_traceable",
    "citations_present",
    "no_securities_advice",
    "nominal_real_consistent",
    "certainty_not_overstated",
    "missing_inputs_flagged",
    "assumptions_disclosed",
    "disclaimer_present",
    "diagnostic_framing",
]

Severity = Literal["blocker", "warning"]


class CriticCheck(BaseModel):
    check_id: CheckId
    passed: bool
    severity: Severity
    details: str
    evidence: list[str] = []


class CriticReport(BaseModel):
    checks: list[CriticCheck]
    reviewed_at: datetime.datetime

    @property
    def approved(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "blocker")

    def blockers(self) -> list[CriticCheck]:
        return [c for c in self.checks if c.severity == "blocker" and not c.passed]

    def warnings(self) -> list[CriticCheck]:
        return [c for c in self.checks if c.severity == "warning" and not c.passed]
