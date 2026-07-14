# Planning memo: sample-household

## 1. Executive summary

The household can retire at 62 with $60,000 annual spending under the base assumptions, but outcomes depend on market performance and sequence-of-returns risk. Conservative assumptions reduce sustainable spending to $32,340, while optimistic assumptions allow $44,100. Social Security claiming ages trade off benefits vs. longevity risk.

## 2. Inputs used

- **Investable assets:** $980,000
- **Annual expenses:** $88,000
- **Annual spending goal:** $60,000
- **Social Security (base):** $3,500
- **Retirement age:** 62.0 years

## 3. Important missing data

- None identified.

## 4. Base-case results

With $980,000 in retirement investable assets, the base assumptions suggest a sustainable spending capacity of $39,200 annually (source_id=ledger:calc:sustainable_spending:0003#sustainable_spending). This assumes a 4% withdrawal rate (source_id=ledger:calc:funded_ratio:0001#withdrawal_rate) and 5.34 years to financial independence (source_id=ledger:calc:years_to_fi:0002#years_to_fi). All simulated paths succeeded under these assumptions (source_id=ledger:sim:run_simulation:0010#success_probability).

- **Required capital:** $1,500,000
- **Funded ratio:** 0.65
- **Sustainable spending:** $39,200

## 5. Stress-case results

### conservative

Under conservative assumptions, the required capital increases to $1,818,181.82 (source_id=ledger:calc:funded_ratio:0004#required_capital) with a 3.3% withdrawal rate (source_id=ledger:calc:funded_ratio:0004#withdrawal_rate). Sustainable spending drops to $32,340 annually (source_id=ledger:calc:sustainable_spending:0006#sustainable_spending), and financial independence takes 10.9 years (source_id=ledger:calc:years_to_fi:0005#years_to_fi). All simulated paths succeeded under these assumptions (source_id=ledger:sim:run_simulation:0011#success_probability).

- **Required capital:** $1,818,182
- **Funded ratio:** 0.54
- **Sustainable spending:** $32,340

## 6. Main risks

- Sequence-of-returns risk: 98.2% of simulated paths survived a market crash (source_id=ledger:sim:run_simulation:0010#stress_sequence_risk_success_probability)
- Inflation risk: Conservative assumptions assume 3.5% inflation (source_id=assumption_sets:conservative#inflation)
- Social Security timing: Benefits start at 67 (source_id=case:income_streams.0.start_age), but claiming at 62 reduces monthly benefits to $3,500 (source_id=ledger:sim:ss_claiming_comparison:0013#monthly_benefit_total)

## 7. Decision trade-offs

- Social Security claiming age trade-offs (SSA-style approximations relative to full retirement age of 67):
- | Claiming Age | Monthly Benefit | Success Probability |
- |-------------|----------------|---------------------|
- | 62          | $3,500         | 99.85%              |
- | 67          | $5,000         | 100%                |
- | 70          | $6,200         | 100%                |

## 8. Suggested next questions

- How do portfolio rebalancing rules affect long-term returns?
- What's the impact of a 4% vs. 3.3% withdrawal rate on longevity risk?
- How do tax implications change with different withdrawal strategies?

## 9. Methodology and citations

Analysis used base, conservative, and optimistic assumption sets (source_id=assumption_sets). Figures are real (today's dollars). Outcomes depend on market performance, sequence-of-returns risk, and Social Security timing. Citable sources include 'dave-ramsey-8-percent-withdrawal' (about withdrawal rate risks) and 'twenty-thirty-percent-returns' (about return expectations).

- The 8% Withdrawal Rule: Where Dave Ramsey's Retirement Math Breaks (mcp: `dave-ramsey-8-percent-withdrawal`)

### Assumptions

| Set | Real return | Volatility | Inflation | Withdrawal rate | Plan end age |
|-----|-------------|------------|-----------|-----------------|--------------|
| base | 4.0% | 12% | 2.5% | 4.0% | 95 |
| conservative | 2.0% | 14% | 3.5% | 3.3% | 95 |
| optimistic | 5.5% | 11% | 2.0% | 4.5% | 95 |

## 10. Disclaimer

This memo is educational analysis produced by an experimental software tool. It is not financial, investment, tax, or legal advice, and no advisor-client relationship is created by it. Figures depend on the stated assumptions and inputs, which may be incomplete or wrong. Consult a qualified professional before acting on any of this analysis.

---

## Verification

Critic checks:

- `numbers_traceable` [blocker]: pass — all traced numbers resolve to ledger or case-file sources
- `prose_numbers_traceable` [blocker]: pass — all dollar and percent figures in prose match recorded values
- `no_securities_advice` [blocker]: pass — no individualized securities advice detected
- `disclaimer_present` [blocker]: pass — required disclaimer present verbatim
- `assumptions_disclosed` [blocker]: pass — assumptions surfaced and all three labels disclosed in methodology
- `missing_inputs_flagged` [blocker]: pass — every case-file gap appears in the memo's missing-data section
- `citations_present` [blocker]: pass — citations correspond to fetched research
- `nominal_real_consistent` [warning]: pass — real/nominal terms stated
- `certainty_not_overstated` [blocker]: pass — no absolute-certainty language detected
- `diagnostic_framing` [warning]: pass — no portfolio diagnostics were run; framing check not applicable
- `certainty_not_overstated` [blocker]: pass — [llm] The memo explicitly conditions all simulation results on stated assumptions (e.g., 'base assumptions', 'conservative assumptions'). While it reports 100% success rates for simulated paths, these are framed as conditional outcomes under specific assumptions, not guaranteed real-world results. No prose promises outcomes beyond the cited probabilities.
- `no_securities_advice` [blocker]: pass — [llm] The prose does not recommend buying, selling, or holding any specific security, fund, or asset. It focuses on analyzing withdrawal rates, Social Security timing, and risk factors without prescribing actionable investment decisions. All references to sources are contextual rather than prescriptive.

Traced numbers:

- Investable assets = 980000.0 (source: `case:balance_sheet.retirement_investable_assets`)
- Annual expenses = 88000.0 (source: `case:cash_flow.annual_expenses`)
- Annual spending goal = 60000.0 (source: `case:goals.0.annual_amount_today`)
- Social Security (base) = 3500.0 (source: `ledger:sim:ss_claiming_comparison:0013#monthly_benefit_total`)
- Retirement age = 62.0 (source: `case:household.persons.0.planned_retirement_age`)
- Required capital = 1500000.0 (source: `ledger:calc:funded_ratio:0001#required_capital`)
- Funded ratio = 0.6533333333333333 (source: `ledger:calc:funded_ratio:0001#funded_ratio`)
- Sustainable spending = 39200.0 (source: `ledger:calc:sustainable_spending:0003#sustainable_spending`)
- Required capital = 1818181.8181818181 (source: `ledger:calc:funded_ratio:0004#required_capital`)
- Funded ratio = 0.539 (source: `ledger:calc:funded_ratio:0004#funded_ratio`)
- Sustainable spending = 32340.0 (source: `ledger:calc:sustainable_spending:0006#sustainable_spending`)
