"""Shared synthetic fixtures for tests. All figures invented."""

import datetime

from planner_lab.calculators import funded_ratio
from planner_lab.memo.disclaimer import REQUIRED_DISCLAIMER
from planner_lab.schemas.assumptions import AssumptionsBundle, default_assumptions
from planner_lab.schemas.case_file import (
    Account,
    BalanceSheet,
    CaseFile,
    CashFlow,
    Goal,
    Household,
    Person,
    Portfolio,
)
from planner_lab.schemas.memo import PlanningMemo, ScenarioNarrative, TracedNumber
from planner_lab.schemas.results import ComputationLedger


def make_case(*, surfaced: bool = True) -> CaseFile:
    bundle = default_assumptions()
    bundle.surfaced = surfaced
    return CaseFile(
        case_id="test-case",
        created=datetime.date(2026, 1, 15),
        question="Can we retire at 62?",
        household=Household(
            persons=[Person(name="Avery Example", birth_year=1972, planned_retirement_age=62)],
            filing_status="married_joint",
        ),
        goals=[
            Goal(
                goal_id="retire-62",
                kind="retirement",
                description="Retire at 62",
                annual_amount_today=60_000,
            )
        ],
        balance_sheet=BalanceSheet(
            accounts=[
                Account(
                    account_id="taxable-1",
                    name="Brokerage",
                    account_type="taxable",
                    balance=350_000,
                    annual_contribution=12_000,
                ),
                Account(
                    account_id="trad-1",
                    name="Pre-tax retirement",
                    account_type="traditional",
                    balance=520_000,
                    annual_contribution=30_000,
                ),
            ]
        ),
        cash_flow=CashFlow(
            annual_gross_income=190_000,
            annual_take_home=138_000,
            annual_expenses=88_000,
            annual_savings=50_000,
        ),
        portfolio=Portfolio(stock_pct=0.7, bond_pct=0.25, cash_pct=0.05),
        assumptions=bundle,
    )


def make_ledger(case: CaseFile) -> ComputationLedger:
    """Ledger with one funded-ratio entry computed from the case."""
    ledger = ComputationLedger(case_id=case.case_id)
    result = funded_ratio(case.balance_sheet.investable_assets, 60_000, 0.04)
    ledger.add(
        "funded_ratio",
        {"portfolio_value": case.balance_sheet.investable_assets, "annual_spending": 60_000},
        result,
        assumptions_label="base",
    )
    return ledger


def make_memo(
    case: CaseFile,
    ledger: ComputationLedger,
    *,
    assumptions: AssumptionsBundle | None = None,
) -> PlanningMemo:
    """A memo that passes every deterministic critic check."""
    entry = ledger.entries[0]
    fr = TracedNumber(
        label="Funded ratio (base)",
        value=round(entry.outputs["funded_ratio"], 2),
        unit="ratio",
        source_id=f"ledger:{entry.entry_id}#funded_ratio",
    )
    assets = TracedNumber(
        label="Investable assets",
        value=case.balance_sheet.investable_assets,
        unit="usd",
        source_id="case:balance_sheet.investable_assets",
    )
    bundle = assumptions if assumptions is not None else case.assumptions
    assert bundle is not None
    return PlanningMemo(
        case_id=case.case_id,
        executive_summary=(
            "The household is partially funded for its retirement spending target; "
            "outcomes depend heavily on the assumption set."
        ),
        inputs_summary=[assets],
        missing_data=list(case.missing_fields),
        assumptions_table=bundle,
        base_case=ScenarioNarrative(
            label="base",
            narrative="Under base assumptions the portfolio covers most of the target.",
            key_numbers=[fr],
        ),
        risks=["Sequence-of-returns risk early in retirement."],
        trade_offs=["Retiring later increases funding at the cost of working years."],
        next_questions=["What is the flexible portion of the spending target?"],
        methodology=(
            "Deterministic funded-ratio arithmetic under base, conservative, and "
            "optimistic assumption sets. All figures are real (today's dollars)."
        ),
        disclaimer=REQUIRED_DISCLAIMER,
    )
