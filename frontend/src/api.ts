export type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };
import type { Snapshot, AnySnapshot, RunItem, Dataset, Portfolio, ReplaySnapshot } from './store';

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Check the experiment settings and try again.');
  }
  return response.json();
}
export const control = (action: string, speed?: number) => request<AnySnapshot>('/api/control', { action, speed: speed ?? 1 });
export const startRun = (settings: object) => request<Snapshot>('/api/runs', settings);
export const getRuns = (offset = 0, kind = '') => request<{items: RunItem[]; total: number}>(`/api/runs?limit=30&offset=${offset}${kind ? `&kind=${kind}` : ''}`);
export const getRun = (id: string) => request<AnySnapshot>(`/api/runs/${id}`);
export const getDatasets = () => request<Dataset[]>('/api/replay-datasets');
export const startReplay = (settings: { dataset_id: string; seed: number; duration: number }) => request<ReplaySnapshot>('/api/replay-runs', settings);
export async function importDataset(file: File): Promise<Dataset> {
  if (file.size > 10 * 1024 * 1024) throw new Error('CSV exceeds 10 MiB.');
  const response = await fetch(`/api/replay-datasets?name=${encodeURIComponent(file.name)}`, { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file });
  if (!response.ok) throw new Error((await response.json()).detail ?? 'CSV import failed');
  return response.json();
}

export const getCandles = (s: string): Promise<Candle[]> =>
  request<Candle[]>(`/api/symbols/${s}/candles`);

export const getPortfolio = () => request<Portfolio>('/api/portfolio');

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
