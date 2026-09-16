import { useStore, type ArenaState } from '../store';
import { money, signedMoney, pct, compact, terminal } from '../format';
import EquityChart from './EquityChart';
import Chart from './Chart';
import DepthLadder from './DepthLadder';
import Signal from './Signal';
import Watchlist from './Watchlist';

export function Performance({ arena }: { arena: ArenaState }) {
  const a = arena.agent;
  const noLossHalt = arena.settings.risk_profile === 'super_risky' && (arena.policy_version ?? 1) >= 2;
  return <div className="metrics-grid">
    <div className="metric"><div className="eyebrow">Agent equity <span>USD</span></div><strong>{money(a.total, 2)}</strong><p>Started with {money(a.initial)}</p></div>
    <div className="metric"><div className="eyebrow">Net profit / loss <span>↗</span></div><strong className={a.net_pnl >= 0 ? 'up' : 'down'}>{signedMoney(a.net_pnl)}</strong><p><span className={`pill ${a.net_pnl >= 0 ? 'positive' : 'negative'}`}>{pct(a.return_pct)}</span> after trading fees</p></div>
    <div className="metric"><div className="eyebrow">Against buy &amp; hold <span>↔</span></div><strong className={arena.excess_pnl >= 0 ? 'up' : 'down'}>{signedMoney(arena.excess_pnl)}</strong><p>Benchmark {pct(arena.benchmark.return_pct)}</p></div>
    <div className="metric"><div className="eyebrow">Maximum drawdown <span>↘</span></div><strong>{a.max_drawdown_pct.toFixed(2)}<small>%</small></strong><p>{noLossHalt ? 'No automatic loss halt' : <><span className="risk-track"><i style={{ width: `${Math.min(100, a.max_drawdown_pct / (arena.settings.max_drawdown * 100) * 100)}%` }}/></span> {(arena.settings.max_drawdown * 100).toFixed(0)}% stop</>}</p></div>
  </div>;
}

export function DecisionLog({ arena }: { arena: ArenaState }) {
  const decisions = arena.decisions.filter(d => d.trader === 'ATLAS').slice(0, 12);
  return <section className="panel decision-log"><div className="panel-heading"><div><h2>Decision journal</h2><p>The reasoning. The order. The actual fill.</p></div><span className="quiet-label">ATLAS / LIVE AUDIT</span></div>
    <div className="table-scroll"><table><thead><tr><th>Tick</th><th>Action</th><th>Market</th><th>Reason</th><th className="align-right">Execution</th></tr></thead><tbody>
      {decisions.map((d, i) => <tr key={`${d.tick}-${d.symbol}-${i}`}><td className="mono dim">{d.tick}</td><td><span className={`order-side ${d.side.toLowerCase()}`}>{d.side}</span></td><td className="mono">{d.symbol}</td><td className="reason-cell">{d.reason}</td><td className="align-right mono">{d.side === 'WAIT' ? '—' : <><span className={d.filled ? '' : 'dim'}>{d.filled}/{d.qty} shares</span><small>{d.avg_price ? `@ ${money(d.avg_price, 2)}` : 'No matching fill'} · T{d.execution_tick}</small></>}</td></tr>)}
      {!decisions.length && <tr><td colSpan={5}><div className="empty-inline">Atlas is collecting 60 ticks of price and order-flow history before placing its first order.</div></td></tr>}
    </tbody></table></div>
  </section>;
}

export default function ArenaView({ onControl }: { onControl: (action: string) => void }) {
  const snap = useStore(s => s.snap);
  if (!snap) return <div className="empty-state"><div className="loading-orbit"/><h2>Connecting to the exchange</h2><p>Waiting for the local simulation server.</p></div>;
  const arena = snap.arena, a = arena.agent;
  const latest = arena.decisions.find(d => d.trader === 'ATLAS');
  const done = terminal(arena.status);
  const progress = Math.min(100, arena.elapsed / arena.settings.duration * 100);
  return <>
    <div className="page-heading"><div><div className="eyebrow">A LIVE EXPERIMENT IN AUTONOMOUS TRADING</div><h1>Give intelligence a trading account.</h1><p>Atlas trades against {Object.values(snap.groups).reduce((x, y) => x + y, 0) - 1} independent participants. The market decides what it earns.</p></div><span className="version-tag">EXPERIMENT {arena.id.slice(0, 6).toUpperCase()}</span></div>
    <Performance arena={arena}/>
    {arena.error && <div role="alert" className="notice negative">{arena.error}</div>}
    {done && <div className={`result-banner ${a.net_pnl >= 0 ? 'won' : 'lost'}`}><span className="result-symbol">{a.net_pnl >= 0 ? '↗' : '↘'}</span><div><strong>{arena.status === 'completed' ? `Experiment complete · ${arena.verdict.toLowerCase()}` : `Experiment ${arena.status}`}</strong><p>{a.positions.length ? 'Remaining inventory is marked to market; this result is not fully realized.' : `Atlas finished with ${money(a.cash, 2)} in cash, including all trading fees.`} Saved to run history.</p></div></div>}
    <div className="overview-grid">
      <section className="panel performance-panel"><EquityChart points={arena.curve}/><div className="run-progress"><div><span>{done ? 'Final result' : snap.tick < arena.warmup ? 'Observing the market' : arena.status === 'settling' ? 'Closing positions' : 'Experiment progress'}</span><b>{Math.min(arena.elapsed, arena.settings.duration).toLocaleString()} / {arena.settings.duration.toLocaleString()} ticks</b></div><div className="progress-track"><i style={{ width: `${progress}%` }}/></div></div></section>
      <section className="panel agent-panel">
        <div className="agent-identity"><div className="agent-mark">A<span>⌁</span></div><div><h2>Atlas</h2><span>Forecast-driven agent</span></div><span className={`state-dot ${arena.agent_halted ? 'warning' : ''}`}/></div>
        <div className="agent-status"><span className="eyebrow">CURRENT STATE</span><strong>{done ? 'Experiment concluded' : arena.agent_halted ? (arena.agent.positions.length ? 'Agent stopped · closing positions' : 'Agent stopped · holding cash') : snap.tick < 60 ? 'Learning the market rhythm' : arena.status === 'paused' ? 'Market paused' : arena.status === 'settling' ? 'Settling the account' : arena.settings.risk_profile === 'super_risky' ? 'FOMO mode · checking every tick' : 'Watching for an edge'}</strong><p>{latest?.reason ?? 'Reading prices, liquidity and order flow. No privileged view of other traders.'}</p></div>
        <div className="allocation"><div className="allocation-ring" style={{ background: `conic-gradient(var(--accent) ${Math.min(100, a.exposure_pct)}%, var(--line) 0)` }}><span>{a.exposure_pct.toFixed(0)}<small>%</small></span></div><div><label>Capital deployed</label><strong>{money(a.equity)}</strong><span>{money(a.cash)} available cash</span></div></div>
        <div className="agent-limits"><div><span>Position cap</span><b>{arena.settings.max_position * 100}%</b></div><div><span>Filled executions</span><b>{a.fills.toLocaleString()}</b></div><div><span>Fees paid</span><b>{money(a.fees, 2)}</b></div></div>
        <button className="button subtle full-width" disabled={done || arena.agent_halted} onClick={() => onControl('halt_agent')}>Stop agent &amp; close positions <span>↗</span></button>
      </section>
    </div>
    <div className="section-heading"><div><h2>Inside the market</h2><p>Fictional companies. Independent traders. Continuous price discovery.</p></div><span className="quiet-label">6 LISTED COMPANIES</span></div>
    <Watchlist/>
    <div className="market-grid"><Chart/><div className="market-side"><Signal/><DepthLadder/></div></div>
    <div className="lower-grid">
      <section className="panel positions-panel"><div className="panel-heading"><div><h2>Agent positions</h2><p>Actual holdings in the shared exchange.</p></div><span className="pill">{a.positions.length} open</span></div><div className="table-scroll"><table><thead><tr><th>Market</th><th>Shares</th><th>Average</th><th>Mark</th><th className="align-right">Unrealized P&amp;L</th></tr></thead><tbody>
        {a.positions.map(p => <tr key={p.symbol}><td className="symbol-name">{p.symbol}</td><td className="mono">{p.shares}</td><td className="mono">{money(p.avg, 2)}</td><td className="mono">{money(p.last, 2)}</td><td className={`mono align-right ${p.pnl >= 0 ? 'up' : 'down'}`}>{signedMoney(p.pnl)}</td></tr>)}
        {!a.positions.length && <tr><td colSpan={5}><div className="empty-inline">{done || arena.agent_halted ? 'No open positions. The account is holding cash.' : arena.settings.risk_profile === 'super_risky' ? 'All cash. Scanning each tick for a bullish forecast with affordable, available shares.' : 'All cash. Atlas will enter when a forecast clears its cost and risk limits.'}</div></td></tr>}
      </tbody></table></div><div className="panel-footer">{a.liquidation_value != null ? `Estimated cash after liquidating at current book depth: ${money(a.liquidation_value, 2)}` : `${a.illiquid_shares} shares currently lack enough exit liquidity.`}</div></section>
      <section className="panel news-panel"><div className="panel-heading"><div><h2>Market events</h2><p>What is moving valuations.</p></div><span className="live-indicator">●</span></div>
        {snap.events.slice(0, 4).map((e, i) => <div className="news-item" key={`${e.tick}-${i}`}><span className={`news-dot ${e.surprise >= 0 ? 'positive' : 'negative'}`}/><div><strong>{e.symbol} {e.type === 'earnings' ? 'reports earnings' : 'valuation revised'}</strong><p>{e.type === 'earnings' ? 'Earnings surprise' : 'News-driven revision'} <span className={e.surprise >= 0 ? 'up' : 'down'}>{pct(e.surprise * 100)}</span></p><small>T{e.tick} · SIMULATED NEWS</small></div></div>)}
        {!snap.events.length && <div className="empty-inline">No news yet. Company reports and unexpected events will appear here.</div>}
      </section>
    </div>
    <DecisionLog arena={arena}/>
    <div className="workspace-note">{compact(a.initial)} of simulated capital · Public market inputs only · Fills, spreads and fees determine P&amp;L</div>
  </>;
}
