"""Batch live price forecasts and score only predictions whose horizon has elapsed."""
from __future__ import annotations

from collections import deque

import joblib
import numpy as np

from app.config import SIM_VERSION
from .features import HISTORY, OBSERVABLE_COLS, observable_row
from .train import SCHEMA_VERSION, forecast


class Predictor:
    def __init__(self, path: str) -> None:
        self.artifact = joblib.load(path)
        d = self.artifact
        if (d.get("schema_version") != SCHEMA_VERSION or d.get("sim_version") != SIM_VERSION
                or d.get("cols") != OBSERVABLE_COLS or not isinstance(d.get("horizon"), int)
                or d["horizon"] < 1):
            raise ValueError("incompatible model; regenerate data and retrain")
        self.model = d["model"]
        self.cols = d["cols"]
        self.horizon = d["horizon"]
        self.buf: dict[str, deque] = {}
        self.pending: deque = deque()
        self.hits = self.total = self.covered = 0
        self.error = self.baseline_error = 0.0
        self.last_tick: int | None = None
        self.last_output: dict = {}

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
        self.last_tick = engine.tick
        for s in engine.symbols:
            self.buf.setdefault(s, deque(maxlen=HISTORY)).append(engine.last[s])
        while self.pending and self.pending[0][0] <= engine.tick:
            tick, s, up, initial, predicted, lower, upper = self.pending.popleft()
            if tick != engine.tick:
                continue
            actual = engine.last[s]
            self.hits += int((actual > initial) == up)
            self.covered += int(lower <= actual <= upper)
            self.error += abs(actual - predicted)
            self.baseline_error += abs(actual - initial)
            self.total += 1

        symbols = [s for s in engine.symbols if len(self.buf[s]) >= HISTORY]
        signals = {}
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
        self.last_output = {
            "signals": signals, "accuracy": self.hits / self.total if self.total else None,
            "mae": self.error / self.total if self.total else None,
            "baseline_mae": self.baseline_error / self.total if self.total else None,
            "coverage": self.covered / self.total if self.total else None,
            "interval_coverage": self.artifact["interval_coverage"],
            "evaluation": self.artifact["evaluation"],
            "n": self.total, "horizon": self.horizon,
        }
        return self.last_output
