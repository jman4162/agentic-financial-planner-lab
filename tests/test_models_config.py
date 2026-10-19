"""Environment plumbing for the model factory."""

import pytest

pytest.importorskip("strands")

from planner_lab.agents.models import DEFAULT_NUM_CTX, DEFAULT_REPEAT_PENALTY, build_model


def _ollama_config(model):  # type: ignore[no-untyped-def]
    return model.get_config()


def test_num_ctx_defaults_high_enough_for_the_memo_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama's server default is 4096 and it truncates input from the front, which can
    silently cut the number menu the model must copy source ids from."""
    monkeypatch.delenv("PLANNER_LAB_OLLAMA_NUM_CTX", raising=False)
    config = _ollama_config(build_model())
    assert config["options"]["num_ctx"] == DEFAULT_NUM_CTX
    assert DEFAULT_NUM_CTX >= 8192


def test_num_ctx_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANNER_LAB_OLLAMA_NUM_CTX", "16384")
    assert _ollama_config(build_model())["options"]["num_ctx"] == 16384


def test_repeat_penalty_is_set_even_when_the_server_default_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama 0.32.10 turned its default penalty off, and greedy decoding on the small
    writer then loops inside a JSON string until the call times out."""
    monkeypatch.delenv("PLANNER_LAB_OLLAMA_REPEAT_PENALTY", raising=False)
    config = _ollama_config(build_model())
    assert config["options"]["repeat_penalty"] == DEFAULT_REPEAT_PENALTY
    assert DEFAULT_REPEAT_PENALTY > 1.0


def test_repeat_penalty_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANNER_LAB_OLLAMA_REPEAT_PENALTY", "1.0")
    assert _ollama_config(build_model())["options"]["repeat_penalty"] == 1.0


def test_seed_and_temperature_are_off_unless_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLANNER_LAB_LLM_SEED", raising=False)
    monkeypatch.delenv("PLANNER_LAB_LLM_TEMPERATURE", raising=False)
    config = _ollama_config(build_model())
    assert "seed" not in config["options"]
    assert config.get("temperature") is None


def test_seed_and_temperature_plumb_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reproducible eval run needs both; neither may perturb normal use."""
    monkeypatch.setenv("PLANNER_LAB_LLM_SEED", "42")
    monkeypatch.setenv("PLANNER_LAB_LLM_TEMPERATURE", "0")
    config = _ollama_config(build_model())
    assert config["options"]["seed"] == 42
    assert config["temperature"] == 0.0
