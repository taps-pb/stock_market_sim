import { create } from "zustand";

export type Depth = { bids: [number, number][]; asks: [number, number][] };
export type Sym = {
  symbol: string; name: string; last: number; fair: number;
  bid: number | null; ask: number | null; open: number; volume: number; depth: Depth;
};
export type Trade = { tick: number; symbol: string; price: number; qty: number; aggressor: string };
export type Snapshot = {
  tick: number; symbols: Sym[];
  sentiment: { fear: number; greed: number };
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
