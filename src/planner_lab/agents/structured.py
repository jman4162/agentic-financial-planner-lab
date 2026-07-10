"""One-shot structured output through the Model interface.

Uses Model.structured_output directly (Ollama serves it via native JSON-schema
formatting) rather than the agent event loop: the two LLM call sites in this
project are single-turn, and the direct path is simpler to test and stub.
"""

import asyncio
from typing import TypeVar

from pydantic import BaseModel
from strands.models.model import Model

T = TypeVar("T", bound=BaseModel)


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
    """Run one structured-output call, with a single retry on validation failure."""
    try:
        return asyncio.run(_collect(model, output_model, prompt, system_prompt))
    except StructuredOutputError:
        raise
    except Exception:
        # One retry: local models occasionally emit malformed JSON.
        return asyncio.run(_collect(model, output_model, prompt, system_prompt))
