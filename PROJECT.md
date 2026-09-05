# Project context

The project is a fictional, trader-driven market and an AI price-forecasting
sandbox. Run instructions are in [README.md](README.md); measured model results
are in [backend/ml/report.md](backend/ml/report.md).

## Current architecture

FastAPI owns one `SimEngine` and one optional `Predictor`. Each tick evolves
fundamentals, expires bot orders, updates trader emotions, collects and shuffles
orders, matches them, applies fills, processes news, then broadcasts a snapshot.
The React app receives snapshots over WebSocket and reads candles/portfolio via
REST. Routes that touch the engine run on the same event loop as simulation
steps, without yielding during mutations.

All trade entry paths pass through `SimEngine._submit`. It reserves outstanding
buy commitments across symbols and sell commitments per symbol, clips bot
orders to their resources, and rejects unaffordable human orders before book
mutation. Market-buy affordability uses a non-mutating sweep quote, including
fees. Self-crossing orders cancel the older resting order without a trade print.

The exchange collects fees. News has its own funded balance sheet, included in
`engine.by_id`, but does not participate in trader decision loops. Institutions
and market makers may short up to configured capacity; ordinary traders and the
human may not. Human limit orders are good until cancelled; bot orders expire.
Open orders and available cash are exposed in the portfolio.

Fundamental innovations combine independent, market, and sector components.
A persistent calm/stress state changes their volatility. Earnings are staggered
across companies. News changes public valuation and sends a funded market order.
Prices still change only through matched trades. Market makers react to observed
return volatility by widening spreads and reducing size.

## Forecasting pipeline

`ml.record` emits one row per symbol/tick after a 60-tick warmup. A row carries
its simulator version, forecast horizon, causal observable features, separately
named oracle features, actual future price/return, and executable quotes for
next-tick entry and horizon exit. Missing quotes remain missing; labels use the
exact tick horizon and never substitute the next available price.

Observable features include lagged returns, volatility, momentum, book and
top-level imbalance, microprice, quote availability, signed flow, and published
valuation. Actual agent fear/greed, campaign phase, institutional inventory and
live intrinsic value belong only to the oracle comparison. Frontend sentiment
and phase badges remain educational access to simulator internals.

`ml.train` uses complete seeds as independent markets. The highest two of the
standard eight seeds are test markets; seed six calibrates intervals; seeds
one through five fit the models. Random early-stopping splits are disabled.
Three gradient-boosted quantile regressors estimate the median and 10th/90th
percentiles of forward returns. A nonnegative residual adjustment, fitted on
calibration observations spaced by the horizon, widens the interval. A separate
classifier estimates up versus non-up probability. The classifier probabilities
are not calibrated probabilities of profit.

The unchanged-price baseline, direction baselines, interval coverage, and
one-share long-only quote replay are reported on untouched test seeds. The replay
enters at the next recorded ask, exits at or after the horizon when a bid is
available, and pays both fees. It prevents overlapping positions per symbol and
reports remaining open positions separately. It does not model market impact,
large order capacity, or portfolio-level returns.

The saved artifact retains its feature schema, simulator version, horizon,
training/calibration/test seeds and measured performance. It is the evaluated
model, without a subsequent refit on held-out markets. Incompatible old artifacts
are rejected and logged. `Predictor` batches all symbols, uses the same feature
and interval code as evaluation, and scores exact-horizon outcomes. Duplicate
ticks do not double count; missing ticks reset history and pending evaluations.

## Interface

The forecast panel shows median target price, expected median change, nominal
80% interval, estimated probability of a higher close, and live direction,
price-error, baseline-error and coverage metrics. Chart price lines show the
forecast median and bounds. The portfolio exposes available cash, fees,
outstanding orders, and cancellation. Layout adapts to narrow screens.

WebSocket subscriptions have explicit cleanup, including pending reconnects,
so React Strict Mode does not leave duplicate connections running.

## Verification and limits

Automated checks cover matching, psychology, campaign behavior, finite account
balances and conservation, reservations and sweep affordability, self-trade
prevention, volatility-sensitive liquidity, causal labels, feature parity,
disjoint evaluation, live forecast maturity, and execution costs/illiquidity.
The frontend has a runnable connection-lifecycle check and a TypeScript/Vite
production build.

The current update passed 20 backend tests, the frontend lifecycle check and
production build, plus a localhost check of proxied REST/WebSocket forecasts,
market fills, cash-limit rejection, candle reads and order cancellation.

The market remains easier to predict than a demonstrated real-market trading
problem: campaigns and relatively simple agents leave persistent public order
flow. Current benchmarks establish simulator performance only. Overlapping test
labels and cross-symbol dependencies mean the number of rows is not the number
of independent observations; nominal interval coverage can drift in new regimes.

Remaining work includes calibration against real market stylized facts, richer
competing strategies and information delays, margin/borrow accounting, larger
order execution replay, persistence, and multi-user isolation. No browser
connection was available for a rendered UI check during this update.
