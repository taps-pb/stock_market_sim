import { useStore } from "../store";

const money = (n: number | null) => n == null ? "—" : `$${n.toFixed(2)}`;
const percent = (n: number | null) => n == null ? "—" : `${(n * 100).toFixed(1)}%`;

export default function Signal() {
  const model = useStore((s) => s.snap?.model);
  const selected = useStore((s) => s.selected);
  const sig = model?.signals[selected];
  return (
    <div className="panel signal">
      <h2>Price forecast · {selected}</h2>
      {!model ? <p className="muted">Price forecasts unavailable.</p> : <>
        {sig ? <>
          <div className="forecast-price">
            <strong>{money(sig.price)}</strong>
            <span className={sig.return_pct >= 0 ? "up" : "down"}>
              {sig.return_pct >= 0 ? "+" : ""}{sig.return_pct.toFixed(2)}%
            </span>
          </div>
          <div className="conf">Median price in {model.horizon} ticks · tick {sig.target_tick}</div>
          <div className="forecast-range">
            <span>{percent(model.interval_coverage)} forecast interval</span>
            <b>{money(sig.lower)} – {money(sig.upper)}</b>
          </div>
          <p className="conf">Estimated chance of a higher close: {percent(sig.prob)}</p>
        </> : <p className="muted">Collecting price history…</p>}
        <div className="acc">
          <div>Live price error <b>{money(model.mae)}</b> · unchanged-price baseline {money(model.baseline_mae)}</div>
          <div>Direction {percent(model.accuracy)} · interval coverage {percent(model.coverage)}</div>
          <div>{model.n.toLocaleString()} matured forecasts; horizons overlap</div>
        </div>
        <details>
          <summary>Unseen-market benchmark</summary>
          <p>Price error {money(model.evaluation.mae)} vs baseline {money(model.evaluation.baseline_mae)}.
            Interval coverage {percent(model.evaluation.coverage)}.</p>
        </details>
        <p className="model-note">Trained on simulated markets. Forecasts can miss; ranges show uncertainty. Trading also pays spreads and fees.</p>
      </>}
    </div>
  );
}
