# Business Case: AI Compliance Matrix Agent

## The problem

The Firm screens about **612 tenders** a year and submits **94 bids**. Screening
and building compliance matrices costs **$108,888 a year** in coordinator time.

The bigger cost shows up when a requirement is missed:

- In the client's loss log, **two bids failed on compliance**.
- Together they were worth **$3.18M** in contract value.
- The team had already spent **59 hours** on them, including **36 engineering
  hours**.

When a bid fails compliance, the company loses the contract and everything it
put into the bid. Engineering time is the most expensive input:

| Role | Hourly rate |
|---|---:|
| Engineer | $145 |
| Coordinator | $52 |

## Design decision: optimize for recall

That asymmetry drove our design decision. We optimized the agent for **recall**,
meaning it should find every requirement even if it also returns some extra
items.

| Error type | Cost |
|---|---|
| Missed requirement | Can disqualify a bid worth over $1.5M on average, after 18 hours of engineering work |
| Extra, irrelevant item | A few minutes of coordinator time to dismiss |

Given that trade-off, it is far cheaper to over-flag than to miss.

## Test results

**Recall: 100%** (every ground-truth requirement found)

**Precision: 59.1%**

**F1: 0.74**

Every compliance obligation was caught, at the cost of some noise for the
coordinator to review.

## Economics

### Cost and speed per tender

| Measure | Result |
|---|---|
| Model usage cost | About **$2.66** per tender (under the $3 budget) |
| Run time | Under **10 minutes** |
| Coordinator time | From up to **8.5 hours** to a **15-minute** go/no-go review |

### Annual impact

| Measure | Before | After | Change |
|---|---:|---:|---:|
| Screening and matrix cost | $108,888 | $9,792 | **−$99,096 (91%)** |
| Coordinator hours freed | — | — | **1,941 hours** |

### Upside from redeployed engineering time

Engineering hours no longer lost to non-compliant bids can go to new bids. At
the current **24.5% win rate**, that is worth an expected **$522,230 a year** in
new contract value.
