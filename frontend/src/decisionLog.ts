import type { Decision } from './store';

export type ActionFilter = 'ALL' | 'BUY' | 'SELL';
export type ExecutionFilter = 'ALL' | 'FILLED' | 'PARTIAL' | 'UNFILLED';

export const isActionable = (decision: Decision) =>
  decision.trader === 'ATLAS' && (decision.side === 'BUY' || decision.side === 'SELL');

export const decisionKey = (decision: Decision) =>
  `${decision.tick}:${decision.execution_tick ?? ''}:${decision.symbol}:${decision.side}`;

export function executionOf(decision: Decision): Exclude<ExecutionFilter, 'ALL'> {
  if (decision.filled >= decision.qty) return 'FILLED';
  return decision.filled > 0 ? 'PARTIAL' : 'UNFILLED';
}

export function mergeDecisions(...groups: Decision[][]): Decision[] {
  const seen = new Set<string>();
  return groups.flat().filter(isActionable).sort((a, b) => b.tick - a.tick).filter(decision => {
    const key = decisionKey(decision);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function filterDecisions(rows: Decision[], action: ActionFilter, market: string, execution: ExecutionFilter) {
  return rows.filter(decision =>
    (action === 'ALL' || decision.side === action) &&
    (!market || decision.symbol === market) &&
    (execution === 'ALL' || executionOf(decision) === execution));
}
