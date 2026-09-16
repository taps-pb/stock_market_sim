"""Feature extraction with a hard leakage boundary.

OBSERVABLE_COLS  = what a real trader could see (the honest prediction task).
ORACLE_COLS      = hidden latents that *cause* future price (upper-bound only).

The two are computed by separate functions and never mixed by accident; a test
asserts OBSERVABLE_COLS contains no latent. Meta columns (seed/tick/symbol) and
the label `y` are not features.
"""
from __future__ import annotations

import numpy as np

LAGS = (1, 5, 10, 20)
WINDOW = 30  # rolling window for volatility / moving-average features
HISTORY = 60  # how many recent prices the recorder must keep

OBSERVABLE_COLS = [
    "ret_1", "ret_5", "ret_10", "ret_20", "logret_1",
    "vol_w", "mom_w", "ma_gap", "hl_range",
    "spread_rel", "book_imb", "bid_depth", "ask_depth",
    "flow_imb", "flow_vol",
    "val_gap",              # last / public (stale) fair - 1
    "top_imb", "microprice_gap", "bid_present", "ask_present",
]

ORACLE_COLS = [
    "o_phase_accumulate", "o_phase_markup", "o_phase_distribute", "o_phase_markdown",
    "o_true_gap",          # last / exact live fair - 1  (latent)
    "o_inst_inv",          # net institutional inventory / campaign target
    "o_panic_frac",        # fraction of the symbol's retail in panic (fear > 0.6)
    "o_sent_fear", "o_sent_greed",  # actual agent emotions are NOT market observations
]

META_COLS = ["seed", "tick", "symbol", "horizon", "sim_version"]
PRICE_COLS = OBSERVABLE_COLS[:9]


def price_row(prices: np.ndarray) -> dict:
    """Causal price-only inputs shared by synthetic and historical forecasts."""
    last = float(prices[-1])
    w = prices[-WINDOW:]
    logrets = np.diff(np.log(w))
    return {
        **{f"ret_{k}": last / float(prices[-1 - k]) - 1 for k in LAGS},
        "logret_1": float(np.log(last / float(prices[-2]))),
        "vol_w": float(logrets.std()) if logrets.size else 0.0,
        "mom_w": last / float(w[0]) - 1,
        "ma_gap": last / float(w.mean()) - 1,
        "hl_range": (float(w.max()) - float(w.min())) / last,
    }


def observable_row(prices: np.ndarray, depth: dict, spread: float | None,
                   flow: list[int], public_fair: float) -> dict:
    """prices: recent price array, most-recent last, length >= HISTORY."""
    last = float(prices[-1])
    bid_depth = float(sum(q for _, q in depth.get("bids", [])))
    ask_depth = float(sum(q for _, q in depth.get("asks", [])))
    buy, sell = flow
    bids, asks = depth.get("bids", []), depth.get("asks", [])
    bp, bq = bids[0] if bids else (last, 0)
    ap, aq = asks[0] if asks else (last, 0)
    micro = (ap * bq + bp * aq) / (bq + aq) if bq and aq else last
    return {
        **price_row(prices),
        "spread_rel": (spread / last) if spread else 0.0,
        "book_imb": (bid_depth - ask_depth) / (bid_depth + ask_depth + 1),
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "flow_imb": (buy - sell) / (buy + sell + 1),
        "flow_vol": float(buy + sell),
        "val_gap": last / max(public_fair, 1e-6) - 1,
        "top_imb": (bq - aq) / (bq + aq + 1),
        "microprice_gap": micro / last - 1,
        "bid_present": float(bool(bids)), "ask_present": float(bool(asks)),
    }


def oracle_row(engine, symbol: str) -> dict:
    """Hidden latents read straight off the engine — the ceiling model only."""
    last = engine.last[symbol]
    fair = engine.companies[symbol].fair_value()
    phases = {"accumulate": 0, "markup": 0, "distribute": 0, "markdown": 0}
    inst_inv = 0.0
    inst_target = 0.0
    panic = 0
    retail = 0
    for t in engine.traders:
        if t.focus != symbol:
            continue
        if t.traits.is_institution:
            phases[t.phase] = phases.get(t.phase, 0) + 1
            inst_inv += t.positions.get(symbol, 0)
            inst_target += t.campaign_target
        elif not t.traits.is_market_maker and t.id != "USER":
            retail += 1
            panic += t.fear > 0.6
    dom = max(phases, key=phases.get)  # dominant institutional phase on this symbol
    return {
        "o_sent_fear": engine._sentiment()["fear"],
        "o_sent_greed": engine._sentiment()["greed"],
        "o_phase_accumulate": float(dom == "accumulate"),
        "o_phase_markup": float(dom == "markup"),
        "o_phase_distribute": float(dom == "distribute"),
        "o_phase_markdown": float(dom == "markdown"),
        "o_true_gap": last / max(fair, 1e-6) - 1,
        "o_inst_inv": inst_inv / inst_target if inst_target else 0.0,
        "o_panic_frac": panic / retail if retail else 0.0,
    }
