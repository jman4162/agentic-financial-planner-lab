"""Model factory. Local-first: Ollama by default, swappable via environment."""

import os
from typing import Any

from strands.models.model import Model

#: Ollama's server-side default context is 4,096 tokens, and it truncates input from the
#: front silently. The memo prompt (case file, number menu, instructions) runs past 2,000
#: tokens before the model writes a word, so the default risks cutting the menu the model
#: is required to copy source ids from. 8,192 fits every current prompt with headroom.
DEFAULT_NUM_CTX = 8192


def _ollama_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "num_ctx": int(os.environ.get("PLANNER_LAB_OLLAMA_NUM_CTX", DEFAULT_NUM_CTX))
    }
    seed = os.environ.get("PLANNER_LAB_LLM_SEED")
    if seed is not None:
        options["seed"] = int(seed)
    return options


def _critic_think() -> bool | None:
    """Whether to ask the critic's model to reason before answering, or None to not ask.

    Unset means the request carries no `think` field at all, which is what every
    provider understood before this setting existed. Reasoning models are the reason
    it exists: on a CPU-only runner the critic spends most of its wall clock emitting
    reasoning tokens nobody reads, for a judgment that is two booleans and a sentence.
    """
    raw = os.environ.get("PLANNER_LAB_CRITIC_THINK", "").strip().lower()
    if not raw:
        return None
    return raw in {"1", "true", "yes", "on"}


def build_model(*, model_id: str | None = None, think: bool | None = None) -> Model:
    """Build the configured model provider.

    Environment:
        PLANNER_LAB_MODEL_PROVIDER: "ollama" (default) or "bedrock"
        OLLAMA_HOST: Ollama server URL (default http://localhost:11434)
        OLLAMA_MODEL: model id (default qwen3; needs reliable tool calling)
        PLANNER_LAB_OLLAMA_NUM_CTX: context window (default 8192)
        PLANNER_LAB_LLM_TEMPERATURE: sampling temperature (unset = provider default)
        PLANNER_LAB_LLM_SEED: sampling seed, for reproducible eval runs (Ollama only)
        PLANNER_LAB_BEDROCK_MODEL: Bedrock model id (provider "bedrock" only)

    ``model_id`` overrides the environment's model selection while keeping every other
    setting; used to build the critic on a different model than the writer. ``think``
    turns a reasoning model's hidden reasoning on or off (Ollama only); None leaves the
    field out of the request, which is the provider's own default.
    """
    provider = os.environ.get("PLANNER_LAB_MODEL_PROVIDER", "ollama")
    temperature = os.environ.get("PLANNER_LAB_LLM_TEMPERATURE")
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        kwargs: dict[str, Any] = {"options": _ollama_options()}
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if think is not None:
            # Ollama reads `think` beside `messages`, not inside `options`, and
            # additional_args is the provider's passthrough for top-level fields.
            kwargs["additional_args"] = {"think": think}
        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=model_id or os.environ.get("OLLAMA_MODEL", "qwen3"),
            **kwargs,
        )
    if provider == "bedrock":
        from strands.models import BedrockModel

        bedrock_id = model_id or os.environ.get("PLANNER_LAB_BEDROCK_MODEL")
        return BedrockModel(model_id=bedrock_id) if bedrock_id else BedrockModel()
    raise ValueError(f"unknown model provider {provider!r}")


def build_critic_model() -> Model | None:
    """Build a separate model for the LLM critic, or None to reuse the writer's.

    Environment:
        PLANNER_LAB_CRITIC_MODEL: model id for the critic (same provider as the writer)
        PLANNER_LAB_CRITIC_THINK: reasoning on/off for a reasoning critic (Ollama only)

    A model reviewing its own prose is a weak judge, and with a small writer it is an
    erratic one: in instrumented eval runs the self-judge flagged a suggested question
    as securities advice and a meta-sentence as overstated certainty, none of it
    corroborated by the deterministic checks. The critic call is short, so a stronger
    judge costs little even where the writer must stay small.
    """
    critic_id = os.environ.get("PLANNER_LAB_CRITIC_MODEL")
    if not critic_id:
        return None
    return build_model(model_id=critic_id, think=_critic_think())
