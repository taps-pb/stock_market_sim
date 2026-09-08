# Market Lab · Agent Trading Arena

Fund an AI agent, turn on a simulated exchange, and measure what it actually
earns. Atlas trades six fictional stocks against 206 autonomous participants:
panic sellers, FOMO buyers, value investors, momentum traders, institutions,
whales, pensions, and market makers. Prices emerge from their matched orders.

The rebuilt workspace includes a live capital curve, an equally funded
buy-and-hold account, price forecasts, market depth, participant behavior,
an execution journal, a manual trading desk, and a persistent experiment archive.
All funds, companies, and results are simulated.

## Start the platform

Backend, in one terminal:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
OMP_NUM_THREADS=1 uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in another:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. A trained model is included. The default
experiment funds Atlas and buy-and-hold with **$100,000 each**, using seed 42.
The exchange runs without an open browser.

1. Watch the first 60 ticks build observable market history.
2. Inspect live equity, net profit after fees, drawdown, and performance against
   buy-and-hold. Switch the capital chart between dollars and percentage returns.
3. Explore individual stocks, forecasts, order books, and trader categories.
4. Use 1×, 5×, or 20× speed. Pause freezes the exchange; stopping Atlas closes
   its positions and prevents new buys while the other participants continue.
5. Finish the run, inspect its saved result, or export its JSON. **New experiment**
   lets you choose capital, seed, duration, market environment, and risk profile.

An experiment trades for 1,500 ticks by default, after warmup. The clock targets
four ticks per second at 1×; speed depends on the machine. Ticks are simulation
steps, not calendar days, so returns are not annualized.

## How Atlas trades

Atlas combines the included gradient-boosted price model with an explicit
execution and risk policy. It is an autonomous model-driven trader, not an LLM
pretending to place orders. It receives past prices, public book depth, signed
order flow, published valuation, and its own account. It cannot read hidden
fundamentals, institutional campaign phases, emotions, or future prices.

The model estimates the price 20 ticks ahead, a nominal 80% interval, and the
probability of a higher close. Every five ticks, Atlas considers buys when the
estimated up probability clears 62% and the forecast clears the current ask,
estimated fees, slippage allowance, and a further 20-basis-point edge.

Default entry limits are 20% of equity per position, 60% total exposure, and
25% of displayed ask depth within the order's price limit. Atlas cannot borrow
or short. It exits after its holding period, a forecast reversal, a 2.5% position
stop, or an 8% account drawdown. These are exit triggers, not guaranteed prices
or maximum losses; actual liquidity determines execution. Price movement can
also take existing positions above their entry allocation caps.

Orders based on tick **t** enter the same shuffled matching queue as other
traders at **t+1**. Buys use immediate-or-cancel limits; exits are market orders.
Partial fills and zero fills are recorded. The agent's cash and shares change
only through actual exchange fills, including fees. The journal shows the
requested quantity, actual fill, execution tick, price, and decision reason.

Buy-and-hold receives the same starting cash, builds equal target allocations
across six stocks within the same exposure budget, and holds until settlement.
It uses the same liquidity participation, delayed execution, and fees. Its
allocation order does not use AI forecasts. Both accounts affect the market;
this is a shared-exchange comparison, not separate counterfactual price paths.

## Market mechanics

- Continuous double auction with price-time priority, partial fills, market
  sweeps, self-trade prevention, and finite depth.
- Cash and shares reserved for outstanding orders. Human limits remain open
  until filled or cancelled; bot quotes expire.
- One basis point per side goes to the exchange. News-driven orders use a
  finite funded account. Cash plus exchange fees and net shares are conserved.
- Fourteen trader archetypes with different capital, patience, fear, greed,
  valuation responses, and trading horizons. Institutions follow staged
  accumulation/distribution campaigns; ordinary retail cannot short.
- Shared market and sector fundamental shocks, persistent calm/stressed states,
  staggered earnings, and public news revisions. Market makers widen spreads
  and reduce size when observed volatility rises.
- Balanced, volatile, and retail-heavy experiment environments. The participant
  page exposes simulator internals for observers, explicitly hidden from Atlas.

The manual desk uses a separate $100,000 account. Its trades affect Atlas's
market and are recorded as interventions in exported results. For reproducible
agent comparisons, leave the manual account idle.

## Results and reproducibility

The current evaluation ran three fresh seeds (101–103) across all three
scenarios, with $100,000 per account and 1,500 trading ticks:

| Measure | Result |
|---|---:|
| Fully settled experiments | 9 / 9 |
| Agent profitable after fees | 9 / 9 |
| Agent beat buy-and-hold | 5 / 9 |
| Mean agent return | +1.58% |
| Mean excess profit over buy-and-hold | −$949.77 |

See [the funded-agent report](backend/reports/agent-evaluation.md) and
[raw results](backend/reports/agent-evaluation.json). These are small synthetic
experiments. The market is highly learnable and is **not yet calibrated against
real exchange data**. Profit here does not establish real-market performance.

Run the same evaluation from `backend/`:

```bash
OMP_NUM_THREADS=1 python -m app.evaluate \
  --seeds 101 102 103 --scenarios balanced volatile retail --ticks 1500
```

Every run is archived in `backend/data/runs.sqlite3`; the report is written to
`backend/reports/agent-evaluation.json`. The UI shows the latest 30 results.
Exports include settings, engine configuration, model fingerprint, sampled
capital curve, full agent decisions/fills, and manual fills. Identical seed,
settings, code, model, and manual inputs reproduce the same exchange path.
Earlier development trials remain in the local archive; the report identifies
its exact nine run IDs.

Finish attempts to liquidate both accounts for up to 100 additional ticks.
If liquidity never appears, remaining inventory stays visible; it is never
converted into invented cash. Restarting creates a new market. Graceful shutdown
archives an unfinished run as interrupted; a running market is not resumable
and a hard process kill can lose the current unfinished run.

## Train the price model

From `backend/`, with the virtual environment active:

```bash
python -m ml.record --seeds 8 --ticks 3000 --horizon 20
OMP_NUM_THREADS=1 python -m ml.train --save ml/model.pkl
```

The included artifact uses seeds 1–5 for training, seed 6 for interval
calibration, and seeds 7–8 for untouched evaluation. Its public-input forecast
price MAE is $0.601 versus $1.032 for unchanged price; direction accuracy is
87.3%, and interval coverage is 79.1%. These forecasting metrics are separate
from the funded trading experiments. See [the model report](backend/ml/report.md).
Up probabilities are classifier estimates, not calibrated probabilities of profit.

Restart after replacing the model. Regenerate data and retrain after changing
market dynamics. Incompatible artifacts fail visibly; an experiment cannot
start without a compatible model.

## Verification and code map

```bash
cd backend
OMP_NUM_THREADS=1 .venv/bin/python -m pytest tests -q
```

```bash
cd frontend
npm test
npm run build
```

Checks cover the matching engine, trader behavior, resource reservations,
conservation, causal features/labels, evaluation splits, forecast maturity,
next-tick agent execution, risk stops, illiquid settlement, deterministic
funded runs, durable archives, and WebSocket cleanup.

- `backend/app/engine/`: exchange, company dynamics, and autonomous traders.
- `backend/app/agent.py`: policy using public observations and its own account.
- `backend/app/arena.py`: funded experiment lifecycle, accounting, and SQLite.
- `backend/app/evaluate.py`: batch experiments through the same live engine.
- `backend/app/runtime.py`, `api/`: local clock, REST controls, WebSocket state.
- `backend/ml/`: causal features, recording, training, and live forecasts.
- `frontend/src/`: React workspace, charts, participants, journal, and archive.
- `backend/app/config.py`: population, liquidity, fees, news, and regime knobs.

This is one local workspace with no broker connection, authentication, or
multi-user isolation. See [PROJECT.md](PROJECT.md) for implementation context.
