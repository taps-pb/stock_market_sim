# Market Lab · Agent Trading Arena

Fund an AI agent, turn on a simulated exchange, and measure what it actually
earns. Atlas trades six fictional stocks against 218 autonomous participants:
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
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt  # exact pins; model.pkl needs scikit-learn 1.9.0
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

The optional **Super risky** profile checks every tick, chases every forecast at
or above 50% up probability even when expected edge does not cover costs, and
pyramids toward its cap while the forecast stays bullish. It dumps the position
on a bearish flip or after a three-tick maximum hold, then immediately reassesses.
It can use 30% of equity per stock, 90% total exposure, 50% of displayed ask
depth, and 1% entry slippage. Its position loss stop remains 15%, but it ignores
the automatic account drawdown halt and keeps trading through losses. Manual
halt still liquidates and stops new buys; available cash and actual liquidity
still constrain trades. Thin books can prevent exits or produce worse execution.

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
  staggered earnings, and public news revisions. Competing market makers price noisy current valuations, widen spreads
  when volatility rises, and actively take sufficiently mispriced quotes.
  Institutional campaigns start in different phases with different clocks.
- Balanced, volatile, and retail-heavy experiment environments. The participant
  page exposes simulator internals for observers, explicitly hidden from Atlas.

The manual desk uses a separate $100,000 account. Its trades affect Atlas's
market and are recorded as interventions in exported results. For reproducible
agent comparisons, leave the manual account idle.

## Results and reproducibility

The v4 evaluation ran eight fresh seeds (501–508) across all three scenarios,
with $100,000 per account and 1,500 trading ticks:

| Measure | Result |
|---|---:|
| Atlas accounts fully liquidated | 24 / 24 |
| Atlas profitable / loss / flat | 19 / 5 / 0 |
| Mean Atlas return after fees (95% CI) | +0.94% (+0.44% to +1.47%) |
| Worst Atlas result | −$2,274.99 |
| Fully liquidated paired comparisons | 22 / 24 |
| Atlas beat buy-and-hold, among paired comparisons | 14 / 22 |
| Mean excess return vs buy-and-hold (95% CI) | +2.91% (+0.59% to +5.26%) |
| Sign test on excess: per run / per-seed means | p = 0.29 / p = 0.73 |

Intervals are seed-bootstrap percentiles (10,000 draws, whole seeds resampled,
because the three scenarios of one seed are dependent). Mean return is positive
across the interval, but Atlas beating buy-and-hold is **not statistically
supported**: 5 of 8 seed means are positive (p = 0.73).

Buy-and-hold retained inventory in two runs. Those do not exclude Atlas's own
realized losses from its statistics. The old 23/24 profitable archive exposed
simulator shortcuts; [the audit](backend/reports/realism-audit.md) documents the
investigation and fixes. Old results remain available, labelled by version.

See [the funded-agent report](backend/reports/agent-evaluation.md) and
[raw results](backend/reports/agent-evaluation.json). These are small synthetic
experiments. The market is highly learnable and is **not yet calibrated against
real exchange data**. Profit here does not establish real-market performance.

Run the same evaluation from `backend/`:

```bash
OMP_NUM_THREADS=1 python -m app.evaluate \
  --seeds 501 502 503 504 505 506 507 508 \
  --scenarios balanced volatile retail --ticks 1500 \
  --markdown reports/agent-evaluation.md
```

The JSON `summary.statistics` block holds the intervals and sign tests.
`--policy '{"min_edge_bps": 0}'` overrides policy settings. `--tune` sweeps a
27-point grid (`min_probability`, `min_edge_bps`, `max_position`) and refuses
final seeds 501–508; use tuning seeds such as 601–612.

**Experiments not adopted (v5).** Platt calibration of the up probability, fit on
calibration seed 6, scored worse than the raw classifier there (Brier 0.2011 vs
0.1977) and lowered final mean return to +0.74%. The tuned policy (edge 0 bps,
position 30%) raised mean return to +1.14% but had 8 losing runs and a −$4,345
worst run, with overlapping intervals. Model and defaults stay v4. See
[the v5 report](backend/reports/agent-evaluation-v5.md).

Every run is archived in `backend/data/runs.sqlite3`; the report is written to
`backend/reports/agent-evaluation.json`. The UI paginates all results, labels their simulator version, and
scopes its summary to the current simulator/model. It shows profit, loss, flat
outcomes and distinct seed counts; repeated seeds are not independent trials.
Exports include settings, engine configuration, model fingerprint, sampled
capital curve, full agent decisions/fills, and manual fills. Identical seed,
settings, code, model, and manual inputs reproduce the same exchange path.
External fundamentals and news use a separate random stream, so policy order
counts cannot change future external shocks.
Earlier development trials remain in the local archive; the report identifies
its exact run IDs. Market v2 and the rejected v3 candidate are historical results,
not evidence for v4. See [the audit](backend/reports/realism-audit.md).

Finish attempts to liquidate both accounts for up to 100 additional ticks.
If liquidity never appears, remaining inventory stays visible; it is never
converted into invented cash. Restarting creates a new market. Graceful shutdown
archives an unfinished run as interrupted; a running market is not resumable
and a hard process kill can lose the current unfinished run.

## Blind historical replay

Choose **New experiment → Blind historical replay**, import a local CSV, select
its dataset, and start a 100-session (or longer) experiment. Finish the current
experiment first. No data-provider account or network download is required.

CSV headers must be exactly:

```csv
date,symbol,open,high,low,close,volume
2010-01-04,EXAMPLE,100,102,99,101,1000000
```

This row illustrates the format, not a usable dataset. Supply roughly 800 or more
daily bars per symbol, ordered by date within each symbol. Dates use YYYY-MM-DD;
duplicate symbol/date pairs, nonfinite values, invalid OHLC bounds, nonpositive
prices, and negative volume are rejected. Limit: 10 MiB and 100,000 rows. Prices
must already be consistently adjusted for splits and dividends. Missing dates
are not filled: a session means one supplied bar for the selected symbol.
The app cannot verify source quality or perform corporate-action adjustments.

The earliest 70% of unique dataset dates are for training, the next 15% for
calibration, and the last 15% for testing. Targets are purged at boundaries;
the first 20 dataset sessions after each boundary are embargoed. Splits are
shared across symbols, so a later period of one stock cannot train a model
tested on an earlier period of another. The seed chooses one eligible stock
and contiguous test window. At least 100 test bars must remain after embargo.

Models receive only causal price vectors from 60 bars. The chart starts with
59 context bars, followed by day 1. The models never receive ticker, date,
dataset ID, or unrevealed bars. The display uses Asset A and relative days,
then reveals ticker and dates on completion, interruption, or early Finish.
This is a model-input boundary, not access control against the local operator
who imported the data.

Two frozen models predict 20 sessions ahead: the existing simulator model
with unavailable book/flow/valuation inputs set to zero, and a newly fitted
price-only historical model. The former is explicitly an out-of-distribution
transfer experiment: 20 simulator ticks and 20 daily sessions have different
meaning. Neither model learns from the selected test outcomes.

Forecasts are saved daily; headline scoring uses days 1, 21, 41, … and waits
20 sessions for each target. A 100-session run therefore has only four matured
checkpoints. Tail forecasts remain unresolved. Direction ties count as non-up.
Balanced accuracy is unavailable unless both up and non-up outcomes occur.
“Useful signal” is a descriptive label requiring better balanced accuracy than
both direction baselines and lower MAE than unchanged price in this sample.
It is not statistical significance or evidence of future profitability.

Paper results use one share per model, enter at the next open when predicted
return exceeds the 2 bp round-trip fee estimate, and exit at target-day close.
Fees are 1 bp each side; positions never overlap. Early-finished or end-of-data
inventory remains marked, with entry fees included in unrealized P&L. This
does not simulate spread, slippage, volume participation, or achievable fills.
Values use the CSV's price units, not an assumed currency.

Datasets live under ignored `backend/data/replay/`, identified by normalized
CSV SHA-256. Run exports include both model fingerprints, split boundaries,
all daily forecasts, checkpoint outcomes, revealed bars, and paper accounts.
Reproduction needs the same normalized CSV, code, dependencies, and simulator
artifact. The model is fitted deterministically again for each replay.
Archive filters and pagination expose all saved synthetic and historical runs;
historical outcomes never enter synthetic profitability summaries.

API additions: `POST /api/replay-datasets?name=...` accepts a `text/csv` body;
`GET /api/replay-datasets` lists imports; `POST /api/replay-runs` accepts
`dataset_id`, `seed`, and `duration`. `GET /api/runs` now returns
`{items,total,limit,offset}` and accepts `limit`, `offset`, and optional `kind`
(`synthetic` or `historical`). Old archived runs default to synthetic. Synthetic
order/candle endpoints return 409 while historical replay is active.

## Train the synthetic price model

From `backend/`, with the virtual environment active:

```bash
python -m ml.record --seeds 8 --ticks 3000 --horizon 20 --out ml/data/dataset-v4.csv
OMP_NUM_THREADS=1 python -m ml.train --data ml/data/dataset-v4.csv --save ml/model.pkl
```

The included artifact uses seeds 1–5 for training, seed 6 for interval
calibration, and seeds 7–8 for untouched evaluation. Its public-input forecast
price MAE is $0.868 versus $0.989 for unchanged price; direction accuracy is
69.5%, and interval coverage is 79.6%. These forecasting metrics are separate
from the funded trading experiments. See [the model report](backend/ml/report.md).
Up probabilities are raw classifier estimates, not probabilities of profit. They are
close to calibrated on seed 6 (Brier 0.198); Platt and isotonic calibration did not improve them.

Restart after replacing the model. Regenerate data and retrain after changing
market dynamics. Incompatible artifacts fail visibly; an experiment cannot
start without a compatible model.

## Security and local data

Market Lab is designed for local use. The API has no authentication and allows
cross-origin requests, so keep the backend bound to `127.0.0.1`. Do not expose it
directly to the internet without adding authentication, access controls, and a
restricted CORS policy.

The application needs no broker credentials, exchange keys, or paid data-provider
account. Included training data, model artifacts, and evaluation reports come from
fictional simulated markets. Imported historical CSVs and experiment archives stay
under ignored `backend/data/`; review exported run JSON before sharing it.

The included `model.pkl` is a Python pickle. Load only the artifact shipped with a
trusted checkout, or one you trained yourself. Never replace it with an untrusted
pickle.

## Verification and code map

```bash
cd backend
OMP_NUM_THREADS=1 .venv/bin/python -m pytest tests -q
```

GitHub Actions (`.github/workflows/ci.yml`) runs both suites and the build on every push.

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
