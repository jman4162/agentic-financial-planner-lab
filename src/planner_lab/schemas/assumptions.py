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
    # Optional per-asset-class assumptions (real rates). When present alongside
    # a case portfolio, simulation models stocks/bonds/cash as correlated
    # assets; otherwise it falls back to the blended single-asset figures above.
    stock_return_real: float | None = Field(default=None, gt=-0.5, lt=0.5)
    bond_return_real: float | None = Field(default=None, gt=-0.5, lt=0.5)
    stock_volatility: float | None = Field(default=None, ge=0, lt=1)
    bond_volatility: float | None = Field(default=None, ge=0, lt=1)
    stock_bond_correlation: float = Field(default=0.1, ge=-1, le=1)
    rationale: dict[str, str] = {}

    def has_asset_classes(self) -> bool:
        return None not in (
            self.stock_return_real,
            self.bond_return_real,
            self.stock_volatility,
            self.bond_volatility,
        )


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
            stock_return_real=0.050,
            bond_return_real=0.015,
            stock_volatility=0.16,
            bond_volatility=0.06,
            stock_bond_correlation=0.1,
            rationale={
                "expected_return_real": "diversified stock/bond mix, net of fees",
                "safe_withdrawal_rate": "4% guideline for a ~30-year horizon",
                "stock_return_real": "global equity premium net of fees",
                "bond_return_real": "investment-grade real yield",
            },
        ),
        conservative=AssumptionSet(
            label="conservative",
            expected_return_real=0.020,
            return_volatility=0.14,
            inflation=0.035,
            safe_withdrawal_rate=0.033,
            stock_return_real=0.030,
            bond_return_real=0.005,
            stock_volatility=0.19,
            bond_volatility=0.07,
            stock_bond_correlation=0.3,
            rationale={
                "expected_return_real": "lower equity premium, higher inflation drag",
                "safe_withdrawal_rate": "longer horizon or worse sequence of returns",
                "stock_bond_correlation": "stocks and bonds co-fall in inflationary stress",
            },
        ),
        optimistic=AssumptionSet(
            label="optimistic",
            expected_return_real=0.055,
            return_volatility=0.11,
            inflation=0.020,
            safe_withdrawal_rate=0.045,
            stock_return_real=0.065,
            bond_return_real=0.020,
            stock_volatility=0.15,
            bond_volatility=0.05,
            stock_bond_correlation=0.0,
            rationale={
                "expected_return_real": "higher real growth, benign inflation",
                "safe_withdrawal_rate": "flexible spending allows a higher rate",
            },
        ),
    )
