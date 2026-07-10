"""The planning memo: the workflow's only end product.

Every numeric claim is a TracedNumber whose source_id must resolve against the
computation ledger or the case file; the critic blocks memos that break this.
"""

from typing import Literal

from pydantic import BaseModel, Field

from planner_lab.schemas.assumptions import AssumptionsBundle

NumberUnit = Literal["usd", "ratio", "percent", "years", "age"]


class TracedNumber(BaseModel):
    label: str
    value: float
    unit: NumberUnit
    source_id: str = Field(description='"ledger:<entry_id>#<output_key>" or "case:<dotted.path>"')


class Citation(BaseModel):
    source_name: str
    ref: str
    title: str


class ScenarioNarrative(BaseModel):
    label: str
    narrative: str
    key_numbers: list[TracedNumber] = []


class PlanningMemo(BaseModel):
    case_id: str
    executive_summary: str
    inputs_summary: list[TracedNumber]
    missing_data: list[str]
    assumptions_table: AssumptionsBundle
    base_case: ScenarioNarrative
    stress_cases: list[ScenarioNarrative] = []
    risks: list[str]
    trade_offs: list[str]
    next_questions: list[str]
    methodology: str
    citations: list[Citation] = []
    disclaimer: str

    def all_traced_numbers(self) -> list[TracedNumber]:
        numbers = list(self.inputs_summary)
        numbers.extend(self.base_case.key_numbers)
        for scenario in self.stress_cases:
            numbers.extend(scenario.key_numbers)
        return numbers

    def all_prose(self) -> list[str]:
        """Every free-text field, for pattern-based critic scans."""
        prose = [
            self.executive_summary,
            self.base_case.narrative,
            *(s.narrative for s in self.stress_cases),
            *self.risks,
            *self.trade_offs,
            *self.next_questions,
            self.methodology,
        ]
        return [p for p in prose if p]
