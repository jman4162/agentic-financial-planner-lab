# Eval report

- Date: 2026-07-13
- Model: ollama:qwen3
- planner-lab: 0.2.0
- Python: 3.12.13
- Approval rate: 7/10

A rejection means the critic refused to emit an unverifiable memo,
which is the designed failure mode; the score measures how often the
model produces a memo that survives every deterministic check.

| Case | Simulate | Approved | Failed checks | Ledger breaches | Seconds |
|---|---|---|---|---|---|
| deficit-household | no | yes | - | - | 137.3 |
| education-family | yes | NO | prose_numbers_traceable | - | 384.2 |
| fire-early | yes | yes | - | - | 167.6 |
| minimal-edge | no | yes | - | - | 338.4 |
| near-retiree | yes | yes | - | - | 358.7 |
| no-portfolio | no | yes | - | - | 368.7 |
| on-track-couple | yes | NO | prose_numbers_traceable | - | 411.4 |
| pension-household | yes | NO | prose_numbers_traceable, certainty_not_overstated | - | 397.9 |
| under-saver | no | yes | - | - | 202.2 |
| young-saver | no | yes | - | - | 189.8 |
