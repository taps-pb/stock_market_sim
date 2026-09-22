import { useStore } from "../store";

export default function Tape() {
  const snap = useStore((s) => s.snap);
  const selected = useStore((s) => s.selected);
  const trades = (snap?.trades ?? []).filter((t) => t.symbol === selected).slice(0, 14);
  return (
    <div className="panel tape">
      <h2>Time &amp; Sales · {selected}</h2>
      <table>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="data-row">
              <td data-label="Price" className={t.aggressor === "BUY" ? "up" : "down"}>{t.price.toFixed(2)}</td>
              <td data-label="Quantity" className="q">{t.qty}</td>
              <td data-label="Side" className="side">{t.aggressor === "BUY" ? "▲ buy" : "▼ sell"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
