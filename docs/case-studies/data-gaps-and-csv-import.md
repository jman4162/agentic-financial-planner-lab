# Case study: data gaps and CSV import

A synthetic 38-year-old asks *"Am I on track for retirement?"* with a thin case file, [`examples/cases/incomplete_household.yaml`](../../examples/cases/incomplete_household.yaml): one pre-tax account, a gross income, and nothing else. This walkthrough shows how the system refuses to paper over what it does not know, and how a transactions CSV fills part of the gap without an LLM anywhere in the loop.

## Step 1: validation names the gaps

```text
$ planner-lab validate riley_case.yaml
Valid case file: incomplete-household
Question: Am I on track for retirement?
Net worth: $95,000
Investable assets: $95,000
Missing material fields:
  - cash_flow.annual_expenses
  - cash_flow.annual_savings
  - goals.retirement.annual_amount_today
  - portfolio
```

These dotted paths follow the case everywhere. The critic gate later requires every one of them to appear in the memo's "Important missing data" section.

## Step 2: derive cash flow from a transactions export

```text
$ planner-lab import-cashflow examples/data/sample_transactions_monarch.csv \
    --format monarch --case riley_case.yaml --write

   Cash flow derived from sample_transactions_monarch.csv
┌────────────────────┬──────────────────────────────────────┐
│ Window             │ 2025-02-01 to 2026-02-01 (exclusive) │
│ Complete months    │ 12                                   │
│ Income (take-home) │ $96,000/yr                           │
│ Expenses           │ $44,949/yr                           │
│ Savings            │ $51,051/yr                           │
│ Excluded transfers │ $48,000/yr                           │
└────────────────────┴──────────────────────────────────────┘

Case file cash flow (current -> imported):
  annual_take_home: unset -> $96,000
  annual_expenses: unset -> $44,949
  annual_savings: unset -> $51,051
Case file updated: riley_case.yaml
```

The importer is stdlib code with a column-mapping preset per export format. Note the excluded-transfers line: $48,000 of credit-card payments and brokerage transfers were kept out of income and expenses, because counting them would double-count spending that was already recorded at the merchant level. The window is the last 12 complete calendar months; shorter exports are annualized with an explicit warning.

## Step 3: the remaining gaps stay visible

```text
$ planner-lab validate riley_case.yaml
Missing material fields:
  - goals.retirement.annual_amount_today
  - portfolio
```

The cash-flow gaps cleared because the data now exists; the portfolio and the retirement spending target still need the human. Running the memo pipeline now produces [`data-gaps-memo.md`](data-gaps-memo.md), whose "Important missing data" section carries both remaining paths (the critic blocks the memo if it does not) and whose analysis leans on the expense figure as the spending proxy, labeled as such.

## Why this matters

A planning answer computed from unstated guesses is worse than no answer. The pipeline's rule is that gaps are data: they are recorded in the case file, disclosed in the memo, and enforced by a deterministic check rather than by hoping the model mentions them.
