"""LLM critic: the second LLM call site.

Judges tone and advice-shape in memo prose — the judgments regex checks miss.
Its findings merge with the deterministic checks in run_critic; a blocker from
either side rejects the memo.
"""

from typing import Literal

from pydantic import BaseModel
from strands.models.model import Model

from planner_lab.agents.structured import get_structured
from planner_lab.critic.run import LLMChecks
from planner_lab.schemas.critic import CriticCheck
from planner_lab.schemas.memo import PlanningMemo

_SYSTEM_PROMPT = """\
You review financial planning memos for two problems only:
1. certainty_not_overstated: does the prose promise or imply certain outcomes
   (beyond citing simulation probabilities as probabilities)?
2. no_securities_advice: does the prose tell the reader to buy, sell, or hold
   any specific security, fund, or asset right now?
Judge tone and meaning, not keywords. Pass a check unless there is a clear
violation; quote the offending sentence as evidence when you fail one.
"""


class LLMFinding(BaseModel):
    check_id: Literal["certainty_not_overstated", "no_securities_advice"]
    passed: bool
    details: str
    evidence: list[str] = []


class LLMCriticFindings(BaseModel):
    findings: list[LLMFinding]


def make_llm_checks(model: Model) -> LLMChecks:
    def llm_checks(memo: PlanningMemo) -> list[CriticCheck]:
        prose = "\n\n".join(memo.all_prose())
        result = get_structured(
            model,
            LLMCriticFindings,
            f"Review this memo prose:\n\n{prose}\n\nReturn one finding per check.",
            _SYSTEM_PROMPT,
        )
        return [
            CriticCheck(
                check_id=f.check_id,
                passed=f.passed,
                severity="blocker",
                details=f"[llm] {f.details}",
                evidence=f.evidence,
            )
            for f in result.findings
        ]

    return llm_checks
