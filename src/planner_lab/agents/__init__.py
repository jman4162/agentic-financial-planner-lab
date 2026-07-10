"""LLM-facing layer. Requires the 'agent' extra."""

try:
    import strands  # noqa: F401
except ImportError as e:  # pragma: no cover
    raise ImportError("planner_lab.agents requires the 'agent' extra: uv sync --extra agent") from e
