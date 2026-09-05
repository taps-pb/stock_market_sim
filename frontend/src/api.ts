export type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };

export const getCandles = (s: string): Promise<Candle[]> =>
  fetch(`/api/symbols/${s}/candles`).then((r) => r.json());

export const getPortfolio = () => fetch("/api/portfolio").then((r) => r.json());

export async function cancelOrder(id: number) {
  const r = await fetch(`/api/orders/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error((await r.json()).detail ?? "cancel rejected");
  return r.json();
}

export async function placeOrder(body: {
  symbol: string; side: "BUY" | "SELL"; qty: number; price?: number | null;
}) {
  const r = await fetch("/api/orders", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "order rejected");
  return r.json();
}
