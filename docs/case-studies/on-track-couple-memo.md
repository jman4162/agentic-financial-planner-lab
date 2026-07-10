# Planning memo: sample-household

## 1. Executive summary

The household's retirement goal of $60,000 annual spending at 62 is not achievable under the base, conservative, or optimistic assumption sets. The **cefr** (comprehensive fundedness ratio) of 0.453 indicates significant financial risk, with haircuts for taxes, liquidity, and reliability reducing net assets by 22.8% of gross assets. Sustainable spending under base assumptions is $39,200, below the target. Even in the optimistic scenario, sustainable spending is $44,100, leaving a $15,900 shortfall. Success probabilities range from 30.55% (conservative) to 91.45% (optimistic), but all scenarios require spending cuts to align with portfolio capacity.

## 2. Inputs used

- **Base Case:** 0.65
- **Required Capital (Base):** $1,500,000
- **Sustainable Spending (Base):** $39,200

## 3. Important missing data

- None identified.

## 4. Base-case results

The base scenario assumes a 4% real return, 2.5% inflation, and a 4% safe withdrawal rate. The funded ratio of 0.65 (65% of required $1.5M) suggests the portfolio can only sustain $39,200/year in real terms. The 5.34-year horizon to financial independence (Fi) requires spending cuts or asset growth to meet the $60k target.

- **Funded Ratio:** 0.65
- **Years to Fi:** 5.3 years
- **Sustainable Spending:** $39,200
- **Success Probability:** 68.3%

## 5. Stress-case results

### conservative

The conservative scenario assumes a 2% real return, 3.5% inflation, and a 3.3% withdrawal rate. The funded ratio drops to 0.54 (54% of required $1.82M), limiting sustainable spending to $32,340/year. The 10.9-year horizon to Fi makes the $60k target even more unattainable without significant asset growth or spending reductions.

- **Funded Ratio:** 0.54
- **Years to Fi:** 10.9 years
- **Sustainable Spending:** $32,340
- **Success Probability:** 30.6%

## 6. Main risks

- The **cefr** of 0.453 indicates the portfolio is only 45.3% of the required capital to sustain $60k/year, with haircuts for taxes (22.8k), liquidity (8.36k), and reliability (7.92k) reducing net assets to $629k from $1.02M gross assets.
- The current 70% stock allocation (source_id=ledger:portfolio:portfolio_diagnostics:0016#current_stock_pct) exceeds the alpha_recommended 54.3% (source_id=ledger:portfolio:portfolio_diagnostics:0016#alpha_recommended), but this is a diagnostic model comparison, not an actionable recommendation.

## 7. Decision trade-offs

- The household's $50k annual savings (source_id=case:cash_flow.annual_savings) could bridge the gap if redirected to asset growth, but this would require reducing current expenses ($88k/year, source_id=case:cash_flow.annual_expenses) or increasing income.

## 8. Suggested next questions

- How might the household adjust their retirement age or spending target to align with portfolio capacity?
- What role could part-time work or passive income play in bridging the $15.9k shortfall in the optimistic scenario (source_id=ledger:calc:sustainable_spending:0009#sustainable_spending)?

## 9. Methodology and citations

Analysis uses three assumption sets: base (4% return, 2.5% inflation, 4% withdrawal), conservative (2% return, 3.5% inflation, 3.3% withdrawal), and optimistic (5.5% return, 2% inflation, 4.5% withdrawal). Figures are real (today's dollars) and depend on assumptions. The **cefr** (source_id=ledger:metric:compute_health_metric:0013#cefr) is a composite metric incorporating tax, liquidity, and reliability risks.

- Grow Income Faster Than Expenses: The Underrated Math Behind Wealth and Freedom (mcp: `grow-income-faster-than-expenses`)
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
- `no_securities_advice` [blocker]: pass — no individualized securities advice detected
- `disclaimer_present` [blocker]: pass — required disclaimer present verbatim
- `assumptions_disclosed` [blocker]: pass — assumptions surfaced and all three labels disclosed in methodology
- `missing_inputs_flagged` [blocker]: pass — every case-file gap appears in the memo's missing-data section
- `citations_present` [blocker]: pass — citations correspond to fetched research
- `nominal_real_consistent` [warning]: pass — real/nominal terms stated
- `certainty_not_overstated` [blocker]: pass — no absolute-certainty language detected
- `diagnostic_framing` [warning]: pass — allocation diagnostics framed comparatively
- `certainty_not_overstated` [blocker]: pass — [llm] The prose does not promise or imply certain outcomes beyond citing simulation probabilities. It explicitly states probabilities (e.g., 'success probabilities range from 30.55% to 91.45%') and frames outcomes as dependent on assumptions, without asserting definitive certainty.
- `no_securities_advice` [blocker]: pass — [llm] The prose does not recommend buying, selling, or holding specific securities. It references portfolio allocations and recommendations (e.g., 70% stock vs. 54.3% alpha_recommended) only as diagnostic comparisons, not actionable advice.

Traced numbers:

- Base Case = 0.6533333333333333 (source: `ledger:calc:funded_ratio:0001#funded_ratio`)
- Required Capital (Base) = 1500000.0 (source: `ledger:calc:funded_ratio:0001#required_capital`)
- Sustainable Spending (Base) = 39200.0 (source: `ledger:calc:sustainable_spending:0003#sustainable_spending`)
- Funded Ratio = 0.6533333333333333 (source: `ledger:calc:funded_ratio:0001#funded_ratio`)
- Years to Fi = 5.34409778290625 (source: `ledger:calc:years_to_fi:0002#years_to_fi`)
- Sustainable Spending = 39200.0 (source: `ledger:calc:sustainable_spending:0003#sustainable_spending`)
- Success Probability = 0.6835 (source: `ledger:sim:run_simulation:0010#success_probability`)
- Funded Ratio = 0.539 (source: `ledger:calc:funded_ratio:0004#funded_ratio`)
- Years to Fi = 10.89765217656114 (source: `ledger:calc:years_to_fi:0005#years_to_fi`)
- Sustainable Spending = 32340.0 (source: `ledger:calc:sustainable_spending:0006#sustainable_spending`)
- Success Probability = 0.3055 (source: `ledger:sim:run_simulation:0011#success_probability`)
