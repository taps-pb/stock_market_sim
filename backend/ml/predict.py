"""Batch live price forecasts and score only predictions whose horizon has elapsed."""
from __future__ import annotations

from collections import deque
from hashlib import sha256
from pathlib import Path

import joblib
import numpy as np

from app.config import SEED_COMPANIES, SIM_VERSION
from .features import HISTORY, OBSERVABLE_COLS, observable_row
from .train import SCHEMA_VERSION, forecast


class Predictor:
    def __init__(self, path: str, outlook_path: str | None = None) -> None:
        primary_sha = sha256(Path(path).read_bytes()).hexdigest()
        self.fingerprint = primary_sha[:16]
        self.artifact = joblib.load(path)
        d = self.artifact
        if (d.get("schema_version") != SCHEMA_VERSION or d.get("sim_version") != SIM_VERSION
                or d.get("cols") != OBSERVABLE_COLS or not isinstance(d.get("horizon"), int)
                or d["horizon"] < 1):
            raise ValueError("incompatible model; regenerate data and retrain")
        self.model = d["model"]
        self.cols = d["cols"]
        self.horizon = d["horizon"]
        self.outlook = None
        if outlook_path is not None:
            bundle = joblib.load(outlook_path)
            prices = {s: float(p) for s, _, _, p, *_ in SEED_COMPANIES}
            if (bundle.get("bundle_version") != 1 or bundle.get("schema_version") != SCHEMA_VERSION
                    or bundle.get("sim_version") != SIM_VERSION or bundle.get("cols") != OBSERVABLE_COLS
                    or bundle.get("base_sha256") != primary_sha or self.horizon != 20
                    or bundle.get("base_prices") != prices or set(bundle.get("models", {})) != {60, 120}
                    or set(bundle.get("index", {})) != {20, 60, 120}
                    or any(bundle["models"][h].get("horizon") != h
                           or bundle["models"][h].get("cols") != OBSERVABLE_COLS
                           or bundle["models"][h].get("schema_version") != SCHEMA_VERSION
                           or bundle["models"][h].get("sim_version") != SIM_VERSION for h in (60, 120))):
                raise ValueError("incompatible outlook; retrain against the primary model")
            self.outlook = bundle
            self.fingerprint = sha256((primary_sha + sha256(Path(outlook_path).read_bytes()).hexdigest()).encode()).hexdigest()[:16]
        self.buf: dict[str, deque] = {}
        self.pending: deque = deque()
        self.hits = self.total = self.covered = 0
        self.error = self.baseline_error = 0.0
        self.last_tick: int | None = None
        self.last_output: dict = {}
        self.by_symbol: dict[str, dict] = {}
        self.recent: deque = deque(maxlen=120)

    def _vector(self, engine, s: str) -> list[float]:
        row = observable_row(np.array(self.buf[s], dtype=float),
                             engine.books[s].depth(8), engine.books[s].spread(),
                             engine.flow[s], engine.companies[s].public_fair())
        return [row[c] for c in self.cols]

    def step(self, engine) -> dict:
        if engine.tick == self.last_tick:
            return self.last_output
        if self.last_tick is not None and engine.tick != self.last_tick + 1:
            # Gaps invalidate lag features and exact-horizon scoring.
            self.buf.clear()
            self.pending.clear()
            self.hits = self.total = self.covered = 0
            self.error = self.baseline_error = 0.0
            self.by_symbol.clear()
            self.recent.clear()
        self.last_tick = engine.tick
        for s in engine.symbols:
            self.buf.setdefault(s, deque(maxlen=HISTORY)).append(engine.last[s])
        while self.pending and self.pending[0][0] <= engine.tick:
            tick, s, up, initial, predicted, lower, upper = self.pending.popleft()
            if tick != engine.tick:
                continue
            actual = engine.last[s]
            err = abs(actual - predicted)
            baseline_err = abs(actual - initial)
            hit = int(lower <= actual <= upper)
            self.hits += int((actual > initial) == up)
            self.covered += hit
            self.error += err
            self.baseline_error += baseline_err
            self.total += 1
            stats = self.by_symbol.setdefault(s, {"n": 0, "error": 0.0, "baseline_error": 0.0, "covered": 0})
            stats["n"] += 1
            stats["error"] += err
            stats["baseline_error"] += baseline_err
            stats["covered"] += hit
            self.recent.appendleft({"symbol": s, "issued_tick": tick - self.horizon, "target_tick": tick,
                                    "starting_price": initial, "predicted_price": predicted, "lower": lower,
                                    "upper": upper, "actual_price": actual, "abs_error": err, "covered": bool(hit)})

        symbols = [s for s in engine.symbols if len(self.buf[s]) >= HISTORY]
        signals = {}
        outlook_series = []
        if symbols:
            x = np.array([self._vector(engine, s) for s in symbols])
            probs = self.model.predict_proba(x)[:, 1]
            returns, lows, highs = forecast(self.artifact, x)
            for s, p, ret, lo, hi in zip(symbols, probs, returns, lows, highs):
                initial = engine.last[s]
                predicted, lower, upper = (initial * (1 + r) for r in (ret, lo, hi))
                signals[s] = {"dir": "up" if p >= 0.5 else "down", "prob": round(float(p), 4),
                              "price": round(float(predicted), 2), "lower": round(float(lower), 2),
                              "upper": round(float(upper), 2), "return_pct": round(float(ret * 100), 3),
                              "target_tick": engine.tick + self.horizon}
                self.pending.append((engine.tick + self.horizon, s, p >= 0.5,
                                     initial, predicted, lower, upper))
            if self.outlook and len(symbols) == len(engine.symbols):
                base = self.outlook["base_prices"]
                now = 100 * sum(engine.last[s] / base[s] for s in symbols) / len(symbols)
                for h in (20, 60, 120):
                    ret, low, high = (returns, lows, highs) if h == 20 else forecast(self.outlook["models"][h], x)
                    stocks = {}
                    norm_pred = 0.0
                    for i, s in enumerate(symbols):
                        current = engine.last[s]
                        predicted, lower, upper = (float(current * (1 + r[i])) for r in (ret, low, high))
                        stocks[s] = {"price": round(predicted, 2), "lower": round(lower, 2),
                                     "upper": round(upper, 2), "return_pct": round(float(ret[i] * 100), 3)}
                        norm_pred += predicted / base[s]
                    index = self.outlook["index"][h]
                    level = 100 * norm_pred / len(symbols)
                    outlook_series.append({"horizon": h, "target_tick": engine.tick + h,
                                           "index_price": round(level, 4),
                                           "index_lower": round(max(0.0, level - index["pad"]), 4),
                                           "index_upper": round(level + index["pad"], 4),
                                           "index_return_pct": round((level / now - 1) * 100, 4),
                                           "stocks": stocks, "evaluation": index["evaluation"]})
        by_symbol = {}
        for s in engine.symbols:
            stats = self.by_symbol.get(s)
            n = stats["n"] if stats else 0
            by_symbol[s] = {"n": n,
                            "mae": stats["error"] / n if n else None,
                            "baseline_mae": stats["baseline_error"] / n if n else None,
                            "coverage": stats["covered"] / n if n else None}
        self.last_output = {
            "signals": signals, "accuracy": self.hits / self.total if self.total else None,
            "mae": self.error / self.total if self.total else None,
            "baseline_mae": self.baseline_error / self.total if self.total else None,
            "coverage": self.covered / self.total if self.total else None,
            "interval_coverage": self.artifact["interval_coverage"],
            "evaluation": self.artifact["evaluation"],
            "n": self.total, "horizon": self.horizon,
            "review": {"by_symbol": by_symbol, "recent": list(self.recent)},
        }
        if self.outlook is not None:
            base = self.outlook["base_prices"]
            if set(engine.symbols) != set(base):
                raise ValueError("outlook index constituents differ from the live market")
            self.last_output["outlook"] = {"index_now": round(100 * sum(engine.last[s] / base[s] for s in engine.symbols) / len(engine.symbols), 4),
                                           "series": outlook_series}
        return self.last_output
