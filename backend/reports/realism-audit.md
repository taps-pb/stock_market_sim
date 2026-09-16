# Profitability and realism audit

The user's concern was justified. The original market supplied persistent,
exploitable behavior. The audit found **no direct lookahead feature or artificial
cash credit**, but it did find unrealistic participant behavior and a broken
randomness boundary in policy comparisons. A high profitable-run count alone
cannot distinguish these causes.

The current market is v4. Its frozen evaluation produced **19 profitable and
5 losing Atlas accounts across 24 runs**, with all agent positions closed.
Average net return was **+0.94%**, worst result **−$2,274.99**. This removes the
observed absence of losing runs; it does not establish real-market realism.

## What the original 23/24 actually represented

At audit start, SQLite contained 25 records: 24 completed and one interrupted.
Of the completed runs, 23 were profitable; the other was a deliberately disabled
agent with no fills and zero return. Several reused seeds 42 and 101–103, and
some were finished early. They were not 24 independent market trials.

There were individual trading losses: 197 of 1,841 closed round trips lost
money, 1,643 won, and one was within half a cent of flat. These counts include
repeated runs. Positive total results can coexist with losing trades, but their
consistency still warranted investigation.

## Leakage and accounting checks

- **Causal features:** only lagged prices, current public book/flow, and published
  valuation enter the model. Future prices, target returns, seed, tick, actual
  emotions, institutional phases, and live intrinsic values are excluded.
- **Hidden-state mutation:** multiplying unpublished fundamentals and changing
  every trader's fear, greed, and campaign phase leaves live input vectors
  bit-for-bit unchanged.
- **Held-out outcome mutation:** replacing all test outcomes leaves classifier
  predictions, return forecasts, and calibrated intervals unchanged. Complete
  seeds separate fitting, calibration, and test sets.
- **Timing:** a tick-t decision executes at t+1 through the shared order book.
  Tests cover partial fills, failed fills, costs, reservations, and no shorting.
- **Cash:** independently reconstructed round-trip P&L reconciles to final cash
  for fully closed accounts. Fees have a counterparty at the exchange. Cash
  plus exchange fees and net shares remain conserved.
- **Actual bug:** orders, fundamentals, and news consumed the same RNG stream.
  Different policy order counts therefore changed later external news draws.
  This was a comparison-confounding bug, not evidence of future labels entering
  the predictor. Fundamentals/news now use their own seeded stream. A regression
  check proves they remain identical when an extra policy order is submitted
  every tick.

These checks cover identified paths; they are not a proof that every possible
modeling or evaluation bias has been eliminated.

## Model-free controls

Each strategy used the same funded account, policy risk limits, execution delay,
fees, and finite liquidity. Controls see only current prices/history or an
independent random draw. They were run on development seeds 301–303 for 1,500
trading ticks, and were not added to the dashboard as Atlas performance.

| Policy | Original v2 mean return | Current v4 mean return |
|---|---:|---:|
| Trained model | +1.925% | +1.240% |
| 20-tick momentum, no ML | −0.548% | −5.583% |
| Random directional signals | −8.103% | −8.297% |
| Always buy when funded | −7.714% | −8.302% |

Source files: [v2 controls and model](realism-audit-v2.json),
[v4 controls](realism-controls-v4.json), [v4 model](realism-model-v4.json).
Random and always-buy controls often hit their drawdown trigger. Losses beyond
8% are possible because a trigger cannot guarantee an exit fill price.
The positive model results and negative controls rule out a universal profit
credit. They do not, by themselves, prove real-world predictive skill.

## Structural problems and corrections

1. All institutions started flat in accumulation, creating common early demand
   and repetitive campaigns. They now start with inventory, randomized phases,
   and clocks scaled by their individual horizons.
2. Market makers anchored quotes almost entirely to the last print, even under
   obvious persistent pressure. Three competing makers per stock now maintain
   noisy current valuation estimates and account for inventory and volatility.
   These are imperfect current signals; they contain no future information.
3. A weighted fractional-return score was compared with a **0.15** threshold.
   Professionals therefore ignored substantial mispricing. The threshold is now
   **0.005** (50 basis points of weighted score), and the whale behavior test
   now requires an actual dip purchase rather than merely absence of selling.
4. Makers kept quoting tiny fixed quantities even when opposing offers were far
   from their reservation values. They can now commit up to 10% of their capital
   to sufficiently mispriced quotes, within inventory and cash limits. This adds
   competition for opportunities before Atlas can repeatedly harvest them.
5. A noise trader's unfunded sell intention was changed into a buy. It now abstains.
6. An old test required institutions to profit relative to retail. It was replaced
   with a test of asynchronous campaign behavior and actual two-sided trading.
   No category is required to win, and no loss probability or P&L adjustment was
   added to the simulator.

A v3 candidate applied the first two changes but **failed**: Atlas earned even
more. Actual execution traces showed purchases such as ATLS at $37.42 followed
by sales near $42.48, while sophisticated counterparties left that discrepancy
untouched. That evidence motivated the professional-response and sizing fixes.
The candidate was rejected as an adequate solution. Its [24-run results](agent-evaluation-v3.json),
[diagnostics](realism-model-v3.json), model in `../ml/archive/model-v3.pkl`, and
[engine patch](candidate-v3.patch) are retained. The patch is relative to baseline
commit `8fdceecf86c3e8d8f95fc4ed7d3a08cb704c4341`.

## Price-dynamics diagnostics

Means across six symbols and three model-driven development runs:

| Measure | v2 | v4 |
|---|---:|---:|
| Same sign in consecutive 20-tick windows | 82.0% | 59.9% |
| 20-tick variance ratio | 2.891 | 0.961 |
| One-tick return autocorrelation | 0.015 | −0.252 |
| Absolute-return autocorrelation | 0.024 | 0.250 |
| Zero-return fraction | 62.0% | 52.4% |
| Excess kurtosis | 9.2 | 133.9 |

The old market's persistent multi-tick direction was easy to exploit. V4 has
less persistent direction and stronger volatility clustering, but also strong
negative one-tick dependence, many zero returns, and extreme tails. These are
remaining calibration issues, not signs that the simulator is now validated.
Ticks do not have a fixed real-world sampling interval, so no empirical pass
threshold is asserted here.

For the methodological distinction between return dependence, volatility
clustering, and heavy tails, see [Cont's empirical review](https://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf).
Persistent order flow need not imply similarly persistent returns when liquidity
providers adapt; see [Bouchaud et al.](https://arxiv.org/abs/cond-mat/0406224).
These papers motivate diagnostics, not the claim that these hand-set parameters
match a particular exchange or stock.

## Retraining and final evaluation

V4 generated a new 140,208-row dataset. The model fit seeds 1–5, calibrated on 6,
and was tested on 7–8. Held-out direction accuracy is **69.5%**, versus **87.3%**
under v2. Price MAE is **$0.868**, versus **$0.989** for unchanged price. Nominal
80% interval coverage is **79.6%**. The separate one-share quote replay loses
$8.14 net and wins 52.1% of trades. Forecast accuracy is not a trading win rate.

After these choices were fixed, eight new seeds (501–508) were each run in
balanced, volatile, and retail-heavy environments. No market or policy
parameter was adjusted after seeing those final results. The
[complete funded report](agent-evaluation.md) lists all 24 outcomes and exact
run IDs. Two benchmarks retained inventory; Atlas's own realized loss in one
of those runs still counts. Comparison statistics use the 22 fully liquidated
pairs, while agent statistics use all 24 closed Atlas accounts.

The history page now labels market versions, scopes counts to the current
model, shows profit/loss/flat and distinct seeds, and identifies unliquidated
benchmark stock. Old and rejected results stay in SQLite; they are not pooled
into the current model's success count.

## Reproduce the checks

From `backend/`, using the existing virtual environment:

```bash
OMP_NUM_THREADS=1 python -m ml.record --seeds 8 --ticks 3000 --out ml/data/dataset-v4.csv
OMP_NUM_THREADS=1 python -m ml.train --data ml/data/dataset-v4.csv --save ml/model.pkl
OMP_NUM_THREADS=1 python -m app.audit
OMP_NUM_THREADS=1 python -m app.evaluate --seeds 501 502 503 504 505 506 507 508 --scenarios balanced volatile retail
OMP_NUM_THREADS=1 python -m pytest tests -q
```

Old artifacts are archived, and loading them into the changed simulator is
rejected. Reproducing old outcomes requires their old engine version. Final
validation includes 29 backend tests, frontend build/lifecycle checks, and
live API/UI inspection. Real-price/volume calibration, heterogeneous information
latency, margin/borrow/default handling, and longer independent market samples
remain necessary for stronger realism claims.
