import { create } from "zustand";

export type Depth = { bids: [number, number][]; asks: [number, number][] };
export type Phase = "accumulate" | "markup" | "distribute" | "markdown";
export type Sym = {
  symbol: string; name: string; last: number; fair: number;
  bid: number | null; ask: number | null; open: number; volume: number; depth: Depth;
  phase: Phase | null;
};
export type Trade = { tick: number; symbol: string; price: number; qty: number; aggressor: string };
export type Signal = { dir: "up" | "down"; prob: number };
export type Model = {
  signals: Record<string, Signal>;
  accuracy: number | null;
  n: number;
  horizon: number;
};
export type Snapshot = {
  tick: number; symbols: Sym[];
  sentiment: { fear: number; greed: number };
  groups: Record<string, number>;
  model?: Model;
  trades: Trade[]; events: { tick: number; type: string; symbol: string; surprise: number }[];
};
export type Position = { symbol: string; shares: number; avg: number; last: number; value: number; pnl: number };
export type Portfolio = { cash: number; positions: Position[]; equity: number; total: number };

type State = {
  snap?: Snapshot;
  selected: string;
  portfolio?: Portfolio;
  setSnap: (s: Snapshot) => void;
  select: (s: string) => void;
  setPortfolio: (p: Portfolio) => void;
};

export const useStore = create<State>((set) => ({
  selected: "NOVA",
  setSnap: (snap) => set({ snap }),
  select: (selected) => set({ selected }),
  setPortfolio: (portfolio) => set({ portfolio }),
}));
