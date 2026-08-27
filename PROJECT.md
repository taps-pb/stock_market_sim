# PROJECT.md — Stock Market Simulator

Status snapshot of what has been built so far. For run instructions see
[README.md](README.md); for the original design see the approved plan.

## What this is

A trader-driven stock market simulator for fictional stocks. Prices are **not**
calculated from a formula — they emerge from a continuous double-auction order
book fed by a population of ~200 simulated traders, each with its own psychology
(capital size, risk tolerance, fear/greed that evolves with the market).
Fundamentals influence only what each trader is *willing to pay*; the last matched
trade is the price. The human user is a trader in the same book.

The population is **tiered**: a few huge institutions (smart money) and a large
retail crowd. Institutions run market-moving **campaigns** — accumulate cheap,
let retail mark the price up, distribute into that strength near the top, then
step aside for the markdown — which is how big players move the market and trap
smaller traders. This is emergent, not scripted onto retail: the crowd simply
reacts to the price the institutions create.

All fundamentals and prices are simulated. Nothing is real market data.

## Architecture

```
fundamentals (eps, growth, quality)  --drift + earnings events-->  fair value
        |                                                              |
        v                                                              v
   each TRADER reads: last price, recent trend, fair value, own P&L,
                      own emotional state (fear/greed)  -->  LIMIT order
        |
        v
   ORDER BOOK (price-time priority) --match--> trades --> LAST PRICE
        |
        v
   trades feed back into every trader's fear/greed  (the loop that makes
   panics and bubbles self-reinforce);  OHLCV --> WebSocket --> React chart
```

The feedback loop — trades reshaping fear/greed, which reshapes the next orders —
is what produces cascades and bubbles instead of a smooth curve.

## Repository layout

```
backend/
  app/
    config.py            # ALL calibration knobs + SEED_COMPANIES
    main.py              # FastAPI app; runs the sim loop in the background
    runtime.py           # process singletons: SimEngine + WebSocket hub
    engine/
      market.py          # Order, Trade, Candle, Side; tick quantization
      orderbook.py       # continuous double-auction, price-time priority
      fundamentals.py    # Company, drift, earnings events, fair_value()
      trader.py          # Trader: traits + emotional state + decide()
      archetypes.py      # preset trait vectors + population builder
      simulation.py      # SimEngine: per-tick loop, fills, candles, snapshot
    api/
      routes.py          # REST (/api/state, /candles, /portfolio, /orders) + /ws
  tests/
    test_orderbook.py    # matching-engine correctness
    test_traders.py      # trader psychology + market-level sanity
  requirements.txt
frontend/                # Vite + React + TypeScript
  src/
    store.ts             # zustand: snapshot + selected symbol + portfolio
    ws.ts / api.ts       # WebSocket stream + REST client
    App.tsx, main.tsx
    components/          # Watchlist, Chart, DepthLadder, Tape,
                        #   TradeTicket, PortfolioView, Sentiment
```

## Components built

### Order book (`engine/orderbook.py`)
Two `SortedDict[price] -> deque[Order]` sides. Best bid = last key, best ask =
first key. Matching: buys take cheapest asks first, sells hit highest bids first,
FIFO within a price level; trades execute at the resting (passive) price. Supports
limit + market orders, partial fills, cancellation, and a depth ladder for the UI.

### Traders (`engine/trader.py`, `engine/archetypes.py`) — the centerpiece
One `Trader` = a fixed **trait vector** + a mutable **emotional state** + a
`decide()` function. Archetypes are just preset trait vectors, so adding a new
"common trader type" is one row in `_PRESETS`.

- **Traits:** capital, risk_tolerance, panic_threshold, fomo_sensitivity,
  conviction, herding, skill, horizon, loss_aversion, activity.
- **Emotional state (evolves each tick):** fear, greed, plus position / entry
  price / unrealized P&L. This makes "weak hands sell on a small dip" emergent and
  path-dependent, not scripted.
- **decide():** combines a value signal (fair vs price, scaled by skill), a
  momentum signal (recent trend, scaled by herding), greed (chasing — a low-skill
  behavior), and fear (into a panic-exit). Panic selling overrides everything.
- **Archetypes (14), grouped in tiers** (`archetypes.TIER`):
  - *institutional* — `institution` (runs campaigns), `whale` (opportunistic big
    value), `pension` (slow, passive, very long horizon).
  - *informed* — `value`, `contrarian`, `swing`, `momentum`.
  - *professional* — `scalper`, `market_maker`.
  - *retail crowd* — `fomo` (buys tops, holds hoping, panics late), `weak_hands`
    (hair-trigger panic), `retail`, `bagholder`, `noise`.
  - ~200 traders across 6 stocks, retail-heavy, mix configurable. Noise is
    guaranteed one per symbol so no stock deadlocks; the market opens with traders
    already holding so sellers exist from tick one.
- **Institutional campaign** (`Trader._campaign`, the market-moving smart money):
  a four-phase state machine — **accumulate** (buy passively near/below fair),
  **markup** (step back, let retail run it), **distribute** (offer into the
  crowd's buying near the top), **markdown** (press it down a little, may go net
  short, then re-accumulate the panic). Phase transitions are driven by inventory,
  price-vs-fair, and timeouts, and are surfaced per symbol in the snapshot.
- **Market maker** quotes both sides with an inventory skew that keeps its book
  bounded and near-flat, so it supplies liquidity without becoming a directional
  winner.

### Fundamentals (`engine/fundamentals.py`)
Each company has eps / growth / quality; `fair_value()` derives a P/E-anchored
value calibrated to open at the seed price. Eps drifts each tick and takes a
discrete surprise jump on the earnings schedule (surfaced as an event).

### Simulation loop (`engine/simulation.py`)
Per tick: evolve fundamentals → expire stale orders (market makers re-quote every
tick) → update every trader's emotion → collect and shuffle orders → match → apply
fills to positions/cash/P&L → roll OHLCV candles → build a snapshot. Exposes
`submit_user_order`, `portfolio()`, `candle_list()`, and a `snapshot()` with per-
symbol quotes + depth, the fear/greed sentiment, recent trades, and events.

### Backend API (`api/routes.py`, `main.py`, `runtime.py`)
FastAPI runs the sim on a fixed clock in a background task and broadcasts each
snapshot over WebSocket. REST: `GET /api/state`, `GET /api/symbols/{s}/candles`,
`GET /api/portfolio`, `POST /api/orders`. The user is a real (activity-0) trader
in the book; order writes are validated for cash and shares (reject → HTTP 400).

### Frontend (`frontend/src/`)
Live dark-theme trading UI: TradingView lightweight-charts candlesticks + volume,
watchlist with % change, a **participants** panel (institutions vs the retail
crowd), a **smart-money phase badge** on the chart (accumulate / markup /
distribute / markdown, so you can watch the campaign play out), live order-book
depth ladder, time & sales tape, a trade ticket (market/limit buy/sell), portfolio
with mark-to-market P&L, and a fear/greed sentiment meter. WebSocket stream for
ticks; REST for candles and portfolio.

### ML prediction layer (`backend/ml/`, Phase 1)

The simulator doubles as a **ground-truth market** for training a predictor and
measuring how accurate prediction can be — with a hard **leakage boundary**.

- `features.py` — splits features into `OBSERVABLE_COLS` (what a real trader sees:
  lagged returns, volatility, momentum, order-book imbalance/spread/depth, signed
  trade flow, a *stale published* fair, an aggregate sentiment index) and
  `ORACLE_COLS` (hidden latents that *cause* price: institution campaign phase,
  exact live fair gap, net institutional inventory, retail panic fraction). A test
  asserts the observable set contains no latent.
- `record.py` — runs `SimEngine` headless across seeds, emitting one row per
  `(symbol, tick)` with a forward label `y = 1` if price `candle_ticks` ahead is
  higher. One tiny engine hook feeds it: per-tick signed volume `SimEngine.flow`.
- `train.py` — baselines (majority, persistence) + gradient-boosted trees, tested
  on **unseen seeds** (must generalize to a fresh market), reporting the
  observable-only model next to an observable+oracle ceiling.

**Result (8 seeds, 3000 ticks, ~140k rows, next-20-tick direction):**

| model | acc | AUC |
|---|---|---|
| baseline majority | 0.534 | — |
| baseline persistence | 0.572 | — |
| **GBM observable** | **0.829** | **0.910** |
| GBM + oracle | 0.830 | 0.913 |

- **+0.26 over baseline** → a genuine learnable signal exists (no temporal leak:
  features use only data up to the current tick).
- **Oracle ≈ observable** → the observable order flow already reveals the latent
  state; knowing the hidden phase/emotions adds ~nothing.
- Ablation: the signal is **order flow** (book imbalance + signed flow → 0.827),
  not valuation/mean-reversion (`val_gap` alone → 0.569). The model learns to read
  the tape/book for the **institutional footprint** — exactly how real quant
  signals work, and why the campaign phase is recoverable from public data.
- **Caveat:** 0.83 directional accuracy is far above real markets (~0.55). Our sim
  is more predictable because institutions push price with strong, persistent,
  *observable* order flow. That's a realistic *reason*, but if the goal is
  real-market *difficulty*, dial up noise / weaken the footprint in `config.py`.

## Verification

- **15/15 tests green** (`pytest tests -q`) — 12 sim + 3 ML (dataset sanity,
  leakage-boundary guard, pipeline produces valid accuracy).
  - Order book: no-cross rest, full/partial fill at resting price, price-time
    priority, cheapest-ask-first, market sweep, cancel, bid<ask invariant.
  - Traders: weak hands panic a small dip while a whale buys it; FOMO chases a
    rally while value stays disciplined; over 1500 ticks the market tracks fair
    value on average with no runaway detachment and every stock trades.
  - Campaign / trap: institutions run full accumulate→markup→distribute→markdown
    cycles, and a beta-neutral signature holds — normalizing every fill by the
    fair value at that instant, institutions buy below fair and sell above it,
    while retail buys at a higher price/fair than smart money (the trap).
- **End-to-end runtime verified:** backend :8000 + Vite :5173, live tick stream
  through the proxy, candles served, buy/sell round-trip (spread cost realistic),
  oversell guard → 400, deep limit order rests unfilled. TypeScript builds clean.

## Not built yet / next steps

- **Non-earnings news events** — headline shocks that jolt sentiment/fundamentals
  beyond the scheduled earnings surprises.
- **UI screenshot check** — no headless browser installed; only the data path was
  verified, not a rendered-pixels check.
- **Persistence** — in-memory only; a restart resets the market (SQLite/Postgres
  when history or portfolio must survive restarts).
- **Auth / multi-user**, and instruments beyond spot limit/market (shorting,
  margin, options) — deferred by design.
- **Scale** — starts at 6 stocks; expand via `SEED_COMPANIES`. Full order book per
  tick is comfortable at this size; larger universes may need perf work.
- **ML later phases** — sequence model (LSTM / temporal CNN), a trading-PnL
  backtest (act on the signal, measure money not accuracy), regression targets,
  and difficulty calibration toward real-market predictability.
