"""One-shot structured output through the Model interface.

Uses Model.structured_output directly (Ollama serves it via native JSON-schema
formatting) rather than the agent event loop: the two LLM call sites in this
project are single-turn, and the direct path is simpler to test and stub.
"""

import asyncio
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

from pydantic import BaseModel
from strands.models.model import Model

T = TypeVar("T", bound=BaseModel)

# Local models occasionally loop during constrained generation; without a
# deadline one hung request blocks the whole pipeline.
_DEFAULT_TIMEOUT_SECONDS = 300.0

#: Monotonic instant that every call inside a `call_deadline` block must finish by.
_deadline: ContextVar[float | None] = ContextVar("planner_lab_call_deadline", default=None)


@contextmanager
def call_deadline(seconds: float) -> Iterator[None]:
    """Bound every structured call made inside the block to one shared deadline.

    The per-call timeout caps a single hung generation and says nothing about what a
    unit of work costs: one `run_analysis` makes up to four calls, so a generous
    per-call timeout multiplies into a budget nobody chose. Batch runners wrap each
    unit in this so the total stays under whatever will otherwise kill the process.
    """
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def _call_timeout() -> float:
    timeout = float(os.environ.get("PLANNER_LAB_LLM_TIMEOUT", _DEFAULT_TIMEOUT_SECONDS))
    deadline = _deadline.get()
    if deadline is None:
        return timeout
    return min(timeout, deadline - time.monotonic())


class StructuredOutputError(RuntimeError):
    pass


async def _collect(model: Model, output_model: type[T], prompt: str, system_prompt: str) -> T:
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    result: T | None = None
    async for event in model.structured_output(
        output_model,
        messages,  # type: ignore[arg-type]
        system_prompt=system_prompt,
    ):
        if "output" in event:
            candidate = event["output"]
            if isinstance(candidate, output_model):
                result = candidate
    if result is None:
        raise StructuredOutputError(f"model produced no {output_model.__name__} structured output")
    return result


def get_structured(model: Model, output_model: type[T], prompt: str, system_prompt: str) -> T:
    """Run one structured-output call, with a single retry on a malformed response.

    Local models occasionally emit malformed JSON or an empty response; that retry is
    cheap, because the failure arrives as fast as the response did.

    A call that burns its whole timeout is not retried. Eval runs pin the seed and the
    temperature, so the second attempt asks a deterministic model the same question and
    hangs the same way; the retry only spends the deadline twice before raising the
    error it was always going to raise. Attempts share the budget set by
    `call_deadline`, so neither failure mode can run past it.
    """

    async def attempt(timeout: float) -> T:
        return await asyncio.wait_for(
            _collect(model, output_model, prompt, system_prompt), timeout=timeout
        )

    def run_once() -> T:
        timeout = _call_timeout()
        if timeout <= 0:
            raise TimeoutError("call deadline exhausted before the request was sent")
        return asyncio.run(attempt(timeout))

    try:
        return run_once()
    except TimeoutError:
        raise
    except Exception:
        return run_once()
