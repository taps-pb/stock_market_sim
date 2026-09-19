import { useEffect, useState } from 'react';
import { getRuns, getRun } from '../api';
import { useStore, isReplay, type AnySnapshot, type RunItem } from '../store';
import { money, pct, signedMoney } from '../format';
import { Performance, DecisionLog } from './ArenaView';
import EquityChart from './EquityChart';
import ReplayView from './ReplayView';

export default function RunHistory() {
  const current = useStore(s => s.snap?.arena);
  const terminalId = useStore(s => {
    const a = s.replay?.arena ?? s.snap?.arena;
    return a && ['completed', 'failed', 'interrupted'].includes(a.status) ? a.id : '';
  });
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selected, setSelected] = useState<AnySnapshot | null>(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0), [total, setTotal] = useState(0), [kind, setKind] = useState('');
  useEffect(() => {
    let alive = true;
    setLoading(true); setError('');
    getRuns(offset, kind).then(page => { if (alive) { setRuns(page.items); setTotal(page.total); } })
      .catch(e => { if (alive) setError(e.message); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [offset, kind, terminalId]);
  async function open(id: string) { setError(''); try { setSelected(await getRun(id)); } catch (e) { setError((e as Error).message); } }
  function download() {
    if (!selected) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(selected, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = `market-lab-${selected.arena.id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (selected) {
    const controls = <div className="panel-heading"><button className="text-button" onClick={() => setSelected(null)}>← All experiments</button><button className="button" onClick={download}>Export run JSON ↗</button></div>;
    if (isReplay(selected)) return <>{controls}<ReplayView snapshot={selected}/></>;
    const a = selected.arena;
    return <>{controls}
      <div className="page-heading"><div><div className="eyebrow">ARCHIVED EXPERIMENT · SEED {a.settings.seed}</div><h1>{a.verdict}</h1><p>{a.settings.scenario} market · {a.elapsed.toLocaleString()} trading ticks · {new Date(a.created_at).toLocaleString()}</p></div></div>
      <Performance arena={a}/><section className="panel"><EquityChart points={a.curve}/></section>
      <div className="notice">{a.agent.positions.length ? 'Open inventory remains. Equity includes unrealized P&L and may not be executable.' : `All agent positions closed. Final cash: ${money(a.agent.cash, 2)}.`} Status: {a.status}. Orders used the live matching engine. {a.benchmark.positions.length > 0 && 'Benchmark inventory remains; its P&L includes unrealized value.'}</div>
      <DecisionLog arena={{ ...a, decisions: a.decisions.slice().reverse() }}/>
    </>;
  }
  const settled = runs.filter(r => r.kind === 'synthetic').filter(r => r.status === 'completed' && !r.agent.positions.length
    && r.sim_version === current?.sim_version && r.model_fingerprint === current?.model_fingerprint);
  const wins = settled.filter(r => r.agent.net_pnl > 0).length, losses = settled.filter(r => r.agent.net_pnl < 0).length;
  return <>
    <div className="page-heading"><div><div className="eyebrow">EVIDENCE OVER IMPRESSIONS</div><h1>Keep every result.</h1><p>{total} saved experiments. Synthetic trading and historical forecast evidence stay separate.</p></div><span className="version-tag">SAVED LOCALLY</span></div>
    <label>Experiment type<select value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}><option value="">All experiments</option><option value="synthetic">Synthetic exchange</option><option value="historical">Historical replay</option></select></label>
    {current && <div className="notice">This page, current synthetic model / market v{current.sim_version}: {wins} profit / {losses} loss / {settled.length - wins - losses} flat. Repeated seeds are not independent trials. Historical runs are excluded.</div>}
    {error && <div className="notice negative" role="alert">{error}</div>}
    <section className="panel"><div className="panel-heading"><h2>Experiment archive</h2><span>{loading ? 'Loading…' : `${total ? offset + 1 : 0}–${Math.min(offset + runs.length, total)} of ${total}`}</span></div><div className="table-scroll"><table><thead><tr><th>Experiment</th><th>Market</th><th>Outcome</th><th>Status</th><th/></tr></thead><tbody>
      {runs.map(r => <tr key={r.id}><td><strong className="mono">{r.kind === 'historical' ? 'Replay' : `v${r.sim_version ?? '?'}`} · Seed {r.settings.seed}</strong><small>{new Date(r.created_at).toLocaleDateString()} · {r.elapsed} {r.kind === 'historical' ? 'sessions' : 'ticks'}</small></td><td>{r.kind === 'historical' ? 'Daily OHLCV' : r.settings.scenario}</td><td>{r.kind === 'historical' ? r.verdict : <><span className={`outcome-badge ${r.agent.net_pnl > 0 ? 'positive' : r.agent.net_pnl < 0 ? 'negative' : 'flat'}`}>{signedMoney(r.agent.net_pnl)} · {pct(r.agent.return_pct)}</span><small>vs hold {signedMoney(r.excess_pnl)}{r.benchmark.positions.length ? ' · benchmark inventory remains' : ''}{r.manual_interventions ? ' · manual trades' : ''}</small></>}</td><td>{r.status}</td><td><button className="text-button" onClick={() => open(r.id)}>Inspect ↗</button></td></tr>)}
      {!loading && !runs.length && <tr><td colSpan={5}>No saved experiments in this filter.</td></tr>}
    </tbody></table></div><div className="panel-heading"><button className="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 30))}>Previous</button><button className="button" disabled={loading || offset + 30 >= total} onClick={() => setOffset(offset + 30)}>Next</button></div></section>
  </>;
}
