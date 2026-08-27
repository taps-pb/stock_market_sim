import { useState } from "react";
import { useStore } from "../store";
import { placeOrder, getPortfolio } from "../api";

export default function TradeTicket() {
  const selected = useStore((s) => s.selected);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const sym = useStore((s) => s.snap?.symbols.find((x) => x.symbol === selected));
  const [qty, setQty] = useState(10);
  const [limit, setLimit] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function submit(side: "BUY" | "SELL") {
    setMsg(null);
    try {
      const price = limit.trim() === "" ? null : Number(limit);
      const res = await placeOrder({ symbol: selected, side, qty, price });
      setPortfolio(res.portfolio);
      setMsg(res.filled ? `${side} ${res.filled} @ ${res.avg_price}` : `${side} resting (0 filled)`);
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      getPortfolio().then(setPortfolio).catch(() => {});
    }
  }

  return (
    <div className="panel ticket">
      <h2>Trade · {selected}</h2>
      <div className="mkt">last {sym?.last.toFixed(2) ?? "—"} · fair {sym?.fair.toFixed(2) ?? "—"}</div>
      <label>qty
        <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(1, +e.target.value))} />
      </label>
      <label>limit (blank = market)
        <input type="number" step="0.01" value={limit} placeholder="market" onChange={(e) => setLimit(e.target.value)} />
      </label>
      <div className="btns">
        <button className="buy" onClick={() => submit("BUY")}>Buy</button>
        <button className="sell" onClick={() => submit("SELL")}>Sell</button>
      </div>
      {msg && <div className="msg">{msg}</div>}
    </div>
  );
}
