# Case study: a rejected memo

The most important behavior in this project is the one that produces no output. When the critic gate finds a blocker twice in a row (initial draft plus one revision), `planner-lab memo` exits with an error and writes nothing. This is a real rejection captured during development, running the on-track-couple case with research enabled against a local 8B-class model:

```text
$ planner-lab memo examples/cases/sample_household.yaml -o memo.md --yes --research
Memo rejected by the critic after one revision:
  FAIL numbers_traceable: 2 number(s) failed to trace
    Retirement age: source_id 'case:household.persons[0].planned_retirement_age' does not resolve
    Spending target: source_id 'case:goals[0].annual_amount_today' does not resolve
  FAIL citations_present: citation set inconsistent with fetched research
    research was fetched but the memo cites nothing
  FAIL certainty_not_overstated: [llm] The prose implies certainty about retirement
    feasibility, stating 'retirement at 62 with $60,000 annual spending is feasible
    under the base assumption set' without qualifying this as a probabilistic outcome.
```

Three different guards fired:

1. **`numbers_traceable`** (deterministic): the model cited two real case-file values but with a path syntax the resolver did not accept. No resolution, no memo. This rejection led to two code changes: the resolver now accepts bracket indexing, and material inputs like the retirement age were added to the explicit number menu so the model has no reason to invent paths.
2. **`citations_present`** (deterministic): research documents were fetched and recorded in the ledger, but the draft cited none of them. When research runs, an uncited memo is treated as unfinished work, not a stylistic choice.
3. **`certainty_not_overstated`** (LLM judgment): a second model reviewed the prose and flagged "is feasible" as a promise the underlying simulation does not make. Regex catches the obvious words (guaranteed, risk-free); the LLM check catches tone.

## Why fail loudly

A generated financial document that is 95% right is dangerous in a way a missing document is not: readers cannot tell which 5% to distrust. The pipeline therefore treats verification failures as fatal. The revision loop gives the model exactly one chance to fix the named problems (the critic's findings are appended to the rewrite prompt); after that, the run fails with the full report printed and a nonzero exit code.

In practice, small local models get rejected occasionally and larger models rarely. That variance is contained by design: the worst case is no memo, never a wrong one that reads as verified.
