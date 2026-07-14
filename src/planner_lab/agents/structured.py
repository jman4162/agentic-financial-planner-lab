"""One-shot structured output through the Model interface.

Uses Model.structured_output directly (Ollama serves it via native JSON-schema
formatting) rather than the agent event loop: the two LLM call sites in this
project are single-turn, and the direct path is simpler to test and stub.
"""

import asyncio
import os
from typing import TypeVar

from pydantic import BaseModel
from strands.models.model import Model

T = TypeVar("T", bound=BaseModel)

# Local models occasionally loop during constrained generation; without a
# deadline one hung request blocks the whole pipeline.
_DEFAULT_TIMEOUT_SECONDS = 300.0


def _call_timeout() -> float:
    return float(os.environ.get("PLANNER_LAB_LLM_TIMEOUT", _DEFAULT_TIMEOUT_SECONDS))


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
    """Run one structured-output call, with a single retry on any failure.

    Local models occasionally emit malformed JSON, an empty response, or hang
    in a generation loop; each failure mode gets exactly one retry (bounded by
    PLANNER_LAB_LLM_TIMEOUT seconds per attempt) before the error surfaces.
    """
    timeout = _call_timeout()

    async def attempt() -> T:
        return await asyncio.wait_for(
            _collect(model, output_model, prompt, system_prompt), timeout=timeout
        )

    try:
        return asyncio.run(attempt())
    except Exception:
        return asyncio.run(attempt())
