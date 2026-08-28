import { useStore } from "../store";

// The ML model's live call for the selected stock + its honest running accuracy.
export default function Signal() {
  const model = useStore((s) => s.snap?.model);
  const selected = useStore((s) => s.selected);
  if (!model) return null; // no model loaded (train one: python -m ml.train --save ml/model.pkl)
  const sig = model.signals?.[selected];
  const conf = sig ? (sig.dir === "up" ? sig.prob : 1 - sig.prob) : 0;

  return (
    <div className="panel signal">
      <h2>Model Signal · {selected}</h2>
      {sig ? (
        <div className={`sig ${sig.dir}`}>
          <span className="arrow">{sig.dir === "up" ? "▲" : "▼"}</span>
          <div>
            <div className="call">predicts {sig.dir === "up" ? "UP" : "DOWN"}</div>
            <div className="conf">{(conf * 100).toFixed(0)}% confidence · suggests {sig.dir === "up" ? "BUY" : "SELL"}</div>
          </div>
        </div>
      ) : (
        <div className="muted">warming up…</div>
      )}
      <div className="acc">
        live accuracy&nbsp;
        <b>{model.accuracy != null ? `${(model.accuracy * 100).toFixed(1)}%` : "—"}</b>
        &nbsp;over {model.n.toLocaleString()} calls · {model.horizon}-tick horizon
      </div>
    </div>
  );
}
