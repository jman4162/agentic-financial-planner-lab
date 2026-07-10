"""The case file: the single typed object every analysis flows through.

All dollar amounts are annual and in today's (real) dollars unless a field
name says otherwise. `Money` is a documented alias for float; round at
presentation time, never inside calculators.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Money = float

AccountType = Literal["taxable", "traditional", "roth", "cash", "hsa", "education", "other"]
FilingStatus = Literal["single", "married_joint", "married_separate", "head_of_household"]


class Person(BaseModel):
    name: str
    birth_year: int = Field(ge=1900, le=2100)
    planned_retirement_age: int | None = Field(default=None, ge=18, le=100)

    def age_in(self, year: int) -> int:
        return year - self.birth_year


class Household(BaseModel):
    persons: list[Person] = Field(min_length=1)
    state: str | None = None
    filing_status: FilingStatus | None = None
    dependents: int = Field(default=0, ge=0)


class Goal(BaseModel):
    goal_id: str
    kind: Literal["retirement", "education", "purchase", "emergency_fund", "other"]
    description: str
    target_year: int | None = None
    annual_amount_today: Money | None = Field(default=None, ge=0)
    priority: Literal["need", "want", "wish"] = "need"


class Account(BaseModel):
    account_id: str
    name: str
    account_type: AccountType
    balance: Money = Field(ge=0)
    annual_contribution: Money = Field(default=0, ge=0)


class Liability(BaseModel):
    liability_id: str
    name: str
    balance: Money = Field(ge=0)
    rate: float | None = Field(default=None, ge=0)
    minimum_annual_payment: Money | None = Field(default=None, ge=0)


class BalanceSheet(BaseModel):
    accounts: list[Account] = []
    liabilities: list[Liability] = []

    @property
    def investable_assets(self) -> Money:
        return sum(a.balance for a in self.accounts if a.account_type != "cash")

    @property
    def total_assets(self) -> Money:
        return sum(a.balance for a in self.accounts)

    @property
    def total_liabilities(self) -> Money:
        return sum(li.balance for li in self.liabilities)

    @property
    def net_worth(self) -> Money:
        return self.total_assets - self.total_liabilities

    @property
    def annual_contributions(self) -> Money:
        return sum(a.annual_contribution for a in self.accounts)


class CashFlow(BaseModel):
    annual_gross_income: Money | None = Field(default=None, ge=0)
    annual_take_home: Money | None = Field(default=None, ge=0)
    annual_expenses: Money | None = Field(default=None, ge=0)
    annual_savings: Money | None = Field(default=None, ge=0)

    def effective_savings(self) -> Money | None:
        """Explicit savings, or take-home minus expenses when both are known."""
        if self.annual_savings is not None:
            return self.annual_savings
        if self.annual_take_home is not None and self.annual_expenses is not None:
            return max(self.annual_take_home - self.annual_expenses, 0.0)
        return None


class Portfolio(BaseModel):
    stock_pct: float = Field(ge=0, le=1)
    bond_pct: float = Field(ge=0, le=1)
    cash_pct: float = Field(default=0, ge=0, le=1)
    weighted_expense_ratio: float | None = Field(default=None, ge=0, le=0.05)
    concentration_note: str | None = None

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "Portfolio":
        total = self.stock_pct + self.bond_pct + self.cash_pct
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"allocation weights sum to {total:.4f}, expected 1.0")
        return self


class Constraints(BaseModel):
    liquidity_floor: Money | None = Field(default=None, ge=0)
    exclusions: str | None = None
    notes: list[str] = []


class CaseFile(BaseModel):
    case_id: str
    created: datetime.date
    question: str
    household: Household
    goals: list[Goal] = []
    balance_sheet: BalanceSheet = BalanceSheet()
    cash_flow: CashFlow = CashFlow()
    portfolio: Portfolio | None = None
    assumptions: "AssumptionsBundle | None" = None
    constraints: Constraints = Constraints()
    missing_fields: list[str] = []

    def retirement_spending_target(self) -> Money | None:
        """Annual retirement spending in today's dollars: the retirement goal's
        amount, falling back to current expenses."""
        for goal in self.goals:
            if goal.kind == "retirement" and goal.annual_amount_today is not None:
                return goal.annual_amount_today
        return self.cash_flow.annual_expenses

    _AUTO_MISSING = frozenset(
        {
            "cash_flow.annual_expenses",
            "cash_flow.annual_savings",
            "portfolio",
            "goals.retirement.annual_amount_today",
        }
    )

    @model_validator(mode="after")
    def _flag_missing_material_fields(self) -> "CaseFile":
        """Record material gaps as dotted paths so downstream stages must disclose
        them. Auto-derived paths are recomputed on every validation (so resolved
        gaps clear); manually added entries are preserved."""
        found = set(self.missing_fields) - self._AUTO_MISSING
        if self.cash_flow.annual_expenses is None:
            found.add("cash_flow.annual_expenses")
        if self.cash_flow.effective_savings() is None:
            found.add("cash_flow.annual_savings")
        if self.portfolio is None:
            found.add("portfolio")
        retirement_goals = [g for g in self.goals if g.kind == "retirement"]
        if retirement_goals and all(g.annual_amount_today is None for g in retirement_goals):
            found.add("goals.retirement.annual_amount_today")
        self.missing_fields = sorted(found)
        return self


from planner_lab.schemas.assumptions import AssumptionsBundle  # noqa: E402

CaseFile.model_rebuild()
