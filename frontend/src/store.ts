import { create } from "zustand";

export type Depth = { bids: [number, number][]; asks: [number, number][] };
export type Phase = "accumulate" | "markup" | "distribute" | "markdown";
export type Sym = {
  symbol: string; name: string; last: number; fair: number;
  bid: number | null; ask: number | null; open: number; volume: number; depth: Depth;
  phase: Phase | null;
  sector: string; history: number[];
};
export type Trade = { tick: number; symbol: string; price: number; qty: number; aggressor: string };
export type Signal = {
  dir: "up" | "down"; prob: number; price: number; lower: number; upper: number;
  return_pct: number; target_tick: number;
};
export type Model = {
  signals: Record<string, Signal>;
  accuracy: number | null;
  n: number;
  horizon: number;
  mae: number | null;
  baseline_mae: number | null;
  coverage: number | null;
  interval_coverage: number;
  evaluation: { mae: number; baseline_mae: number; coverage: number; direction_accuracy: number };
};
export type Snapshot = {
  tick: number; symbols: Sym[];
  sentiment: { fear: number; greed: number };
  groups: Record<string, number>;
  model?: Model | null;
  arena: ArenaState;
  trades: Trade[]; events: { tick: number; type: string; symbol: string; surprise: number }[];
};
export type Position = { symbol: string; shares: number; avg: number; last: number; value: number; pnl: number };
export type Portfolio = {
  cash: number; available_cash: number; fee_bps: number;
  orders: { id: number; symbol: string; side: string; qty: number; price: number }[];
  positions: Position[]; equity: number; total: number;
  fees: number; realized_pnl: number;
};

export type Account = Portfolio & {
  id: string; initial: number; net_pnl: number; return_pct: number;
  max_drawdown_pct: number; exposure_pct: number; fills: number;
  unrealized_pnl: number; liquidation_value: number | null; illiquid_shares: number;
};
export type RunSettings = {
  capital: number; seed: number; duration: number; scenario: string;
  max_position: number; max_exposure: number; max_drawdown: number;
  stop_loss: number; min_probability: number; min_edge_bps: number;
  slippage_bps: number; participation: number;
};
export type CurvePoint = { tick: number; agent: number; hold: number; cash: number };
export type Decision = {
  tick: number; execution_tick?: number; trader: string; side: string; symbol: string;
  qty: number; filled: number; price: number | null; reason: string; avg_price?: number | null;
};
export type Fill = { tick: number; symbol: string; side: string; qty: number; price: number; fee: number };
export type Population = {
  name: string; count: number; capital: number; return_pct: number; fear: number; greed: number;
  buy_volume: number; sell_volume: number;
};
export type ArenaState = {
  id: string; created_at: string; status: string; error: string | null; speed: number;
  settings: RunSettings; agent_halted: boolean; elapsed: number; warmup: number;
  verdict: string; agent: Account; benchmark: Account; excess_pnl: number;
  curve: CurvePoint[]; decisions: Decision[]; fills: Fill[]; population: Population[]; model_ready: boolean;
};
export type SavedRun = Pick<ArenaState, 'id' | 'created_at' | 'status' | 'settings' | 'elapsed' | 'verdict' | 'agent' | 'benchmark' | 'excess_pnl'>;

type State = {
  snap?: Snapshot;
  selected: string;
  portfolio?: Portfolio;
  connected: boolean;
  setConnected: (connected: boolean) => void;
  setSnap: (s: Snapshot) => void;
  select: (s: string) => void;
  setPortfolio: (p: Portfolio) => void;
};

export const useStore = create<State>((set) => ({
  selected: "NOVA",
  connected: false,
  setConnected: (connected) => set({ connected }),
  setSnap: (snap) => set({ snap }),
  select: (selected) => set({ selected }),
  setPortfolio: (portfolio) => set({ portfolio }),
}));
