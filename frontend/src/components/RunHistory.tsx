import { useEffect, useState } from 'react';
import { getRuns, getRun } from '../api';
import type { SavedRun, Snapshot } from '../store';
import { money, pct, signedMoney } from '../format';
import { Performance, DecisionLog } from './ArenaView';
import EquityChart from './EquityChart';

export default function RunHistory() {
  const [runs, setRuns] = useState<SavedRun[]>([]);
  const [selected, setSelected] = useState<Snapshot | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => { getRuns().then(setRuns).catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  async function open(id: string) { try { setSelected(await getRun(id)); } catch (e) { setError((e as Error).message); } }
  function download() {
    if (!selected) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(selected, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = `market-lab-${selected.arena.id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (selected) {
    const a = selected.arena;
    const journal = { ...a, decisions: a.decisions.slice().reverse() };
    return <>
      <button className="text-button" onClick={() => setSelected(null)}>← All experiments</button>
      <div className="page-heading"><div><div className="eyebrow">ARCHIVED EXPERIMENT · SEED {a.settings.seed}</div><h1>{a.verdict === 'Profitable' ? 'The agent made money.' : a.verdict === 'Loss' ? 'The market won this round.' : 'An experiment, on record.'}</h1><p>{a.settings.scenario} market · {a.elapsed.toLocaleString()} trading ticks · {new Date(a.created_at).toLocaleString()}</p></div><button className="button" onClick={download}>Export run JSON ↗</button></div>
      <Performance arena={a}/><section className="panel"><EquityChart points={a.curve}/></section>
      <div className="notice">{a.agent.positions.length ? 'Open inventory remains. Equity includes unrealized P&L and may not be executable.' : `All agent positions closed. Final cash: ${money(a.agent.cash, 2)}.`} Status: {a.status}. Every order was matched in the live simulation.</div>
      <DecisionLog arena={journal}/>
    </>;
  }
  const settled = runs.filter(r => r.status === 'completed' && !r.agent.positions.length && !r.benchmark.positions.length);
  const wins = settled.filter(r => r.agent.net_pnl > 0).length;
  return <>
    <div className="page-heading"><div><div className="eyebrow">EVIDENCE OVER IMPRESSIONS</div><h1>Keep every result.</h1><p>Finished and interrupted experiments stay here. Good runs and bad ones.</p></div><span className="version-tag">SAVED LOCALLY</span></div>
    <div className="population-summary"><div><span>Saved experiments</span><strong>{runs.length}</strong></div><div><span>Fully settled runs</span><strong>{settled.length}</strong></div><div><span>Profitable runs</span><strong>{wins}<small> / {settled.length}</small></strong></div><div><span>Average agent return</span><strong>{settled.length ? pct(settled.reduce((s, r) => s + r.agent.return_pct, 0) / settled.length) : '—'}</strong></div></div>
    {error && <div className="notice negative" role="alert">{error}</div>}
    <section className="panel"><div className="panel-heading"><div><h2>Experiment archive</h2><p>Most recent 30 runs · click a run to inspect its decisions.</p></div></div><div className="table-scroll"><table><thead><tr><th>Experiment</th><th>Market</th><th>Capital</th><th>Agent P&amp;L</th><th>vs buy &amp; hold</th><th>Status</th><th/></tr></thead><tbody>
      {runs.map(r => <tr key={r.id}><td><strong className="mono">Seed {r.settings.seed}</strong><small>{new Date(r.created_at).toLocaleDateString()} · {(r.elapsed ?? r.settings.duration).toLocaleString()} ticks</small></td><td className="capitalize">{r.settings.scenario}</td><td className="mono">{money(r.settings.capital)}</td><td className={`mono ${r.agent.net_pnl >= 0 ? 'up' : 'down'}`}>{signedMoney(r.agent.net_pnl)}<small>{pct(r.agent.return_pct)}</small></td><td className={`mono ${r.excess_pnl >= 0 ? 'up' : 'down'}`}>{signedMoney(r.excess_pnl)}</td><td><span className="pill capitalize">{r.status === 'completed' ? r.verdict : r.status}</span></td><td><button className="text-button" onClick={() => open(r.id)} aria-label={`Inspect seed ${r.settings.seed} run ${r.id}`}>Inspect ↗</button></td></tr>)}
      {!runs.length && <tr><td colSpan={7}><div className="empty-state"><h2>{loading ? 'Loading experiments…' : 'Your first result starts here.'}</h2><p>Finish a run in the live arena. Its capital curve and trade journal will be saved automatically.</p></div></td></tr>}
    </tbody></table></div></section>
  </>;
}
