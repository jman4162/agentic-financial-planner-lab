"""A scripted strands Model for no-network tests.

Queue Pydantic instances for structured_output calls; each call pops the next.
`stream` yields a minimal text response (the pipeline never uses it, but the
ABC requires it and the orchestrator path may touch it).
"""

from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.streaming import StreamEvent

T = TypeVar("T", bound=BaseModel)


class StubModel(Model):
    def __init__(self, structured_outputs: list[BaseModel] | None = None):
        self._structured_outputs = list(structured_outputs or [])
        self.structured_output_calls: list[tuple[type[BaseModel], str]] = []
        self._config: dict[str, Any] = {}

    def queue(self, *outputs: BaseModel) -> None:
        self._structured_outputs.extend(outputs)

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Any,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        prompt_text = str(prompt)
        self.structured_output_calls.append((output_model, prompt_text))
        if not self._structured_outputs:
            raise AssertionError(f"StubModel has no queued output for {output_model.__name__}")
        candidate = self._structured_outputs.pop(0)
        if not isinstance(candidate, output_model):
            raise AssertionError(
                f"queued output is {type(candidate).__name__}, expected {output_model.__name__}"
            )
        yield {"output": candidate}

    async def stream(
        self,
        messages: Any,
        tool_specs: Any = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        events: list[StreamEvent] = [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"start": {}}},
            {"contentBlockDelta": {"delta": {"text": "ok"}}},
            {"contentBlockStop": {}},
            {"messageStop": {"stopReason": "end_turn"}},
        ]
        for event in events:
            yield event
