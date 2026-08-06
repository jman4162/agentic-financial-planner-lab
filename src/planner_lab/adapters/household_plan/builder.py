"""Build a written policy document from a case file.

The case file already carries what a policy document needs: goals with a priority, a
balance sheet that says which account types exist, a liquidity floor, an allocation, and
assumptions that each carry a rationale. This adapter maps those onto the document
generator's inputs so the resulting plan states figures the case file actually holds
rather than blanks somebody has to fill in twice.

Two mappings are worth stating plainly. A numeric policy value is seeded only when the
case file actually implies it, so a figure in the document is one the household supplied.
Anything else is left blank for a person to decide, because a plausible default in a
policy document reads as a decision that was never made. Assumption rationales come from
`AssumptionSet.rationale`, so the document's "why this value" column is populated from
the same strings the memo pipeline surfaces instead of reading "(fill in)".

Nothing here does arithmetic beyond restating a case-file figure in the unit the policy
sentence uses. The calculators own the math.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile

if TYPE_CHECKING:  # pragma: no cover - import guard for the optional dependency
    from householdplan.schemas import PlanSpec

_PRIORITY_ORDER = {"need": 0, "want": 1, "wish": 2}

#: Case-file goal kinds that map onto a flexibility the document understands. A goal with
#: a hard date is not flexible on date; one with no target year is flexible on both.
_KIND_FLEXIBILITY = {
    "emergency_fund": "neither",
    "education": "amount",
    "retirement": "date",
    "purchase": "both",
    "other": "both",
}


def _has_account_type(case: CaseFile, account_type: str) -> bool:
    return any(a.account_type == account_type for a in case.balance_sheet.accounts)


def _months_of_expenses(case: CaseFile) -> float | None:
    """The liquidity floor expressed in months, if both halves are known."""
    floor = case.constraints.liquidity_floor
    annual = case.cash_flow.annual_expenses
    if floor is None or not annual:
        return None
    return round(floor / (annual / 12), 1)


def _savings_rate_pct(case: CaseFile) -> float | None:
    savings = case.cash_flow.effective_savings()
    gross = case.cash_flow.annual_gross_income
    if savings is None or not gross:
        return None
    return round(100 * savings / gross, 1)


def case_to_household(case: CaseFile) -> Any:
    """Map a case file onto the document generator's household flags.

    Note the name collision: `planner_lab.schemas.case_file.Household` is a different
    model, describing people and filing status. The document's household is a set of
    booleans that decide which policies apply.
    """
    from householdplan.schemas import PlanHousehold

    persons = case.household.persons
    couple = len(persons) > 1
    near_retirement = False
    earliest = case.earliest_retirement_age()
    if earliest is not None and persons:
        oldest_now = max(p.age_in(case.created.year) for p in persons)
        near_retirement = (earliest - oldest_now) <= 10

    return PlanHousehold(
        couple=couple,
        partner_a=persons[0].name if persons else "",
        partner_b=persons[1].name if couple else "",
        dependents=case.household.dependents > 0,
        both_retirement_plans=couple
        and sum(1 for a in case.balance_sheet.accounts if a.account_type == "traditional") > 1,
        equity_comp=False,
        taxable=_has_account_type(case, "taxable"),
        near_retirement=near_retirement,
    )


def case_to_spec(case: CaseFile, assumptions: AssumptionSet) -> PlanSpec:
    """Build a plan spec from a case file, seeding every value it can justify."""
    from householdplan.schemas import AssumptionNote, Goal, PlanSpec

    values: dict[str, float | str] = {}
    notes: dict[str, AssumptionNote] = {}

    savings_rate = _savings_rate_pct(case)
    if savings_rate is not None:
        values["savings-rate.rate"] = savings_rate
        notes["savings-rate.rate"] = AssumptionNote(
            why="The rate the case file's income and spending already imply.",
            revisit_when="Either income or essential spending changes materially.",
        )

    months = _months_of_expenses(case)
    if months is not None:
        values["reserve-floor.months"] = months
        notes["reserve-floor.months"] = AssumptionNote(
            why="The liquidity floor recorded in the case file, expressed in months.",
            revisit_when="Essential spending changes, or the number of incomes changes.",
        )

    if case.portfolio is not None:
        values["allocation-band.stock"] = round(100 * case.portfolio.stock_pct)
        values["allocation-band.bond"] = round(
            100 * (case.portfolio.bond_pct + case.portfolio.cash_pct)
        )
        for key in ("allocation-band.stock", "allocation-band.bond"):
            notes[key] = AssumptionNote(
                why=assumptions.rationale.get(
                    "expected_return_real", "The allocation recorded in the case file."
                ),
                revisit_when="A change in circumstances, not a change in the market.",
            )

    retirement_year = _retirement_year(case)
    if retirement_year is not None:
        values["retire-range.from"] = retirement_year
        values["retire-range.to"] = retirement_year + 5
        notes["retire-range.from"] = AssumptionNote(
            why="The earliest planned retirement age in the case file.",
            revisit_when="A projection moves the earliest workable year by more than one year.",
        )
        notes["retire-range.to"] = AssumptionNote(
            why=(
                "Five years past the earliest date. Planning a window rather than a date "
                "keeps a projection that only works at the early end from looking like a plan."
            ),
            revisit_when="The retirement decision becomes concrete.",
        )

    plan_end = assumptions.rationale.get("plan_end_age")
    if plan_end:
        notes.setdefault(
            "retire-range.to", AssumptionNote(why=plan_end, revisit_when="At the next review.")
        )

    highest_rate = max(
        (li.rate for li in case.balance_sheet.liabilities if li.rate is not None),
        default=None,
    )
    if highest_rate is not None:
        values["debt-priority.rate"] = round(100 * highest_rate, 1)
        notes["debt-priority.rate"] = AssumptionNote(
            why=(
                "Set at the highest rate currently carried, so every existing debt is "
                "above the threshold and none is left to drift."
            ),
            revisit_when="A debt is cleared, refinanced, or added.",
        )

    goals = [
        Goal(
            name=goal.description,
            from_year=goal.target_year,
            to_year=goal.target_year,
            flexible=_KIND_FLEXIBILITY.get(goal.kind, "both"),
        )
        for goal in sorted(case.goals, key=lambda g: _PRIORITY_ORDER.get(g.priority, 3))
    ]

    return PlanSpec(
        household=case_to_household(case),
        effective_date=case.created.isoformat(),
        goals=goals,
        values=values,
        notes=notes,
    )


def _retirement_year(case: CaseFile) -> int | None:
    years = [
        p.birth_year + p.planned_retirement_age
        for p in case.household.persons
        if p.planned_retirement_age
    ]
    return min(years) if years else None


class HouseholdPlanBuilder:
    """Renders the policy document. Satisfies `PlanDocumentBuilder` structurally."""

    name = "householdplan"

    def build(
        self,
        case: CaseFile,
        assumptions: AssumptionSet,
        *,
        attribution: str | None = None,
    ) -> str:
        from householdplan.engine import build_document
        from householdplan.render.markdown import render_markdown
        from householdplan.rules import load_rules

        spec = case_to_spec(case, assumptions)
        document = build_document(spec, load_rules())
        return render_markdown(document, attribution=attribution)

    def check(self, case: CaseFile, assumptions: AssumptionSet) -> list[str]:
        """Structural findings on the generated document, as readable strings."""
        from householdplan.engine import build_document
        from householdplan.rules import load_rules
        from householdplan.validate import validate_plan

        rules = load_rules()
        spec = case_to_spec(case, assumptions)
        report = validate_plan(build_document(spec, rules), rules)
        return [
            f"{'BLOCKING' if f.blocking else 'note'} {f.check}"
            + (f" [{f.where}]" if f.where else "")
            + f": {f.message}"
            for f in report.findings
        ]
