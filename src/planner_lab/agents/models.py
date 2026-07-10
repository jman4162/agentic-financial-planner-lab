"""Model factory. Local-first: Ollama by default, swappable via environment."""

import os

from strands.models.model import Model


def build_model() -> Model:
    """Build the configured model provider.

    Environment:
        PLANNER_LAB_MODEL_PROVIDER: "ollama" (default) or "bedrock"
        OLLAMA_HOST: Ollama server URL (default http://localhost:11434)
        OLLAMA_MODEL: model id (default qwen3; needs reliable tool calling)
        PLANNER_LAB_BEDROCK_MODEL: Bedrock model id (provider "bedrock" only)
    """
    provider = os.environ.get("PLANNER_LAB_MODEL_PROVIDER", "ollama")
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("OLLAMA_MODEL", "qwen3"),
        )
    if provider == "bedrock":
        from strands.models import BedrockModel

        model_id = os.environ.get("PLANNER_LAB_BEDROCK_MODEL")
        return BedrockModel(model_id=model_id) if model_id else BedrockModel()
    raise ValueError(f"unknown model provider {provider!r}")
