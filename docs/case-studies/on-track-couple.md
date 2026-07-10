# Case study: an on-track couple, full analysis

A synthetic couple in their early fifties asks: *"Can we retire at 62 while spending $60,000 a year?"* Their case file is [`examples/cases/sample_household.yaml`](../../examples/cases/sample_household.yaml): $980,000 investable across taxable, pre-tax, and Roth accounts, $50,000 annual savings, a 70/25/5 portfolio, and a $180,000 mortgage.

## The run

```bash
uv sync --all-extras
PLANNER_LAB_RESEARCH_MCP_URL=<your research server> \
  uv run planner-lab memo examples/cases/sample_household.yaml \
  -o memo.md --yes --simulate --health --allocation --research
```

One command exercises every engine:

1. The three assumption sets (base, conservative, optimistic) are shown and confirmed (`--yes` accepts them non-interactively).
2. Deterministic calculators run under each set: funded ratio, years to financial independence, sustainable spending.
3. The Monte Carlo adapter simulates each set (2,000 seeded paths), plus crash and sequence-risk stress runs on the base set.
4. The fundedness metric computes the certainty-equivalent funded ratio (CEFR) with tax, liquidity, and reliability haircuts.
5. The lifecycle engine computes a model-implied benchmark stock share, framed strictly as a diagnostic comparison.
6. The research adapter searches the configured library, fetches the top guides, and records them in the ledger.
7. The LLM drafts the memo from a menu of recorded numbers; the critic gate approves or rejects it.

## The memo

The full generated output is checked in verbatim: [`on-track-couple-memo.md`](on-track-couple-memo.md). It was drafted by a local 8B-class model (qwen3 via Ollama) and approved by the critic on this run. Things to notice:

- Every bolded number in sections 2, 4, and 5 also appears in the Verification footer with a `source_id` like `ledger:sim:run_simulation:0010#success_probability`. Each id resolves to a recorded computation with its inputs, or the critic would have rejected the memo.
- Section 9 cites two guides fetched from the research library by slug. The critic verified each citation against the ledger's fetch records; the model cannot cite a document that was never retrieved.
- The allocation discussion compares the current 70% stock weight with the model benchmark without telling the reader to trade. A dedicated critic check flags imperative allocation language.
- The prose is honest small-model prose. The system's guarantee is not eloquence; it is that no number was invented.

## Reading the audit

`planner-lab memo` also writes a `.audit.json` sidecar with the complete computation ledger, the memo as structured data, and every critic check with its evidence. To check any figure by hand, find its `source_id` in the footer, look up the ledger entry, and rerun the calculator with the recorded inputs.
