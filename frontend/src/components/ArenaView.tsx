import { useEffect, useMemo, useState } from 'react';
import { useStore, type ArenaState, type Decision } from '../store';
import { money, signedMoney, pct, compact, terminal } from '../format';
import { getDecisions } from '../api';
import { filterDecisions, mergeDecisions, executionOf, type ActionFilter, type ExecutionFilter } from '../decisionLog';
import EquityChart from './EquityChart';
import Chart from './Chart';
import DepthLadder from './DepthLadder';
import Signal from './Signal';
import MarketForecastBoard from './MarketForecastBoard';
import ForecastReview from './ForecastReview';
import MarketOutlook from './MarketOutlook';

export function Performance({ arena }: { arena: ArenaState }) {
  const a = arena.agent;
  const noLossHalt = arena.settings.risk_profile === 'super_risky' && (arena.policy_version ?? 1) >= 2;
  return <div className="metrics-grid arena-summary">
    <div className={`metric hero ${a.net_pnl >= 0 ? 'positive' : 'negative'}`}><div className="eyebrow">Net result after fees</div><strong className={a.net_pnl >= 0 ? 'up' : 'down'}>{signedMoney(a.net_pnl)}</strong><p><span className={`pill ${a.net_pnl >= 0 ? 'positive' : 'negative'}`}>{pct(a.return_pct)}</span> against {money(a.initial)} starting capital</p></div>
    <div className="metric"><div className="eyebrow">Account equity <span>USD</span></div><strong>{money(a.total, 2)}</strong><p>{money(a.cash)} available cash</p></div>
    <div className="metric"><div className="eyebrow">Excess vs. buy &amp; hold</div><strong className={arena.excess_pnl >= 0 ? 'up' : 'down'}>{signedMoney(arena.excess_pnl)}</strong><p>Benchmark {pct(arena.benchmark.return_pct)}</p></div>
    <div className="metric"><div className="eyebrow">Maximum drawdown</div><strong>{a.max_drawdown_pct.toFixed(2)}<small>%</small></strong><p>{noLossHalt ? 'No automatic loss halt' : <><span className="risk-track"><i style={{ width: `${Math.min(100, a.max_drawdown_pct / (arena.settings.max_drawdown * 100) * 100)}%` }}/></span> {(arena.settings.max_drawdown * 100).toFixed(0)}% stop</>}</p></div>
  </div>;
}

export function DecisionLog({ arena, live = false }: { arena: ArenaState; live?: boolean }) {
  const [history, setHistory] = useState<{ runId: string; rows: Decision[] } | null>(null);
  const [action, setAction] = useState<ActionFilter>('ALL');
  const [market, setMarket] = useState('');
  const [execution, setExecution] = useState<ExecutionFilter>('ALL');
  useEffect(() => {
    setAction('ALL'); setMarket(''); setExecution('ALL');
    if (!live) return;
    let active = true;
    getDecisions().then(rows => { if (active) setHistory({ runId: arena.id, rows }); }).catch(() => {});
    return () => { active = false; };
  }, [arena.id, live]);
  const decisions = useMemo(() => mergeDecisions(
    arena.decisions,
    history?.runId === arena.id ? history.rows : [],
  ), [arena.decisions, arena.id, history]);
  const markets = useMemo(() => [...new Set(decisions.map(d => d.symbol))].sort(), [decisions]);
  const visible = useMemo(() => filterDecisions(decisions, action, market, execution), [decisions, action, market, execution]);
  return <section className="panel decision-log"><div className="panel-heading"><div><h2>Decision journal</h2><p>Atlas order attempts, rationale, and execution results.</p></div><div className="decision-heading-meta"><span className="quiet-label">Atlas · {live ? 'live' : 'archived'}</span><span className="decision-count"><b>{visible.length}</b> of {decisions.length}</span></div></div>
    <div className="decision-toolbar">
      <div className="decision-action-filters" role="group" aria-label="Filter by action">
        {(['ALL', 'BUY', 'SELL'] as ActionFilter[]).map(value => <button key={value} type="button" aria-pressed={action === value} onClick={() => setAction(value)}>{value === 'ALL' ? 'All actions' : value === 'BUY' ? 'Buys' : 'Sells'}</button>)}
      </div>
      <div className="decision-dropdowns">
        <label><span>Market</span><select value={market} onChange={e => setMarket(e.target.value)}><option value="">All stocks</option>{markets.map(symbol => <option key={symbol} value={symbol}>{symbol}</option>)}</select></label>
        <label><span>Execution</span><select value={execution} onChange={e => setExecution(e.target.value as ExecutionFilter)}><option value="ALL">All results</option><option value="FILLED">Filled</option><option value="PARTIAL">Partial</option><option value="UNFILLED">Unfilled</option></select></label>
      </div>
    </div>
    <div className="table-scroll decision-scroll"><table><thead><tr><th>Tick</th><th>Action</th><th>Market</th><th>Reason</th><th className="align-right">Execution</th></tr></thead><tbody>
      {visible.map(d => <tr key={`${d.tick}-${d.execution_tick}-${d.symbol}-${d.side}`} className="data-row"><td data-label="Tick" className="mono dim">{d.tick}</td><td data-label="Action"><span className={`order-side ${d.side.toLowerCase()}`}>{d.side}</span></td><td data-label="Market" className="mono">{d.symbol}</td><td data-label="Reason" className="reason-cell">{d.reason}</td><td data-label="Execution" className="align-right mono"><span className={d.filled ? '' : 'dim'}>{d.filled}/{d.qty} shares</span><small>{executionOf(d).toLowerCase()} · {d.avg_price != null ? `@ ${money(d.avg_price, 2)}` : 'No fill'}{d.execution_tick != null ? ` · T${d.execution_tick}` : ''}</small></td></tr>)}
      {!decisions.length && <tr className="data-row empty-row"><td colSpan={5}><div className="empty-inline">No Atlas orders attempted yet. Passive observation ticks are hidden.</div></td></tr>}
      {!!decisions.length && !visible.length && <tr className="data-row empty-row"><td colSpan={5}><div className="empty-inline">No order attempts match these filters.</div></td></tr>}
    </tbody></table></div>
  </section>;
}

export default function ArenaView({ onControl }: { onControl: (action: string) => void }) {
  const snap = useStore(s => s.snap);
  if (!snap) return <div className="empty-state"><div className="loading-orbit"/><h2>Connecting to the exchange</h2><p>Waiting for the local simulation server.</p></div>;
  const arena = snap.arena, a = arena.agent;
  const latest = arena.decisions.find(d => d.trader === 'ATLAS');
  const done = terminal(arena.status);
  const warmingUp = !done && snap.tick < arena.warmup;
  const progress = Math.min(100, arena.elapsed / arena.settings.duration * 100);
  const resultDirection = a.net_pnl > 0 ? 'up' : a.net_pnl < 0 ? 'down' : 'flat at';
  const headlineAmount = money(Math.abs(a.net_pnl), 2);
  return <>
    <div className="title-row arena-headline"><div><div className="eyebrow">Live · {arena.settings.scenario} market</div><h1>Atlas is {resultDirection} <span>{headlineAmount}</span> today.</h1></div><div className="run-id">RUN {arena.id.slice(0, 6).toUpperCase()} · SEED {arena.settings.seed}</div></div>
    {warmingUp && <div className="warmup-notice" role="status"><span className="loading-orbit"/><div><strong>Atlas is collecting market history</strong><p>Gathering prices, liquidity and order flow before trading begins.</p></div><b>{snap.tick} / {arena.warmup} ticks</b></div>}
    <Performance arena={arena}/>
    {arena.error && <div role="alert" className="notice negative">{arena.error}</div>}
    {done && <div className={`result-banner ${a.net_pnl >= 0 ? 'won' : 'lost'}`}><div><strong>{arena.status === 'completed' ? `Experiment complete · ${arena.verdict.toLowerCase()}` : `Experiment ${arena.status}`}</strong><p>{a.positions.length ? 'Remaining inventory is marked to market; this result is not fully realized.' : `Atlas finished with ${money(a.cash, 2)} in cash, including all trading fees.`} Saved to run history.</p></div></div>}
    <div className="overview-grid arena-workbench">
      <section className="panel performance-panel"><EquityChart points={arena.curve}/><div className="run-progress"><div><span>{done ? 'Final result' : snap.tick < arena.warmup ? 'Observing the market' : arena.status === 'settling' ? 'Closing positions' : 'Experiment progress'}</span><b>{Math.min(arena.elapsed, arena.settings.duration).toLocaleString()} / {arena.settings.duration.toLocaleString()} ticks</b></div><div className="progress-track"><i style={{ width: `${progress}%` }}/></div></div></section>
      <section className="panel agent-panel">
        <div className="agent-identity"><div className="agent-mark">A</div><div><h2>Atlas</h2><span>Forecast-driven agent</span></div><span className={`state-dot ${arena.agent_halted ? 'warning' : ''}`}/></div>
        <div className="agent-status"><span className="eyebrow">CURRENT STATE</span><strong>{done ? 'Experiment concluded' : arena.agent_halted ? (arena.agent.positions.length ? 'Agent stopped · closing positions' : 'Agent stopped · holding cash') : warmingUp ? 'Waiting for market history' : arena.status === 'paused' ? 'Market paused' : arena.status === 'settling' ? 'Settling the account' : arena.settings.risk_profile === 'super_risky' ? 'FOMO mode · checking every tick' : 'Watching for an edge'}</strong><p>{latest?.reason ?? 'Reading prices, liquidity and order flow. No privileged view of other traders.'}</p></div>
        <div className="allocation"><div className="allocation-ring" style={{ background: `conic-gradient(var(--accent) ${Math.min(100, a.exposure_pct)}%, var(--line) 0)` }}><span>{a.exposure_pct.toFixed(0)}<small>%</small></span></div><div><label>Capital deployed</label><strong>{money(a.equity)}</strong><span>{money(a.cash)} available cash</span></div></div>
        <div className="agent-limits"><div><span>Position cap</span><b>{arena.settings.max_position * 100}%</b></div><div><span>Filled executions</span><b>{a.fills.toLocaleString()}</b></div><div><span>Fees paid</span><b>{money(a.fees, 2)}</b></div></div>
        <button className="button subtle full-width" disabled={done || arena.agent_halted} onClick={() => onControl('halt_agent')}>Stop agent &amp; close positions</button>
      </section>
    </div>
    <div className="section-heading"><div><h2>Inside the market</h2><p>Fictional companies, independent traders, continuous price discovery.</p></div><span className="quiet-label">6 listed companies</span></div>
    <MarketForecastBoard/>
    <MarketOutlook model={snap.model} symbols={snap.symbols}/>
    <ForecastReview model={snap.model} symbols={snap.symbols}/>
    <div className="market-grid"><Chart/><div className="market-side"><Signal/><DepthLadder/></div></div>
    <div className="lower-grid arena-lower">
      <section className="panel positions-panel"><div className="panel-heading"><div><h2>Agent positions</h2><p>Actual holdings in the shared exchange.</p></div><span className="pill">{a.positions.length} open</span></div><div className="table-scroll"><table><thead><tr><th>Market</th><th>Shares</th><th>Average</th><th>Mark</th><th className="align-right">Unrealized P&amp;L</th></tr></thead><tbody>
        {a.positions.map(p => <tr key={p.symbol} className="data-row"><td data-label="Market" className="symbol-name">{p.symbol}</td><td data-label="Shares" className="mono">{p.shares}</td><td data-label="Average" className="mono">{money(p.avg, 2)}</td><td data-label="Mark" className="mono">{money(p.last, 2)}</td><td data-label="Unrealized P&amp;L" className={`mono align-right ${p.pnl >= 0 ? 'up' : 'down'}`}>{signedMoney(p.pnl)}</td></tr>)}
        {!a.positions.length && <tr className="data-row empty-row"><td colSpan={5}><div className="empty-inline">{done || arena.agent_halted ? 'No open positions. The account is holding cash.' : arena.settings.risk_profile === 'super_risky' ? 'All cash. Scanning each tick for a bullish forecast with affordable, available shares.' : 'All cash. Atlas will enter when a forecast clears its cost and risk limits.'}</div></td></tr>}
      </tbody></table></div><div className="panel-footer">{a.liquidation_value != null ? `Estimated cash after liquidating at current book depth: ${money(a.liquidation_value, 2)}` : `${a.illiquid_shares} shares currently lack enough exit liquidity.`}</div></section>
      <section className="panel news-panel"><div className="panel-heading"><div><h2>Market events</h2><p>Recent valuation movers.</p></div></div>
        {snap.events.slice(0, 4).map((e, i) => <div className="news-item" key={`${e.tick}-${i}`}><span className={`news-dot ${e.surprise >= 0 ? 'positive' : 'negative'}`}/><div><strong>{e.symbol} {e.type === 'earnings' ? 'reports earnings' : 'valuation revised'}</strong><p>{e.type === 'earnings' ? 'Earnings surprise' : 'News-driven revision'} <span className={e.surprise >= 0 ? 'up' : 'down'}>{pct(e.surprise * 100)}</span></p><small>T{e.tick} · SIMULATED NEWS</small></div></div>)}
        {!snap.events.length && <div className="empty-inline">No news yet. Company reports and unexpected events will appear here.</div>}
      </section>
    </div>
    <DecisionLog arena={arena} live/>
    <div className="workspace-note">{compact(a.initial)} of simulated capital · Public market inputs only · Fills, spreads and fees determine P&amp;L</div>
  </>;
}
