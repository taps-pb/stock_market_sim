import { useStore } from "../store";

export default function PortfolioView() {
  const p = useStore((s) => s.portfolio);
  if (!p) return null;
  return (
    <div className="panel">
      <h2>Portfolio</h2>
      <div className="pf-top">
        <div><label>cash</label><span>${p.cash.toLocaleString()}</span></div>
        <div><label>equity</label><span>${p.equity.toLocaleString()}</span></div>
        <div><label>total</label><span>${p.total.toLocaleString()}</span></div>
      </div>
      <table className="positions">
        <thead><tr><th>sym</th><th>sh</th><th>avg</th><th>last</th><th>P&amp;L</th></tr></thead>
        <tbody>
          {p.positions.map((x) => (
            <tr key={x.symbol}>
              <td>{x.symbol}</td><td>{x.shares}</td><td>{x.avg.toFixed(2)}</td>
              <td>{x.last.toFixed(2)}</td>
              <td className={x.pnl >= 0 ? "up" : "down"}>{x.pnl.toFixed(0)}</td>
            </tr>
          ))}
          {p.positions.length === 0 && <tr><td colSpan={5} className="muted">no positions</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
