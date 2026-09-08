import { useState } from "react";
import { useStore } from "../store";
import { placeOrder, getPortfolio } from "../api";

export default function TradeTicket() {
  const selected = useStore((s) => s.selected);
  const running = useStore((s) => s.snap?.arena.status === 'running' && s.connected);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const sym = useStore((s) => s.snap?.symbols.find((x) => x.symbol === selected));
  const [qty, setQty] = useState(10);
  const [limit, setLimit] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function submit(side: "BUY" | "SELL") {
    setMsg(null);
    try {
      const price = limit.trim() === "" ? null : Number(limit);
      if (!Number.isInteger(qty) || qty <= 0 || (price !== null && (!Number.isFinite(price) || price < .01))) {
        throw new Error('Enter a whole share quantity and a positive limit price.');
      }
      const res = await placeOrder({ symbol: selected, side, qty, price });
      setPortfolio(res.portfolio);
      setMsg(res.filled ? `${side} ${res.filled} @ ${res.avg_price}`
        : price == null ? "No fill: no matching liquidity" : `${side} resting (0 filled)`);
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      getPortfolio().then(setPortfolio).catch(() => {});
    }
  }

  return (
    <div className="panel ticket">
      <h2>Trade · {selected}</h2>
      <div className="mkt">last {sym?.last.toFixed(2) ?? "—"} · published value {sym?.fair.toFixed(2) ?? "—"}</div>
      <label>qty
        <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(1, +e.target.value))} />
      </label>
      <label>limit (blank = market)
        <input type="number" step="0.01" value={limit} placeholder="market" onChange={(e) => setLimit(e.target.value)} />
      </label>
      <div className="btns">
        <button className="buy" disabled={!running} onClick={() => submit("BUY")}>Buy</button>
        <button className="sell" disabled={!running} onClick={() => submit("SELL")}>Sell</button>
      </div>
      {!running && <div className="msg">Trading opens when the experiment is running.</div>}
      {msg && <div className="msg">{msg}</div>}
    </div>
  );
}
