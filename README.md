# agentic-financial-planner-lab

An experimental, provider-neutral framework for building auditable personal-finance planning agents: a typed case file, deterministic calculators, a Monte Carlo simulation adapter, cited research through the Model Context Protocol, and a critic gate that blocks any memo whose numbers cannot be traced to a recorded computation.

**Keywords:** financial planning, retirement readiness, Monte Carlo simulation, LLM agents, Model Context Protocol (MCP), funded ratio, safe withdrawal rate, personal finance, FIRE.

The design premise: an LLM is good at asking questions, structuring a case, choosing tools, and explaining trade-offs. It is bad at arithmetic. So this project splits the work:

- **LLM (via [Strands Agents](https://strandsagents.com/)):** intake, orchestration, tool selection, explanation, memo writing.
- **Deterministic code:** every simulation, tax calculation, withdrawal rate, funded ratio, and portfolio metric. Seeded, typed, testable.
- **Case file:** a typed Pydantic model holding household facts, goals, balance sheet, cash flow, portfolio, and labeled assumptions. Every number in an output memo traces back to a case-file input or a calculator result.
- **Critic stage:** before a memo is emitted, a verifier checks that numbers are traceable, citations are present, assumptions are disclosed, and the output contains no individualized securities advice.

This is a research and education project. It is not a financial advisor, does not execute trades, does not pick stocks, and does not require any commercial product or account. Examples use synthetic households only.

## Install

Requires Python 3.11+.

```bash
uv sync --extra agent --extra dev
```

Or with pip:

```bash
pip install -e ".[agent,dev]"
```

Extras are optional by design. The core installs without any agent framework; `agent` adds the Strands SDK (with Ollama and OpenTelemetry support), `mcp` adds Model Context Protocol clients for research sources.

## Try it

The core works offline with no LLM:

```bash
uv run planner-lab validate examples/cases/sample_household.yaml
uv run planner-lab calc funded-ratio --portfolio 900000 --spending 50000
uv run planner-lab calc fi-timeline --portfolio 250000 --savings 50000 --spending 60000
```

With a local [Ollama](https://ollama.com/) server running and a tool-calling-capable model pulled (default `qwen3`; override with `OLLAMA_MODEL`):

```bash
# Full pipeline: assumptions -> calculators -> memo draft -> critic gate -> memo
uv run planner-lab memo examples/cases/sample_household.yaml -o memo.md --yes

# Add Monte Carlo simulation, the fundedness metric, and allocation diagnostics
uv sync --all-extras
uv run planner-lab analyze examples/cases/sample_household.yaml --simulate --health --allocation --yes

# Ground the memo's methodology in cited guides from an MCP research server
PLANNER_LAB_RESEARCH_MCP_URL=https://example.com/mcp \
  uv run planner-lab memo examples/cases/sample_household.yaml -o memo.md --yes --research

# Derive annual cash flow from a budgeting-app CSV export (no LLM involved)
uv run planner-lab import-cashflow examples/data/sample_transactions_monarch.csv \
  --format monarch --case my_case.yaml --write

# Interactive intake chat that builds a case file
uv run planner-lab intake -o my_case.yaml

# Minimal agent-plus-tool example
uv run python examples/hello_agent.py
```

The memo command writes the markdown memo plus a `.audit.json` sidecar holding the full computation ledger and critic report, so every number can be checked by hand. If the critic rejects the draft twice, no memo is written and the failing checks are printed.

## How a run works

1. The case file is loaded and validated; material gaps are recorded.
2. Base, conservative, and optimistic assumption sets are shown for confirmation (`--yes` accepts them non-interactively). Rates are real, after inflation.
3. Deterministic calculators run per assumption set: funded ratio, years to financial independence, sustainable spending. Each result lands in the computation ledger with an id.
4. Optionally, a Monte Carlo engine simulates each set (plus crash and sequence-risk stress runs) behind a generic `ScenarioSimulator` interface.
5. The LLM drafts the memo, citing numbers only from the ledger menu it is given.
6. The critic runs eight deterministic checks (traceability, no securities advice, disclaimer, assumption disclosure, missing-data disclosure, citation consistency, real/nominal labeling, certainty language) plus an LLM tone review. One revision is attempted; then the run fails.

## Configuration

Everything is configured through environment variables; nothing is hardcoded.

| Variable | Purpose | Default |
|---|---|---|
| `PLANNER_LAB_MODEL_PROVIDER` | `ollama` or `bedrock` | `ollama` |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local model server and model id | `http://localhost:11434` / `qwen3` |
| `PLANNER_LAB_BEDROCK_MODEL` | Bedrock model id (provider `bedrock`) | provider default |
| `PLANNER_LAB_RESEARCH_MCP_URL` | Streamable-HTTP MCP server exposing `search` and `fetch` tools; enables `--research` | unset |
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` | OTLP tracing target for `setup_telemetry("otlp")`; `--trace` prints spans to stdout | unset |

Small local models occasionally mis-copy a number or skip a citation; the critic then rejects the memo after one revision attempt rather than emitting it. A larger model (for example `OLLAMA_MODEL=gpt-oss:20b`) makes full runs with simulation, diagnostics, and research more reliable.

Optional extras: `agent` (LLM pipeline, Strands SDK), `planning` (Monte Carlo simulation, fundedness metric), `portfolio` (lifecycle allocation diagnostics), `mcp` (research sources), `dev` (tests, lint, types). The core installs with none of them.

## Status

Working retirement-readiness pipeline: case-file schemas, deterministic calculators, critic gate, memo renderer, interactive intake, Monte Carlo simulation, certainty-equivalent funded ratio (CEFR) metric, lifecycle allocation diagnostics, MCP research citations, and CSV cash-flow import. See `CLAUDE.md` for architecture rules.

## Citation

```bibtex
@software{hodge_agentic_financial_planner_lab,
  author  = {Hodge, John},
  title   = {agentic-financial-planner-lab: an auditable financial planning agent framework},
  year    = {2026},
  url     = {https://github.com/jman4162/agentic-financial-planner-lab},
  version = {0.1.0},
  license = {MIT}
}
```

## License

MIT. Educational use; nothing here is financial advice.
