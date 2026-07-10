# Planning memo: incomplete-household

## 1. Executive summary

Current retirement readiness is uncertain due to incomplete data, but analysis under three scenarios suggests significant gaps. The base case indicates a funded ratio of 8.45% with $1.12M required capital, while conservative and optimistic scenarios show even greater shortfalls. Additional data is needed to refine projections.

## 2. Inputs used

- **Annual Savings:** $51,051
- **Investable Assets:** $95,000
- **Annual Expenses:** $44,949
- **Net Worth:** $95,000

## 3. Important missing data

- goals.retirement.annual_amount_today
- portfolio

## 4. Base-case results

Using base assumptions (4% real return, 2.5% inflation, 4% safe withdrawal rate), the funded ratio is 8.45% (source_id=ledger:calc:funded_ratio:0001#funded_ratio). Required capital is $1,123,718 (source_id=ledger:calc:funded_ratio:0001#required_capital). To achieve a sustainable $3,800/month withdrawal (source_id=ledger:calc:sustainable_spending:0003#sustainable_spending), 14.27 years of saving would be needed (source_id=ledger:calc:years_to_fi:0002#years_to_fi).

- **Funded Ratio:** 0.08
- **Required Capital:** $1,123,718
- **Withdrawal Rate:** 0.04
- **Years to FI:** 14.3 years
- **Sustainable Spending:** $3,800

## 5. Stress-case results

### conservative

Under conservative assumptions (2% real return, 3.5% inflation, 3.3% safe withdrawal rate), the funded ratio drops to 6.97% (source_id=ledger:calc:funded_ratio:0004#funded_ratio). Required capital increases to $1,362,082.42 (source_id=ledger:calc:funded_ratio:0004#required_capital). Sustainable spending declines to $3,135/month (source_id=ledger:calc:sustainable_spending:0006#sustainable_spending), requiring 19.75 years of saving (source_id=ledger:calc:years_to_fi:0005#years_to_fi).

- **Funded Ratio:** 0.07
- **Required Capital:** $1,362,082
- **Withdrawal Rate:** 0.03
- **Years to FI:** 19.7 years
- **Sustainable Spending:** $3,135

## 6. Main risks

- Missing retirement income target (goals.retirement.annual_amount_today)
- No portfolio details to assess asset allocation
- Current savings rate may not sustain required capital
- Uncertain retirement age and spending patterns

## 7. Decision trade-offs

- Higher withdrawal rates (optimistic case: 4.5%) require more aggressive assumptions
- Extended years to financial independence (conservative case: 19.75 years)
- Varying required capital ($998k vs. $1.36M vs. $1.12M)
- Sustainable spending ranges from $3,135 to $4,275

## 8. Suggested next questions

- What is the target annual retirement income?
- What are the details of the portfolio?
- What is the planned retirement age?
- What is the desired spending pattern in retirement?

## 9. Methodology and citations

Analysis uses three assumption sets: base (4% real return, 2.5% inflation, 4% safe withdrawal rate), conservative (2% real return, 3.5% inflation, 3.3% safe withdrawal rate), and optimistic (5.5% real return, 2% inflation, 4.5% safe withdrawal rate). All figures are calculated in today's dollars. Outcomes depend on assumptions about market returns, inflation, and spending patterns. The funded ratio calculations assume a 4% withdrawal rate for base and conservative scenarios, and 4.5% for optimistic. Sustainable spending is calculated based on required capital and withdrawal rate. Years to financial independence assumes consistent annual savings of $51,051.28.

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
- `citations_present` [blocker]: pass — no research sources were used; citation check not applicable
- `nominal_real_consistent` [warning]: pass — real/nominal terms stated
- `certainty_not_overstated` [blocker]: pass — no absolute-certainty language detected
- `diagnostic_framing` [warning]: pass — no portfolio diagnostics were run; framing check not applicable
- `certainty_not_overstated` [blocker]: pass — [llm] The prose presents probabilistic outcomes through scenario analysis (base, conservative, optimistic) and explicitly states that 'outcomes depend on assumptions about market returns, inflation, and spending patterns.' It avoids asserting certainty beyond simulation probabilities, instead emphasizing variability and dependency on assumptions.
- `no_securities_advice` [blocker]: pass — [llm] The prose does not recommend buying, selling, or holding specific securities, funds, or assets. It focuses on analyzing assumptions, required capital, and withdrawal rates without mentioning any particular investment vehicles.

Traced numbers:

- Annual Savings = 51051.28 (source: `case:cash_flow.annual_savings`)
- Investable Assets = 95000.0 (source: `case:balance_sheet.investable_assets`)
- Annual Expenses = 44948.72 (source: `case:cash_flow.annual_expenses`)
- Net Worth = 95000.0 (source: `case:balance_sheet.net_worth`)
- Funded Ratio = 0.0845407833637976 (source: `ledger:calc:funded_ratio:0001#funded_ratio`)
- Required Capital = 1123718.0 (source: `ledger:calc:funded_ratio:0001#required_capital`)
- Withdrawal Rate = 0.04 (source: `ledger:calc:funded_ratio:0001#withdrawal_rate`)
- Years to FI = 14.271098703877975 (source: `ledger:calc:years_to_fi:0002#years_to_fi`)
- Sustainable Spending = 3800.0 (source: `ledger:calc:sustainable_spending:0003#sustainable_spending`)
- Funded Ratio = 0.069746146275133 (source: `ledger:calc:funded_ratio:0004#funded_ratio`)
- Required Capital = 1362082.4242424243 (source: `ledger:calc:funded_ratio:0004#required_capital`)
- Withdrawal Rate = 0.033 (source: `ledger:calc:funded_ratio:0004#withdrawal_rate`)
- Years to FI = 19.749149164518446 (source: `ledger:calc:years_to_fi:0005#years_to_fi`)
- Sustainable Spending = 3135.0 (source: `ledger:calc:sustainable_spending:0006#sustainable_spending`)
