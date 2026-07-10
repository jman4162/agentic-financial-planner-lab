"""Labeled assumption sets. All rates of return are real (after inflation).

Nominal figures enter the system only through `planner_lab.calculators.conversions`.
"""

from typing import Literal

from pydantic import BaseModel, Field

AssumptionLabel = Literal["base", "conservative", "optimistic"]


class AssumptionSet(BaseModel):
    label: AssumptionLabel
    expected_return_real: float = Field(gt=-0.5, lt=0.5)
    return_volatility: float = Field(ge=0, lt=1)
    inflation: float = Field(ge=-0.05, lt=0.5)
    safe_withdrawal_rate: float = Field(gt=0, le=0.20)
    plan_end_age: int = Field(default=95, ge=60, le=120)
    rationale: dict[str, str] = {}


class AssumptionsBundle(BaseModel):
    base: AssumptionSet
    conservative: AssumptionSet
    optimistic: AssumptionSet
    surfaced: bool = False

    def get(self, label: str) -> AssumptionSet:
        if label not in ("base", "conservative", "optimistic"):
            raise KeyError(f"unknown assumption label {label!r}")
        result: AssumptionSet = getattr(self, label)
        return result

    def all_sets(self) -> list[AssumptionSet]:
        return [self.base, self.conservative, self.optimistic]


def default_assumptions() -> AssumptionsBundle:
    """Deterministic defaults for a globally diversified stock/bond portfolio.

    Values are deliberately unheroic; the base real return sits below long-run
    US equity history because the portfolio is assumed diversified and
    fee-paying. Users override per field during intake.
    """
    return AssumptionsBundle(
        base=AssumptionSet(
            label="base",
            expected_return_real=0.040,
            return_volatility=0.12,
            inflation=0.025,
            safe_withdrawal_rate=0.040,
            rationale={
                "expected_return_real": "diversified stock/bond mix, net of fees",
                "safe_withdrawal_rate": "4% guideline for a ~30-year horizon",
            },
        ),
        conservative=AssumptionSet(
            label="conservative",
            expected_return_real=0.020,
            return_volatility=0.14,
            inflation=0.035,
            safe_withdrawal_rate=0.033,
            rationale={
                "expected_return_real": "lower equity premium, higher inflation drag",
                "safe_withdrawal_rate": "longer horizon or worse sequence of returns",
            },
        ),
        optimistic=AssumptionSet(
            label="optimistic",
            expected_return_real=0.055,
            return_volatility=0.11,
            inflation=0.020,
            safe_withdrawal_rate=0.045,
            rationale={
                "expected_return_real": "higher real growth, benign inflation",
                "safe_withdrawal_rate": "flexible spending allows a higher rate",
            },
        ),
    )
