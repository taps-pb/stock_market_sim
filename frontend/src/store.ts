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
  capital: number; seed: number; duration: number; scenario: string; risk_profile?: string;
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
  kind?: 'synthetic';
  id: string; created_at: string; status: string; error: string | null; speed: number;
  settings: RunSettings; agent_halted: boolean; elapsed: number; warmup: number;
  verdict: string; agent: Account; benchmark: Account; excess_pnl: number;
  curve: CurvePoint[]; decisions: Decision[]; fills: Fill[]; population: Population[]; model_ready: boolean;
  sim_version: number; policy_version?: number; model_fingerprint: string | null; manual_interventions: number;
};
export type SavedRun = Pick<ArenaState, 'id' | 'created_at' | 'status' | 'settings' | 'elapsed' | 'verdict' | 'agent' | 'benchmark' | 'excess_pnl' | 'sim_version' | 'model_fingerprint' | 'manual_interventions'>;

export type Dataset = { id: string; name: string; rows: number; symbols: string[]; start: string; end: string; max_duration: number };
export type ReplaySignal = { prob: number; price: number; lower: number; upper: number; return_pct: number };
export type ReplayCall = { day: number; target_day: number; initial: number; models: Record<'transfer' | 'historical', ReplaySignal>; actual?: number; actual_up?: boolean };
export type ReplayMetric = { accuracy: number | null; balanced_accuracy: number | null; mae?: number | null; baseline_mae?: number | null; return_mae_bps?: number | null; baseline_return_mae_bps?: number | null; coverage?: number | null; verdict?: string };
export type ReplaySnapshot = {
  kind: 'historical';
  arena: { kind: 'historical'; id: string; created_at: string; status: string; error: string | null; speed: number; elapsed: number; settings: { seed: number; duration: number }; verdict: string; model_ready: boolean };
  replay: {
    asset: string; dataset_id: string; horizon: number; interval_coverage: number; model_fingerprints: Record<string, string>;
    bars: { day: number; open: number; high: number; low: number; close: number; volume: number }[];
    latest: ReplayCall | null; outcomes: ReplayCall[]; unscored_checkpoints: number;
    metrics: { n: number; transfer: ReplayMetric; historical: ReplayMetric; persistence: ReplayMetric; majority: ReplayMetric };
    paper: Record<string, { net_pnl: number; trades: number; fees: number; unrealized_pnl: number; position: { entry: number; entry_day: number; target_day: number } | null; pending: number | null }>;
    reveal: { symbol: string; start: string; end: string | null; planned_end: string; splits: Record<string, string> } | null;
  };
};
export type AnySnapshot = Snapshot | ReplaySnapshot;
export const isReplay = (s: AnySnapshot): s is ReplaySnapshot => 'replay' in s;
export type RunItem = (SavedRun & { kind: 'synthetic' }) | ReplaySnapshot['arena'];

type State = {
  snap?: Snapshot;
  replay?: ReplaySnapshot;
  selected: string;
  portfolio?: Portfolio;
  connected: boolean;
  setConnected: (connected: boolean) => void;
  setSnap: (s: AnySnapshot) => void;
  select: (s: string) => void;
  setPortfolio: (p: Portfolio) => void;
};

export const useStore = create<State>((set) => ({
  selected: "NOVA",
  connected: false,
  setConnected: (connected) => set({ connected }),
  setSnap: (snap) => set(isReplay(snap) ? { replay: snap, snap: undefined, portfolio: undefined }
    : { snap, replay: undefined }),
  select: (selected) => set({ selected }),
  setPortfolio: (portfolio) => set({ portfolio }),
}));
