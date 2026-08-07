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


def build_model() -> Model:
    """Build the configured model provider.

    Environment:
        PLANNER_LAB_MODEL_PROVIDER: "ollama" (default) or "bedrock"
        OLLAMA_HOST: Ollama server URL (default http://localhost:11434)
        OLLAMA_MODEL: model id (default qwen3; needs reliable tool calling)
        PLANNER_LAB_OLLAMA_NUM_CTX: context window (default 8192)
        PLANNER_LAB_LLM_TEMPERATURE: sampling temperature (unset = provider default)
        PLANNER_LAB_LLM_SEED: sampling seed, for reproducible eval runs (Ollama only)
        PLANNER_LAB_BEDROCK_MODEL: Bedrock model id (provider "bedrock" only)
    """
    provider = os.environ.get("PLANNER_LAB_MODEL_PROVIDER", "ollama")
    temperature = os.environ.get("PLANNER_LAB_LLM_TEMPERATURE")
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        kwargs: dict[str, Any] = {"options": _ollama_options()}
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("OLLAMA_MODEL", "qwen3"),
            **kwargs,
        )
    if provider == "bedrock":
        from strands.models import BedrockModel

        model_id = os.environ.get("PLANNER_LAB_BEDROCK_MODEL")
        return BedrockModel(model_id=model_id) if model_id else BedrockModel()
    raise ValueError(f"unknown model provider {provider!r}")
