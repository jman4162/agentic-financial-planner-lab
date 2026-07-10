# agentic-financial-planner-lab

An experimental, provider-neutral framework for building auditable personal-finance planning agents.

The design premise: an LLM is good at asking questions, structuring a case, choosing tools, and explaining trade-offs. It is bad at arithmetic. So this project splits the work:

- **LLM (via [Strands Agents](https://strandsagents.com/)):** intake, orchestration, tool selection, explanation, memo writing.
- **Deterministic code:** every simulation, tax calculation, withdrawal rate, funded ratio, and portfolio metric. Seeded, typed, testable.
- **Case file:** a typed Pydantic model holding household facts, goals, balance sheet, cash flow, portfolio, and labeled assumptions. Every number in an output memo traces back to a case-file input or a calculator result.
- **Critic stage:** before a memo is emitted, a verifier checks that numbers are traceable, citations are present, assumptions are disclosed, and the output contains no individualized securities advice.

This is a research and education project. It is not a financial advisor, does not execute trades, does not pick stocks, and does not require any commercial product or account. Examples use synthetic households only.

## Install

Requires Python 3.10+.

```bash
uv sync --extra agent --extra dev
```

Or with pip:

```bash
pip install -e ".[agent,dev]"
```

Extras are optional by design. The core installs without any agent framework; `agent` adds the Strands SDK (with Ollama and OpenTelemetry support), `mcp` adds Model Context Protocol clients for research sources.

## Try it

With a local [Ollama](https://ollama.com/) server running and a tool-calling-capable model pulled (default `qwen3`; override with `OLLAMA_MODEL`):

```bash
uv run python examples/hello_agent.py
```

The example wires a Strands agent to one deterministic tool (a funded-ratio calculator) and asks it a planning question. The agent calls the tool for the math and explains the result; it never computes the ratio itself.

## Status

Early scaffolding. The case-file schema, calculators, importers, and critic stage are not built yet. See `CLAUDE.md` for the intended architecture and the rules the codebase follows.

## License

MIT. Educational use; nothing here is financial advice.
