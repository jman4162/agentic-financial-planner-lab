"""Interactive intake orchestrator: one agent, deterministic tools, guarded."""

import datetime

from strands import Agent
from strands.models.model import Model

from planner_lab.agents.state import RunState
from planner_lab.agents.tools import TOOL_NAMES, build_planner_tools
from planner_lab.hooks.compliance import ComplianceGuard
from planner_lab.schemas.case_file import CaseFile, Household, Person
from planner_lab.schemas.results import ComputationLedger

_SYSTEM_PROMPT = """\
You are an educational financial planning intake assistant. Your job:
1. Ask high-value questions one or two at a time: ages, planned retirement age,
   account balances by tax type (taxable/traditional/roth/cash), annual savings,
   annual spending, retirement spending target, state, filing status.
2. Record facts by calling update_case_file with the full case JSON.
3. Never perform arithmetic yourself; call the calculator tools and report
   their outputs with the entry_id they return.
4. Before any simulation, call build_assumptions then surface_assumptions and
   show the user the table verbatim; ask them to confirm or adjust.
5. Never recommend specific securities, funds, or trades. Never promise
   outcomes. This is educational analysis, not financial advice, and you should
   say so when presenting results.
"""


def empty_case(question: str) -> CaseFile:
    return CaseFile(
        case_id=f"intake-{datetime.date.today().isoformat()}",
        created=datetime.date.today(),
        question=question,
        household=Household(persons=[Person(name="Person 1", birth_year=1980)]),
    )


def build_orchestrator(
    model: Model,
    case: CaseFile | None = None,
    session_id: str | None = None,
) -> tuple[Agent, RunState]:
    working_case = case if case is not None else empty_case("(to be gathered)")
    state = RunState(
        case=working_case,
        ledger=ComputationLedger(case_id=working_case.case_id),
        allowed_tools=TOOL_NAMES,
    )
    kwargs: dict[str, object] = {}
    if session_id is not None:
        from strands.session.file_session_manager import FileSessionManager

        kwargs["session_manager"] = FileSessionManager(session_id=session_id)
    agent = Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=build_planner_tools(state),
        hooks=[ComplianceGuard(state)],
        **kwargs,  # type: ignore[arg-type]
    )
    return agent, state
