# Project context

Market Lab is now a funded-agent trading arena. The main question is whether
Atlas turns its starting cash into more cash, after real simulated execution
costs, and whether it beats an equally funded buy-and-hold account. Setup and
measured results are in [README.md](README.md).

## Execution flow

`runtime` owns one `Arena`, its `Predictor`, and a SQLite `RunStore`. The same
`Arena` drives browser experiments and `python -m app.evaluate`.

At tick t, the predictor updates from causal public market observations.
`plan_orders` receives only a small quote view, forecasts, the account's own
portfolio, holding ages, and risk settings. It has no engine reference. Plans
enter `SimEngine.step` at t+1, shuffled with NPC orders before matching. No
agent fills are inferred from chart prices or replayed quotes.

All entry paths converge on `SimEngine._submit`. It reserves outstanding cash
and shares, checks executable market-buy costs including fees, and prevents
unfunded human/retail purchases and shorts. Price-time matching supports partial
fills, self-trade prevention, and immediate-or-cancel orders. Cancelled or
unfilled IOC residuals never remain reserved. Existing human GTC limits and
bounded institutional shorts remain supported.

Atlas and HOLD are inert funded accounts in `engine.by_id`, separate from the
NPC decision loop and USER. Fees and closed-position P&L are booked at each
fill. Their ledgers are the source for trade counts, decision execution results,
position cost, realized/unrealized P&L, and equity. News also has finite cash and
shares. Cash plus exchange fees and total net shares are conserved.

Both benchmark and Atlas receive equal capital. Benchmark buys equal target
allocations with the same exposure budget, delayed entry, and liquidity limits;
it does not use forecast ranking or rebalance after building its allocation.
Cash is a flat third reference line. Shared exchange participation means neither
benchmark is a counterfactual market without the other account's impact.

## Lifecycle and persistence

A run is running, paused, settling, completed, failed, or interrupted. Trading
starts after 60 warmup ticks. Pause preserves pending plans without advancing
matching; manual submissions are rejected while not running. A drawdown breach
or manual agent stop permanently prevents new Atlas buys and queues real exits.

After the requested duration or Finish, both accounts attempt liquidation for
up to 100 ticks. If bids never return, completed results retain inventory and
are labelled accordingly. Marked equity and current-depth liquidation estimates
are distinct; insufficient exit depth produces no full liquidation estimate.
Entry exposure caps and stop triggers cannot guarantee future marked exposure,
a stop fill price, or a maximum loss.

SQLite stores one complete result document per UUID, idempotently. Saved results
include settings, full engine configuration, simulator/policy versions, model
fingerprint, sampled equity curve, full decisions/Atlas fills, and manual fills.
The list endpoint paginates all runs (30 per page by default), supports kind filters,
and returns items and total count; full results are available by ID.
Graceful shutdown archives an active run as interrupted. Live engine state is
in memory; hard kills can lose the unfinished run, and restarts do not resume it.

REST and the simulation loop share one asyncio event loop. Mutating routes do
not yield during engine operations. WebSocket sends have timeouts and explicit
disconnect cleanup. This is a single local workspace, not a multi-user service.

## Forecasting and information boundaries

The current version-4 simulator model uses observable price lags, volatility, momentum,
book imbalance, microprice, signed flow, quote availability, and published
valuation. It estimates forward return quantiles and up/non-up probability.
Hidden live value, emotions, inventories, and campaign phases are excluded;
participant insights in the interface are explicitly observer-only. Market makers
receive noisy current valuation signals, not future values. Their beliefs are
not visible to the model. The simulator
therefore remains an information model with assumed signal quality, not a
calibrated reconstruction of a real venue.

Data recording labels exact future ticks. Whole seeds separate training,
calibration, and test markets. Calibration observations are spaced by the
forecast horizon; the fitted model is not refit on held-out seeds. Live scoring
waits for outcomes to mature and handles duplicate/missing ticks. Fingerprints
identify the exact model used in each funded experiment.

The old one-share forecast replay remains a diagnostic in `ml/report.md`.
Funded performance now comes from the actual matching engine, with finite
capital, delayed orders, market impact, fees, partial fills, and closing trades.
Changing the policy or benchmark submission order can change a seeded market
price path because all accounts interact. Fundamentals and news now have an
independent random stream: those external draws remain fixed across policies. Compare reports with their exact
settings, model, and code; a seed alone does not identify an experiment.

## Interface and validation

The React workspace has four views: live arena, market participants, run history,
and manual trading desk. A native dialog funds new experiments. Equity/return
charts compare Atlas, buy-and-hold, and cash. Candles, forecasts, depth, news,
positions, and an execution journal explain the account's result. Saved runs
can be inspected and exported as JSON. Desktop and 390-pixel mobile layouts
were checked in Chrome, including funding, pause, speed, finish, stock switching,
and archive inspection.

The implementation passes 41 backend tests, the WebSocket lifecycle
check, and the TypeScript/Vite production build. Tests include next-tick timing,
resource conservation, IOC handling, account P&L, deterministic runs, risk
stops, and stranded inventory. Backend dependencies are pinned exactly; CI runs backend tests, frontend tests, and the build. Tests now also prove that changing
hidden state cannot alter live features, changing test outcomes cannot alter
the fitted model, and changing order counts cannot alter external news.

## Historical replay

`app/replay.py` owns CSV validation, normalized content fingerprints, chronological
training/calibration, and `HistoricalArena`. It shares runtime controls and the
SQLite archive with synthetic runs but never creates an order book. Price features
are shared through `ml.features.price_row`; both frozen models receive only causal
vectors, never symbols, calendar dates, or future bars. Missing simulator inputs
are explicitly zero in the transfer baseline.

Dataset-wide date boundaries enforce 70/15/15 splits with purged 20-session targets
and embargoes. The replay seed selects a symbol and contiguous test window. The
chart reveals 59 context bars plus one bar per step. Forecasts are recorded daily;
headline metrics and the one-share paper strategy use non-overlapping checkpoints.
Incomplete horizons and open inventory remain visible when the run ends. Models
are fitted in a worker thread, and a start guard prevents competing run creations.

The frontend stores historical and synthetic snapshots separately, uses a dedicated
replay view, and disables exchange-only interfaces for replay. Archive pagination
returns `{items,total,limit,offset}`; old rows without a kind are synthetic. The
README documents the CSV contract, API, units, small-sample limits, and reproduction.

## Known realism limits

The market is still highly learnable. Eight final seeds across three regimes are a
small synthetic test, with dependencies across scenarios and symbols. No claim
of real-market accuracy or profitability follows from these results. The
classifier's up probability is not a probability of profitable execution.
Seed-bootstrap intervals put v4 mean return at +0.94% (+0.44% to +1.47%) but
excess over buy-and-hold is not significant (per-seed sign test p = 0.73). Overlapping forecast targets also limit interpretation of sample size.

The next substantive realism work is calibration against measured return tails,
volatility clustering, spreads, depth, and order-flow persistence. Further
extensions can add heterogeneous information delays and competing adaptive
strategies. Institutions currently have bounded short capacity without a full
margin, borrow, or default system. Real exchange calendars, corporate actions,
dividends, and multi-venue execution are not implemented.


## Profitability audit and market v4

The old archive had 23 profitable completed runs and one flat disabled-agent
run. Reused seeds and early-stopped runs made that an invalid independent
24-trial success estimate. Individual round trips did lose money, but profitable
runs were implausibly consistent. The audit found no direct lookahead input;
fresh random, always-buy, and simple momentum controls all lost money.

The simulator supplied exploitable behavior: all institutions began accumulating,
market makers followed stale prints with tiny fixed sizes, and professional
traders ignored moderate mispricing because fractional-return scores were
compared with a 15% threshold. A v3 candidate changed maker valuation and
campaign timing but amplified price-gap arbitrage. Its results are preserved;
it was rejected as an adequate fix.

V4 retains independent exogenous randomness and asynchronous campaigns, lowers
the action threshold to 50 basis points of the weighted score, and lets market
makers commit bounded capital to sufficiently mispriced opposing quotes.
Unfunded noise sell intentions no longer become mandatory buys. The forecast
model was retrained on fresh v4 data using the original train/calibration/test
seed split. Trading-policy thresholds were not tuned to the final outcomes.

## Evaluation statistics and v5 experiments

`app.evaluate` reports seed-bootstrap 95% intervals for mean return and excess
return, plus sign tests per run and per seed mean. `--tune` runs a grid sweep that
raises if any final seed (501–508) is included; score is mean excess return minus
0.5 × mean drawdown. Two v5 changes were evaluated once on the final seeds and not
adopted: Platt calibration (worse Brier on seed 6, lower final return) and the tuned
policy (edge 0 bps, 30% position; neighbouring grid points unstable, more losing runs,
larger worst loss). `reports/agent-evaluation-v5*.json` and `policy-tuning-v5.json`
are records only; the shipped model and `Experiment` defaults remain v4.

`python -m app.audit` runs model-free controls, accounts for winning and losing
round trips, reconciles cash P&L to fills, and measures return dependence and
volatility clustering. Audits and rejected candidates are in `backend/reports/`;
old models are in `backend/ml/archive/`. Tests must not require any trader
category to make money. Realism is not defined as a target loss frequency.
