import { useStore } from "../store";
import { useState } from "react";
import { cancelOrder } from "../api";

export default function PortfolioView() {
  const p = useStore((s) => s.portfolio);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const [error, setError] = useState("");
  async function cancel(id: number) {
    try { setError(""); setPortfolio(await cancelOrder(id)); }
    catch (e) { setError((e as Error).message); }
  }
  if (!p) return null;
  return (
    <div className="panel">
      <h2>Portfolio</h2>
      <div className="pf-top">
        <div><label>cash</label><span>${p.cash.toLocaleString()}</span></div>
        <div><label>equity</label><span>${p.equity.toLocaleString()}</span></div>
        <div><label>total</label><span>${p.total.toLocaleString()}</span></div>
      </div>
      <p className="portfolio-note">Available cash ${p.available_cash.toLocaleString()} · fee {p.fee_bps} bps/side</p>
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
      {p.orders.length > 0 && <h2 className="orders-title">Open orders · until cancelled</h2>}
      {p.orders.map((o) => (
        <div className="open-order" key={o.id}>
          <span>{o.side} {o.qty} {o.symbol} @ {o.price.toFixed(2)}</span>
          <button onClick={() => cancel(o.id)} aria-label={`Cancel ${o.side} order for ${o.symbol}`}>Cancel</button>
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
