export type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };
import type { Snapshot, SavedRun } from './store';

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Check the experiment settings and try again.');
  }
  return response.json();
}
export const control = (action: string, speed?: number) => request<Snapshot>('/api/control', { action, speed: speed ?? 1 });
export const startRun = (settings: object) => request<Snapshot>('/api/runs', settings);
export const getRuns = () => request<SavedRun[]>('/api/runs');
export const getRun = (id: string) => request<Snapshot>(`/api/runs/${id}`);

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
  if (!r.ok) {
    const { detail } = await r.json();
    throw new Error(typeof detail === 'string' ? detail : 'Check the order quantity and price.');
  }
  return r.json();
}
