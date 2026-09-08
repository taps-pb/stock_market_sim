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
The list endpoint returns the latest 30; full results are available by ID.
Graceful shutdown archives an active run as interrupted. Live engine state is
in memory; hard kills can lose the unfinished run, and restarts do not resume it.

REST and the simulation loop share one asyncio event loop. Mutating routes do
not yield during engine operations. WebSocket sends have timeouts and explicit
disconnect cleanup. This is a single local workspace, not a multi-user service.

## Forecasting and information boundaries

The existing version-2 model uses observable price lags, volatility, momentum,
book imbalance, microprice, signed flow, quote availability, and published
valuation. It estimates forward return quantiles and up/non-up probability.
Hidden live value, emotions, inventories, and campaign phases are excluded;
participant insights in the interface are explicitly observer-only.

Data recording labels exact future ticks. Whole seeds separate training,
calibration, and test markets. Calibration observations are spaced by the
forecast horizon; the fitted model is not refit on held-out seeds. Live scoring
waits for outcomes to mature and handles duplicate/missing ticks. Fingerprints
identify the exact model used in each funded experiment.

The old one-share forecast replay remains a diagnostic in `ml/report.md`.
Funded performance now comes from the actual matching engine, with finite
capital, delayed orders, market impact, fees, partial fills, and closing trades.
Changing the policy or even benchmark submission order can change a seeded
market path because all accounts interact. Compare reports with their exact
settings, model, and code; a seed alone does not identify an experiment.

## Interface and validation

The React workspace has four views: live arena, market participants, run history,
and manual trading desk. A native dialog funds new experiments. Equity/return
charts compare Atlas, buy-and-hold, and cash. Candles, forecasts, depth, news,
positions, and an execution journal explain the account's result. Saved runs
can be inspected and exported as JSON. Desktop and 390-pixel mobile layouts
were checked in Chrome, including funding, pause, speed, finish, stock switching,
and archive inspection.

The current implementation passes 26 backend tests, the WebSocket lifecycle
check, and the TypeScript/Vite production build. Tests include next-tick timing,
resource conservation, IOC handling, account P&L, deterministic runs, risk
stops, and stranded inventory. No new runtime dependency was needed.

## Known realism limits

The market is still highly learnable. Three seeds across three regimes are a
small synthetic test, with dependencies across scenarios and symbols. No claim
of real-market accuracy or profitability follows from these results. The
classifier's up probability is not a calibrated probability of profitable
execution. Overlapping forecast targets also limit interpretation of sample size.

The next substantive realism work is calibration against measured return tails,
volatility clustering, spreads, depth, and order-flow persistence. Further
extensions can add heterogeneous information delays and competing adaptive
strategies. Institutions currently have bounded short capacity without a full
margin, borrow, or default system. Real exchange calendars, corporate actions,
dividends, and multi-venue execution are not implemented.
