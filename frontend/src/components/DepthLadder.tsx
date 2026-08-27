import { useStore } from "../store";

export default function DepthLadder() {
  const snap = useStore((s) => s.snap);
  const selected = useStore((s) => s.selected);
  const sym = snap?.symbols.find((x) => x.symbol === selected);
  if (!sym) return null;
  const max = Math.max(
    1,
    ...sym.depth.bids.map((b) => b[1]),
    ...sym.depth.asks.map((a) => a[1])
  );
  return (
    <div className="panel">
      <h2>Order Book · {selected}</h2>
      <div className="ladder">
        {sym.depth.asks.slice().reverse().map(([p, q]) => (
          <div key={"a" + p} className="lvl">
            <i className="fill ask" style={{ width: `${(q / max) * 100}%` }} />
            <span className="down">{p.toFixed(2)}</span><span className="q">{q}</span>
          </div>
        ))}
        <div className="spread">
          spread {sym.bid && sym.ask ? (sym.ask - sym.bid).toFixed(2) : "—"}
        </div>
        {sym.depth.bids.map(([p, q]) => (
          <div key={"b" + p} className="lvl">
            <i className="fill bid" style={{ width: `${(q / max) * 100}%` }} />
            <span className="up">{p.toFixed(2)}</span><span className="q">{q}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
