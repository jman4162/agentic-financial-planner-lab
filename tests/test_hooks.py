"""ComplianceGuard tests: constructed BeforeToolCallEvent, no model calls."""

from strands import Agent
from strands.hooks import BeforeToolCallEvent

from planner_lab.agents.state import RunState
from planner_lab.agents.tools import TOOL_NAMES
from planner_lab.hooks.compliance import ComplianceGuard
from planner_lab.schemas.results import ComputationLedger
from tests.support.fixtures import make_case
from tests.support.stub_model import StubModel


def make_event(agent: Agent, name: str, tool_input: dict[str, object]) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"toolUseId": "t-1", "name": name, "input": tool_input},
        invocation_state={},
    )


def make_guard(*, surfaced: bool) -> tuple[ComplianceGuard, Agent]:
    case = make_case(surfaced=surfaced)
    state = RunState(
        case=case,
        ledger=ComputationLedger(case_id=case.case_id),
        allowed_tools=TOOL_NAMES,
    )
    return ComplianceGuard(state), Agent(model=StubModel())


class TestComplianceGuard:
    def test_simulation_blocked_before_surfacing(self) -> None:
        guard, agent = make_guard(surfaced=False)
        event = make_event(agent, "run_simulation", {"assumptions_label": "base"})
        guard._before_tool(event)
        assert isinstance(event.cancel_tool, str)
        assert "surfaced" in event.cancel_tool

    def test_simulation_allowed_after_surfacing(self) -> None:
        guard, agent = make_guard(surfaced=True)
        event = make_event(agent, "run_simulation", {"assumptions_label": "base"})
        guard._before_tool(event)
        assert event.cancel_tool is False

    def test_unknown_tool_blocked(self) -> None:
        guard, agent = make_guard(surfaced=True)
        event = make_event(agent, "execute_trade", {})
        guard._before_tool(event)
        assert isinstance(event.cancel_tool, str)
        assert "not permitted" in event.cancel_tool

    def test_security_selection_input_blocked(self) -> None:
        guard, agent = make_guard(surfaced=True)
        event = make_event(
            agent, "calc_funded_ratio", {"annual_spending": "which stock should I buy"}
        )
        guard._before_tool(event)
        assert isinstance(event.cancel_tool, str)
        assert "out of scope" in event.cancel_tool

    def test_normal_calculator_allowed(self) -> None:
        guard, agent = make_guard(surfaced=False)
        event = make_event(agent, "calc_funded_ratio", {"annual_spending": 60000})
        guard._before_tool(event)
        assert event.cancel_tool is False
