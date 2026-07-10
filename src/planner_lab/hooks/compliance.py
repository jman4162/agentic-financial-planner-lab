"""Input-side compliance guard for the interactive agent.

Defense-in-depth: the deterministic pipeline enforces the same preconditions in
code; this hook enforces them when the model drives tool selection.
"""

import json
import re
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from planner_lab.agents.state import RunState

_SECURITY_SELECTION = re.compile(
    r"\$[A-Z]{1,5}\b|\b(ticker|which stock|what stock|undervalued|hot stock)\b",
    re.IGNORECASE,
)

_NEEDS_SURFACED_ASSUMPTIONS = {"run_simulation"}


class ComplianceGuard(HookProvider):
    def __init__(self, state: RunState):
        self._state = state

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before_tool)

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        if self._state.allowed_tools and name not in self._state.allowed_tools:
            event.cancel_tool = f"Tool {name!r} is not permitted in this workflow."
            return
        if name in _NEEDS_SURFACED_ASSUMPTIONS and not self._state.assumptions_surfaced:
            event.cancel_tool = (
                "Assumptions must be built and surfaced to the user before simulation: "
                "call build_assumptions, then surface_assumptions, and show the user "
                "the table."
            )
            return
        tool_input = json.dumps(event.tool_use.get("input", {}))
        if _SECURITY_SELECTION.search(tool_input):
            event.cancel_tool = (
                "Individual security selection is out of scope; this workflow analyzes "
                "portfolio structure only."
            )
