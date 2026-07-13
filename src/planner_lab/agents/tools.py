"""Plain tools for the interactive orchestrator: closures over one RunState.

Every calculation records a ledger entry and returns its entry_id so the model
can cite results as ledger:<entry_id>#<key>. No tool contains LLM reasoning.
"""

import io
from typing import Any

from rich.console import Console
from strands import tool

from planner_lab import calculators
from planner_lab.adapters import get_simulator
from planner_lab.agents.state import RunState
from planner_lab.schemas.assumptions import default_assumptions
from planner_lab.schemas.case_file import CaseFile

TOOL_NAMES = frozenset(
    {
        "calc_funded_ratio",
        "calc_years_to_fi",
        "calc_sustainable_spending",
        "build_assumptions",
        "surface_assumptions",
        "run_simulation",
        "update_case_file",
        "show_case_file",
        "search_research",
        "fetch_research",
    }
)

_RESEARCH_EXCERPT_BUDGET = 4000


def build_planner_tools(state: RunState) -> list[Any]:
    @tool
    def calc_funded_ratio(annual_spending: float, withdrawal_rate: float = 0.04) -> dict[str, Any]:
        """Funded ratio of the case's investable assets against an annual
        spending target. Returns the results plus an entry_id to cite.

        Args:
            annual_spending: Target annual retirement spending in today's dollars.
            withdrawal_rate: Withdrawal rate as a decimal; omit for the 4% default.
        """
        portfolio = state.case.balance_sheet.investable_assets
        result = calculators.funded_ratio(portfolio, annual_spending, withdrawal_rate)
        entry_id = state.ledger.add(
            "funded_ratio",
            {
                "portfolio_value": portfolio,
                "annual_spending": annual_spending,
                "withdrawal_rate": withdrawal_rate,
            },
            result,
        )
        return {"entry_id": entry_id, **result}

    @tool
    def calc_years_to_fi(
        annual_spending: float, real_return: float = 0.04, withdrawal_rate: float = 0.04
    ) -> dict[str, Any]:
        """Years until the case's portfolio supports the spending target.

        Args:
            annual_spending: Target annual spending in today's dollars.
            real_return: Expected real (after-inflation) return, decimal.
            withdrawal_rate: Withdrawal rate as a decimal.
        """
        portfolio = state.case.balance_sheet.investable_assets
        savings = state.case.cash_flow.effective_savings()
        if savings is None:
            savings = state.case.balance_sheet.annual_contributions
        years = calculators.years_to_fi(
            portfolio, savings, annual_spending, real_return, withdrawal_rate
        )
        outputs = {"years_to_fi": years}
        entry_id = state.ledger.add(
            "years_to_fi",
            {
                "current_portfolio": portfolio,
                "annual_savings": savings,
                "annual_spending": annual_spending,
                "real_return": real_return,
                "withdrawal_rate": withdrawal_rate,
            },
            outputs,
        )
        return {"entry_id": entry_id, **outputs}

    @tool
    def calc_sustainable_spending(withdrawal_rate: float = 0.04) -> dict[str, Any]:
        """Annual spending the case's investable assets support.

        Args:
            withdrawal_rate: Withdrawal rate as a decimal; omit for the 4% default.
        """
        portfolio = state.case.balance_sheet.investable_assets
        value = calculators.sustainable_spending(portfolio, withdrawal_rate)
        entry_id = state.ledger.add(
            "sustainable_spending",
            {"portfolio_value": portfolio, "withdrawal_rate": withdrawal_rate},
            {"sustainable_spending": value},
        )
        return {"entry_id": entry_id, "sustainable_spending": value}

    @tool
    def build_assumptions() -> str:
        """Attach the default base/conservative/optimistic assumption sets to the
        case. Call surface_assumptions next to show them to the user."""
        state.case.assumptions = default_assumptions()
        return "Default assumption sets attached (not yet surfaced to the user)."

    @tool
    def surface_assumptions() -> str:
        """Render the assumption table to show the user. Marks assumptions as
        surfaced, which unlocks simulation."""
        from planner_lab.agents.pipeline import assumptions_table

        if state.case.assumptions is None:
            state.case.assumptions = default_assumptions()
        buffer = io.StringIO()
        Console(file=buffer, width=100).print(assumptions_table(state.case.assumptions))
        state.case.assumptions.surfaced = True
        return buffer.getvalue()

    @tool
    def run_simulation(assumptions_label: str = "base") -> dict[str, Any]:
        """Run a Monte Carlo retirement simulation for one assumption set.
        Requires assumptions to have been surfaced to the user first.

        Args:
            assumptions_label: "base", "conservative", or "optimistic".
        """
        from planner_lab.protocols import DEFAULT_N_PATHS, DEFAULT_SEED

        assert state.case.assumptions is not None  # guarded by compliance hook
        aset = state.case.assumptions.get(assumptions_label)
        summary = get_simulator().simulate(
            state.case, aset, n_paths=DEFAULT_N_PATHS, seed=DEFAULT_SEED
        )
        outputs: dict[str, Any] = {
            "success_probability": summary.success_probability,
            **{f"terminal_wealth_{k}": v for k, v in summary.terminal_wealth_percentiles.items()},
        }
        entry_id = state.ledger.add(
            "run_simulation",
            {"assumptions_label": assumptions_label, "n_paths": DEFAULT_N_PATHS, "seed": DEFAULT_SEED},
            outputs,
            assumptions_label=assumptions_label,
            kind="sim",
        )
        return {"entry_id": entry_id, **outputs}

    @tool
    def update_case_file(case_json: str) -> str:
        """Replace the working case file with new JSON after gathering facts.
        Validation errors are returned for correction.

        Args:
            case_json: Full case file as a JSON string.
        """
        state.case = CaseFile.model_validate_json(case_json)
        gaps = ", ".join(state.case.missing_fields) or "none"
        return f"Case file updated. Missing material fields: {gaps}."

    @tool
    def show_case_file() -> str:
        """Return the current case file as JSON."""
        return state.case.model_dump_json(indent=2)

    _source_cell: list[Any] = []

    def _research_source() -> Any:
        if state.research_url is None:
            return None
        if not _source_cell:
            from planner_lab.adapters import get_research_source

            _source_cell.append(get_research_source(state.research_url))
        return _source_cell[0]

    @tool
    def search_research(query: str, limit: int = 5) -> dict[str, Any] | str:
        """Search the configured research library for educational guides.

        Args:
            query: Search terms, e.g. the user's planning question.
            limit: Maximum hits to return.
        """
        source = _research_source()
        if source is None:
            return "Research is not configured for this session."
        hits = source.search(query, limit=limit)
        entry_id = state.ledger.add(
            "search_research",
            {"query": query, "limit": limit},
            {"refs": [h.ref for h in hits]},
            adapter=source.name,
            kind="research",
        )
        return {"entry_id": entry_id, "results": [h.model_dump() for h in hits]}

    @tool
    def fetch_research(ref: str) -> dict[str, Any] | str:
        """Fetch one research guide by its ref (from search_research results).

        Args:
            ref: The guide ref returned by search_research.
        """
        source = _research_source()
        if source is None:
            return "Research is not configured for this session."
        doc = source.fetch(ref)
        entry_id = state.ledger.add(
            "fetch_research",
            {"ref": ref},
            {"ref": doc.ref, "title": doc.title, "url": doc.url or ""},
            adapter=source.name,
            kind="research",
        )
        return {
            "entry_id": entry_id,
            "ref": doc.ref,
            "title": doc.title,
            "url": doc.url,
            "excerpt": doc.text[:_RESEARCH_EXCERPT_BUDGET],
        }

    return [
        calc_funded_ratio,
        calc_years_to_fi,
        calc_sustainable_spending,
        build_assumptions,
        surface_assumptions,
        run_simulation,
        update_case_file,
        show_case_file,
        search_research,
        fetch_research,
    ]
