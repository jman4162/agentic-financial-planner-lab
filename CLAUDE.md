# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --extra agent --extra planning --extra dev    # full install
uv run pytest                          # run tests (offline; live tests are opt-in marks)
uv run pytest tests/test_x.py::test_y  # run a single test
uv run pytest -m ollama                # live tests against local Ollama (excluded by default)
uv run ruff check . && uv run ruff format --check .   # lint/format
uv run mypy                            # type check (strict)
uv run planner-lab validate examples/cases/sample_household.yaml
uv run planner-lab memo examples/cases/sample_household.yaml -o memo.md --yes  # needs Ollama
uv run planner-lab analyze examples/cases/sample_household.yaml --simulate --health --allocation \
  --ss-comparison --spending-policy vpw --compare-spending-policies --sensitivity --yes
uv run planner-lab import-cashflow examples/data/sample_transactions_monarch.csv --format monarch
uv run python evals/run_evals.py       # golden evals against the local model (slow; writes report)
bash scripts/slopcheck.sh              # AI-slop lint on public prose (see Writing style)
```

The package lives in `src/planner_lab/` (src layout, hatchling). Dependencies are grouped as optional extras in `pyproject.toml` (`agent`, `planning`, `portfolio`, `mcp`, `dev`); the core must install, import, and pass its tests with no extras (pipeline/hook tests need `agent`; `test_adapter_*` files skip when their package is absent). `--research` needs the `PLANNER_LAB_RESEARCH_MCP_URL` env var; that URL lives only in the environment, never in code or docs.

Known environment quirk: this repo lives under `~/Documents`, and macOS file syncing sometimes marks new `.venv` files with the BSD `hidden` flag, which makes Python skip the editable-install `.pth` file (`ModuleNotFoundError: planner_lab`). Fix: `chflags -R nohidden .venv` and delete any `*.pth` duplicates with ` 2`/` 3` suffixes in `site-packages`.

## Project status

Built: schemas (including guaranteed-income streams and per-asset-class assumptions), calculators, traceability ledger, deterministic critic (ten checks, including prose dollar/percent verification), memo renderer, CLI (`validate`/`calc`/`analyze`/`memo`/`intake`/`import-cashflow`), agent pipeline with exactly two LLM call sites (memo writer, LLM critic), compliance hooks, Monte Carlo simulation adapter (multi-asset, spending policies, sensitivity, SS claiming comparison, goal outflow events), generic MCP research adapter with citation enforcement, CEFR health metric with income-netted liability segments, lifecycle allocation diagnostics (comparisons, never instructions), a stdlib CSV cash-flow importer, and a golden eval harness (`evals/`) with a nightly CI job running a real local model. Deferred: taxes/RMD/Roth conversions, additional model providers, Streamlit demo, historical backtesting.

## What this project is

An experimental, provider-neutral Python framework for auditable personal-finance planning agents: it turns a user's question into a structured household case file, runs deterministic calculators and simulations against it, passes results through a critic/verifier, and emits a planning memo with explicit assumptions, citations, and an educational disclaimer.

It is not a financial advisor. It does not execute trades, give individualized securities advice ("buy/sell X"), or pick stocks.

## Core design rules

These are architectural invariants, not suggestions:

1. **The LLM never does math.** LLMs handle orchestration, question-asking, tool selection, and explanation. All arithmetic (simulations, tax math, withdrawal rates, funded ratios, portfolio metrics) comes from deterministic, seeded, testable functions the agent calls as tools.
2. **Everything flows through a typed case file.** Household facts, goals, balance sheet, cash flow, portfolio, assumptions, and constraints live in a Pydantic model, not loose chat history. Every number in an output memo must be traceable to a case-file input or a calculator result.
3. **Assumptions are explicit.** The assumption builder produces labeled base / conservative / optimistic sets and surfaces them before simulations run. Never silently pick optimistic assumptions.
4. **A critic/verifier stage is mandatory** before any memo is emitted: numbers traceable, citations present, no individualized securities advice, no nominal/real confusion, certainty not overstated, missing material inputs flagged.
5. **Integrations are optional adapters behind generic Protocol interfaces** (`ScenarioSimulator`, `ResearchSource`, `FinancialHealthMetric`, `CashflowImporter`, `PortfolioAnalyticsEngine`). Core workflow must run with no adapter installed; no specific commercial product or third-party account is ever required, and no adapter's name leaks into core classes, schemas, prompts, or diagrams.
6. **Examples and docs use synthetic households only.** Never commit real financial data.

## Intended architecture

```
User question
  → Intake (classify task, ask high-value missing-field questions)
  → Case file builder (typed Pydantic model)
  → Optional data importers (generic CSV first; budgeting exports, ledgers as adapters)
  → Assumption builder (base / conservative / optimistic)
  → Deterministic engines (Monte Carlo simulation, tax models, portfolio diagnostics)
  → Optional research/citation sources (MCP-based, read-only)
  → Critic / verifier
  → Cited planning memo (exec summary, inputs, missing data, base + stress results,
    risks, trade-offs, next questions, methodology, disclaimer)
```

Agent topology: single orchestrator with specialist sub-agents (intake, ingestion, assumptions, simulation, research, tax/account location, portfolio risk, critic, report writer), not a decentralized swarm.

Planned stack: Strands Agents SDK for the agent layer (swap-friendly interface in case LangGraph is needed later for durable/resumable state), OpenTelemetry for tracing, Typer/Rich for CLI, optional local-first LLM via Ollama. Dependencies are grouped as optional extras in `pyproject.toml` (e.g. `agent`, `mcp`, `planning`, `imports`, `market-data`, `portfolio`, `dev`) so the core installs lean.

Planned dev tooling: pytest + hypothesis for tests, ruff for lint/format, mypy for types. Simulation code must be deterministic under a fixed seed so results are regression-testable.

## Scope guardrails

- Portfolio analysis addresses structure (allocation mix, concentration, fees, factor tilts, sequence risk). It never covers security selection or trade timing.
- Optimization libraries (mean-variance etc.) are diagnostics and educational examples, not recommendation engines.
- Market-data integrations fetch neutral series (asset-class returns, yields, inflation), never stock screens.
- Prefer user-controlled file imports (CSV, plain-text ledgers) over live account aggregation.

## Writing style for public-facing prose

Applies to README, docs, docstrings, example output, commit messages, and PR text.

- **Required pre-publish slop check.** Before committing new or substantially rewritten public prose, run `bash scripts/slopcheck.sh` (or pass explicit files). It runs two local, no-network linters: `slopscore-lint` (0-100 SlopScore with evidence spans) and `slopless` (rule findings). Both flag patterns, not authorship. Review findings by hand; do not auto-apply. Fix true positives, ignore deliberate house style. Advisory by default; `--strict` exits non-zero on high-severity findings for CI. The script auto-creates a venv at `scripts/.slopvenv` (gitignored) and never scans `*.local.md`.
- **No em dashes** in public prose. Use commas, periods, or semicolons.
- **No corrective-contrast framing.** Avoid "X is not Y, it is Z" / "It's not just X, it's Y" couplets and "X, not Y" section headings. State the strong version directly; the strawman rarely adds value.
- **No puffery or significance narration.** State results; do not narrate their importance ("this is powerful because...", "crucially...").
- **No formulaic-preamble emphasizers.** No "Importantly:", "Notably:", "At its core...", "Ultimately..." as sentence openers.
- **No meta-narration.** No "This guide covers..." / "We'll explore..."; readers can see the headings.
- **No hyperbolic insight-claiming.** No "Here's the thing..." / "What most people miss..." setups.
- **Avoid reflexive AI vocabulary:** delve, crucial, pivotal, robust, seamless, leverage, showcase, underscore, tapestry, vibrant. Prefer specific, concrete, falsifiable wording.
- Reference: [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).

## Local files

Files matching `*.local.md` are private working notes and are gitignored. Never commit them or copy their contents into committed files. Read `background-info.local.md` for the full design discussion behind this document.
