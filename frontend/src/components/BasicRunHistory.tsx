import { useEffect, useState } from 'react';
import { getRuns, getRun } from '../api';
import { isReplay, useStore, type AnySnapshot, type RunItem, type Snapshot, type ReplaySnapshot } from '../store';
import { money, signedMoney } from '../format';

const pageSize = 30; // getRuns requests 30 records at a time.
const statusWords: Record<string, string> = { completed: 'Finished', paused: 'Paused', interrupted: 'Stopped early', failed: 'Failed', running: 'Running', settling: 'Finishing up' };
const statusLabel = (status: string) => statusWords[status] ?? status;

export default function BasicRunHistory() {
  const terminalId = useStore(s => { const a = s.replay?.arena ?? s.snap?.arena; return a && ['completed', 'failed', 'interrupted'].includes(a.status) ? a.id : ''; });
  const [runs, setRuns] = useState<RunItem[]>([]), [selected, setSelected] = useState<AnySnapshot | null>(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0), [total, setTotal] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true); setError('');
    getRuns(offset).then(page => { if (alive) { setRuns(page.items); setTotal(page.total); } })
      .catch(e => { if (alive) setError((e as Error).message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [offset, terminalId]);
  async function open(id: string) {
    setError('');
    try { setSelected(await getRun(id)); }
    catch (e) { setError((e as Error).message); }
  }
  if (selected) return <div className="basic-runs"><button className="text-button" type="button" onClick={() => setSelected(null)}>← Back to all runs</button>{isReplay(selected) ? <ReplayRecap snapshot={selected}/> : <SyntheticRecap snapshot={selected}/>}</div>;
  return <div className="basic-runs">
    <div className="basic-head"><div><div className="eyebrow">Runs</div><h1>Your past runs</h1><p>Look back at saved simulations and historical replays.</p></div></div>
    {error && <div className="notice negative" role="alert">{error}</div>}
    {loading && <div className="empty-inline" role="status">Loading your runs…</div>}
    {!loading && !error && !runs.length && <div className="empty-inline">No saved runs yet. Start an experiment from Home and it will show up here.</div>}
    {!loading && !!runs.length && <><ul className="basic-runs-list">{runs.map(run => <li key={run.id}><button className="basic-run-card" type="button" onClick={() => open(run.id)} aria-label={`Open ${run.kind === 'historical' ? 'historical replay' : 'simulation'} from ${new Date(run.created_at).toLocaleString()}`}>
      <span className="basic-run-top"><strong>{run.kind === 'historical' ? 'Historical replay' : `${run.settings.scenario} market`}</strong><span className="basic-run-status">{statusLabel(run.status)}</span></span>
      <span className="basic-run-when">{new Date(run.created_at).toLocaleString()}</span>
      <span className="basic-run-summary">{run.kind === 'historical' ? `Practice using past prices · day ${run.elapsed} of ${run.settings.duration} · not a real trading result` : run.agent.positions.length ? `Atlas still holds shares. Current value may change.` : <>Net result after fees: <b className={run.agent.net_pnl >= 0 ? 'positive' : 'negative'}>{signedMoney(run.agent.net_pnl)}</b></>}</span>
    </button></li>)}</ul><div className="basic-runs-pager"><button className="button" type="button" onClick={() => setOffset(Math.max(0, offset - pageSize))} disabled={offset === 0}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(total, offset + runs.length)} of {total}</span><button className="button" type="button" onClick={() => setOffset(offset + pageSize)} disabled={offset + pageSize >= total}>Next</button></div></>}
  </div>;
}

function SyntheticRecap({ snapshot }: { snapshot: Snapshot }) {
  const a = snapshot.arena, open = !!a.agent.positions.length;
  const outcome = a.agent.net_pnl > 0 ? 'Atlas made money' : a.agent.net_pnl < 0 ? 'Atlas lost money' : 'Atlas broke even';
  return <><div className="basic-head"><div><div className="eyebrow">Simulation recap</div><h1>{open ? 'Atlas still owns shares' : outcome}</h1><p>{a.settings.scenario} market · {new Date(a.created_at).toLocaleString()}</p></div></div><section className="basic-recap"><h2>What happened</h2><dl><div><dt>Status</dt><dd>{statusLabel(a.status)}</dd></div><div><dt>Starting amount</dt><dd>{money(a.agent.initial)}</dd></div><div><dt>Account value</dt><dd>{money(a.agent.total)}</dd></div>{!open && <div><dt>Net result after fees</dt><dd className={a.agent.net_pnl >= 0 ? 'positive' : 'negative'}>{signedMoney(a.agent.net_pnl)}</dd></div>}</dl><p className="basic-caveat">{open ? 'Shares still held are valued at their latest price, not sold. This result can change.' : a.status === 'completed' ? 'This was a simulated result, not a real trade.' : 'This run stopped early. No real money was involved.'}</p></section></>;
}

function ReplayRecap({ snapshot }: { snapshot: ReplaySnapshot }) {
  const a = snapshot.arena;
  return <><div className="basic-head"><div><div className="eyebrow">Historical replay recap</div><h1>Practice run on past prices</h1><p>{new Date(a.created_at).toLocaleString()}</p></div></div><section className="basic-recap"><h2>Run status</h2><dl><div><dt>Status</dt><dd>{statusLabel(a.status)}</dd></div><div><dt>Replay day</dt><dd>{a.elapsed} of {a.settings.duration}</dd></div></dl><p className="basic-caveat">Past prices were used for practice. No real money was invested.</p></section></>;
}
