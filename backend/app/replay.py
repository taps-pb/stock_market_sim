"""Local daily-bar experiments. Models see price vectors, never the replay tape."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
from math import ceil
from pathlib import Path
import json
import pickle
import re
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from ml.features import HISTORY, OBSERVABLE_COLS, PRICE_COLS, price_row
from ml.train import forecast

HORIZON = 20
MAX_BYTES = 10 * 1024 * 1024
REPLAY_VERSION = 1
COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]


def split_dates(frame):
    dates = sorted(frame.date.unique())
    a, b = int(len(dates) * .70), int(len(dates) * .85)
    if a < HISTORY + HORIZON or b + HORIZON >= len(dates):
        raise ValueError("Insufficient history for 70/15/15 splits and 20-session embargoes")
    return dict(train_end=dates[a - 1], calibration_start=dates[a + HORIZON],
                calibration_end=dates[b - 1], test_start=dates[b + HORIZON], test_end=dates[-1])


def eligible(frame, splits, duration=100):
    return {symbol: group.reset_index(drop=True) for symbol, group in frame.groupby("symbol", sort=True)
            if int((group.date >= splits["test_start"]).sum()) >= duration
            and int((group.date < splits["test_start"]).sum()) >= HISTORY - 1}


class DatasetStore:
    def __init__(self, root: Path):
        self.root = root

    def import_csv(self, raw: bytes, name: str):
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError("CSV must be nonempty and at most 10 MiB")
        try:
            frame = pd.read_csv(StringIO(raw.decode("utf-8-sig")), dtype={"date": str, "symbol": str}, keep_default_na=False)
            if list(frame.columns) != COLUMNS or not 1 <= len(frame) <= 100_000:
                raise ValueError("CSV needs date,symbol,open,high,low,close,volume and at most 100,000 rows")
            if not frame.date.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                raise ValueError("Dates must use YYYY-MM-DD")
            pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise")
            if not frame.symbol.str.fullmatch(r"[A-Za-z0-9.^_-]{1,32}").all():
                raise ValueError("Symbols must be 1–32 letters, digits, or . ^ _ -")
            frame.symbol = frame.symbol.str.upper()
            if frame.duplicated(["symbol", "date"]).any():
                raise ValueError("Duplicate symbol/date rows")
            if any(not g.date.is_monotonic_increasing for _, g in frame.groupby("symbol")):
                raise ValueError("Dates must be ordered within each symbol")
            for col in COLUMNS[2:]:
                frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
            if not np.isfinite(frame[COLUMNS[2:]].to_numpy()).all():
                raise ValueError("OHLCV values must be finite")
            if ((frame[COLUMNS[2:6]] <= 0).any().any() or (frame.volume < 0).any()
                    or (frame.high < frame[["open", "close", "low"]].max(axis=1)).any()
                    or (frame.low > frame[["open", "close", "high"]].min(axis=1)).any()):
                raise ValueError("Invalid OHLC bounds, nonpositive price, or negative volume")
        except (UnicodeError, pd.errors.ParserError, TypeError) as exc:
            raise ValueError("Invalid UTF-8 OHLCV CSV") from exc
        frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
        splits = split_dates(frame)
        choices = eligible(frame, splits)
        if not choices:
            raise ValueError("Need at least 100 test sessions after embargo; supply roughly 800+ daily bars per symbol")
        # Validate that fitting and calibration are feasible before accepting the file.
        training_rows(frame, splits)
        normalized = frame.to_csv(index=False, float_format="%.17g").encode()
        key = sha256(normalized).hexdigest()
        metadata = dict(id=key, name=Path(name).name[:120] or "history.csv", rows=len(frame),
                        symbols=sorted(frame.symbol.unique().tolist()), start=frame.date.min(), end=frame.date.max(),
                        max_duration=max(int((g.date >= splits["test_start"]).sum()) for g in choices.values()))
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{key}.json"
        if path.exists() and (self.root / f"{key}.csv").exists() and sha256((self.root / f"{key}.csv").read_bytes()).hexdigest() == key:
            return json.loads(path.read_text())
        # Metadata appears last, so incomplete writes never appear in the importer list.
        (self.root / f"{key}.csv").write_bytes(normalized)
        path.write_text(json.dumps(metadata))
        return metadata

    def list(self):
        return [json.loads(p.read_text()) for p in sorted(self.root.glob("*.json"))]

    def load(self, key):
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("Invalid dataset ID")
        path = self.root / f"{key}.csv"
        if not path.exists() or not path.with_suffix(".json").exists():
            raise ValueError("Dataset not found")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != key:
            raise ValueError("Dataset fingerprint mismatch; reimport the original CSV")
        return pd.read_csv(BytesIO(raw), dtype={"date": str, "symbol": str}, keep_default_na=False)


def training_rows(frame, splits):
    rows = {"train": [], "calibration": []}
    for _, group in frame.groupby("symbol", sort=True):
        prices, dates = group.close.to_numpy(), group.date.to_numpy()
        for i in range(HISTORY - 1, len(group) - HORIZON):
            part = ("train" if dates[i + HORIZON] <= splits["train_end"] else
                    "calibration" if splits["calibration_start"] <= dates[i]
                    and dates[i + HORIZON] <= splits["calibration_end"] and i % HORIZON == 0 else None)
            if part:
                row = price_row(prices[i - HISTORY + 1:i + 1])
                rows[part].append(([row[c] for c in PRICE_COLS], prices[i + HORIZON] / prices[i] - 1))
    if not rows["calibration"] or len({y > 0 for _, y in rows["train"]}) < 2:
        raise ValueError("Need earlier training examples of both up and non-up moves, plus calibration history")
    result = {k: (np.array([x for x, _ in v]), np.array([y for _, y in v])) for k, v in rows.items()}
    if not all(np.isfinite(a).all() for pair in result.values() for a in pair):
        raise ValueError("Price changes produce nonfinite features or targets")
    return result


def train_historical(frame, splits, max_iter=120):
    data = training_rows(frame, splits)
    x, y = data["train"]
    params = dict(max_iter=max_iter, max_leaf_nodes=15, l2_regularization=1., early_stopping=False, random_state=42)
    artifact = dict(interval_pad=0., horizon=HORIZON, cols=PRICE_COLS, replay_version=REPLAY_VERSION,
                    majority_up=bool(np.mean(y > 0) >= .5))
    artifact["model"] = HistGradientBoostingClassifier(**params).fit(x, y > 0)
    for name, q in [("lower", .1), ("median", .5), ("upper", .9)]:
        artifact[name] = HistGradientBoostingRegressor(loss="quantile", quantile=q, **params).fit(x, y)
    xcal, ycal = data["calibration"]
    _, lo, hi = forecast(artifact, xcal)
    scores = np.maximum(np.maximum(lo - ycal, ycal - hi), 0)
    artifact["interval_pad"] = float(np.quantile(scores, min(1, ceil((len(scores) + 1) * .8) / len(scores)), method="higher"))
    return artifact


def model_fingerprint(artifact):
    return sha256(pickle.dumps(artifact, protocol=5)).hexdigest()


def predict_prices(artifact, row, initial, cols):
    # Absent book, flow and valuation features are neutral zero; never fabricated observations.
    x = np.array([[row.get(c, 0.) for c in cols]])
    prob = float(artifact["model"].predict_proba(x)[0, 1])
    median, low, high = forecast(artifact, x)
    return dict(prob=prob, price=float(initial * (1 + median[0])),
                lower=float(initial * (1 + low[0])), upper=float(initial * (1 + high[0])),
                return_pct=float(median[0] * 100))


def direction_metrics(actual, predicted):
    if not actual:
        return dict(accuracy=None, balanced_accuracy=None)
    a, p = np.array(actual, dtype=bool), np.array(predicted, dtype=bool)
    recalls = [float(np.mean(p[a == label] == label)) for label in (False, True) if np.any(a == label)]
    return dict(accuracy=float(np.mean(a == p)), balanced_accuracy=float(np.mean(recalls)) if len(recalls) == 2 else None)


class HistoricalArena:
    kind = "historical"

    def __init__(self, frame, dataset_id, seed, duration, simulator, historical=None):
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1 or type(duration) is not int or not 100 <= duration <= 10_000:
            raise ValueError("Seed must be a uint32 and duration must be 100–10000 sessions")
        self.splits = split_dates(frame)
        choices = eligible(frame, self.splits, duration)
        if not choices:
            raise ValueError("No symbol has enough blind test sessions for this duration")
        if simulator.horizon != HORIZON:
            raise ValueError("Simulator model must have a 20-tick horizon for this comparison")
        self.historical = historical if historical is not None else train_historical(frame, self.splits)
        self.simulator = simulator.artifact
        rng = np.random.default_rng(seed)
        self.symbol = sorted(choices)[int(rng.integers(len(choices)))]
        self.tape = choices[self.symbol]
        first = int(np.flatnonzero(self.tape.date.to_numpy() >= self.splits["test_start"])[0])
        self.start = int(rng.integers(first, len(self.tape) - duration + 1))
        self.duration, self.seed, self.dataset_id = duration, seed, dataset_id
        self.id = uuid4().hex[:12]
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status, self.error, self.archived = "running", None, False
        self.elapsed = 0
        self.pending, self.predictions, self.outcomes, self.bars = [], [], [], []
        for i in range(self.start - HISTORY + 1, self.start):
            bar = self.tape.iloc[i]
            self.bars.append(dict(day=i - self.start + 1, **{c: float(bar[c]) for c in COLUMNS[2:]}))
        self.paper = {name: dict(net_pnl=0., trades=0, fees=0., position=None, pending=None, unexecuted=0)
                      for name in ("transfer", "historical")}
        self.fingerprints = dict(transfer=simulator.fingerprint, historical=model_fingerprint(self.historical))

    @property
    def terminal(self):
        return self.status in {"completed", "failed", "interrupted"}

    def finish(self):
        if not self.terminal:
            self.status = "completed"

    def step(self):
        if self.status != "running":
            return
        i = self.start + self.elapsed
        bar = self.tape.iloc[i]
        self.elapsed += 1
        day = self.elapsed
        self.bars.append(dict(day=day, **{c: float(bar[c]) for c in COLUMNS[2:]}))
        for account in self.paper.values():
            if account["pending"]:
                account["position"] = dict(entry=float(bar.open), entry_day=day, target_day=account["pending"])
                account["fees"] += float(bar.open) * .0001
                account["pending"] = None
            pos = account["position"]
            if pos and pos["target_day"] == day:
                account["net_pnl"] += float(bar.close) * .9999 - pos["entry"] * 1.0001
                account["fees"] += float(bar.close) * .0001
                account["trades"] += 1
                account["position"] = None
        for call in self.pending:
            if call["target_day"] == day:
                self.outcomes.append({**call, "actual": float(bar.close), "actual_up": bool(bar.close > call["initial"])})
        self.pending = [c for c in self.pending if c["target_day"] > day]
        prices = self.tape.close.iloc[i - HISTORY + 1:i + 1].to_numpy()
        row = price_row(prices)
        models = {"transfer": predict_prices(self.simulator, row, bar.close, OBSERVABLE_COLS),
                  "historical": predict_prices(self.historical, row, bar.close, PRICE_COLS)}
        call = dict(day=day, target_day=day + HORIZON, initial=float(bar.close), models=models,
                    persistence_up=bool(row["ret_1"] > 0), majority_up=self.historical["majority_up"])
        self.predictions.append(call)
        # Non-overlapping checkpoint labels are the only headline scoring sample.
        if (day - 1) % HORIZON == 0:
            self.pending.append(call)
            for name, signal in models.items():
                if signal["return_pct"] > .02 and not self.paper[name]["position"]:
                    if day < self.duration:
                        self.paper[name]["pending"] = day + HORIZON
                    else:
                        self.paper[name]["unexecuted"] += 1
        if day >= self.duration:
            self.finish()

    def metrics(self):
        actual = [c["actual_up"] for c in self.outcomes]
        result = {name: direction_metrics(actual, [c[f"{name}_up"] for c in self.outcomes])
                  for name in ("persistence", "majority")}
        for name in ("transfer", "historical"):
            m = direction_metrics(actual, [c["models"][name]["prob"] >= .5 for c in self.outcomes])
            m.update(mae=None, baseline_mae=None, return_mae_bps=None, baseline_return_mae_bps=None, coverage=None)
            if actual:
                m.update(mae=float(np.mean([abs(c["actual"] - c["models"][name]["price"]) for c in self.outcomes])),
                         baseline_mae=float(np.mean([abs(c["actual"] - c["initial"]) for c in self.outcomes])),
                         return_mae_bps=float(np.mean([abs(c["actual"] - c["models"][name]["price"]) / c["initial"] * 10000 for c in self.outcomes])),
                         baseline_return_mae_bps=float(np.mean([abs(c["actual"] / c["initial"] - 1) * 10000 for c in self.outcomes])),
                         coverage=float(np.mean([c["models"][name]["lower"] <= c["actual"] <= c["models"][name]["upper"] for c in self.outcomes])))
            m["verdict"] = ("Useful signal" if m["balanced_accuracy"] is not None
                            and all(m["balanced_accuracy"] > result[b]["balanced_accuracy"] for b in ("persistence", "majority"))
                            and m["mae"] < m["baseline_mae"] else "No demonstrated edge")
            result[name] = m
        return dict(n=len(actual), **result)

    def snapshot(self):
        paper = {}
        for name, account in self.paper.items():
            pos = account["position"]
            paper[name] = {**account, "unrealized_pnl": (self.bars[-1]["close"] - pos["entry"] * 1.0001) if pos else 0.}
        reveal = None
        if self.terminal:
            reveal = dict(symbol=self.symbol, start=self.tape.iloc[self.start].date,
                          end=self.tape.iloc[self.start + max(0, self.elapsed - 1)].date if self.elapsed else None,
                          planned_end=self.tape.iloc[self.start + self.duration - 1].date, splits=self.splits)
        return {"kind": self.kind, "arena": dict(kind=self.kind, id=self.id, created_at=self.created_at,
                status=self.status, error=self.error, elapsed=self.elapsed, settings=dict(seed=self.seed, duration=self.duration),
                verdict=self.metrics()["historical"]["verdict"], model_ready=True),
                "replay": dict(asset="Asset A", dataset_id=self.dataset_id, version=REPLAY_VERSION,
                horizon=HORIZON, interval_coverage=.8, model_fingerprints=self.fingerprints,
                bars=self.bars, latest=self.predictions[-1] if self.predictions else None,
                outcomes=self.outcomes, metrics=self.metrics(), paper=paper, reveal=reveal,
                unscored_checkpoints=len(self.pending))}

    def result(self):
        result = self.snapshot()
        result["replay"]["predictions"] = self.predictions
        result["replay"]["method"] = "Daily adjusted bars; 70/15/15 chronological split; purged targets and 20-session embargoes; frozen models; non-overlapping 20-session checkpoints. Transfer inputs missing from OHLCV are zero. Paper: one share, next open to target close, 1 bp/side, no liquidity model."
        return result
