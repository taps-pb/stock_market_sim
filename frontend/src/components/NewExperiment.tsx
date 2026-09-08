import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useStore } from '../store';
import { startRun } from '../api';
import { terminal } from '../format';

export default function NewExperiment({ open, close, finish }: { open: boolean; close: () => void; finish: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const arena = useStore(s => s.snap?.arena);
  const setSnap = useStore(s => s.setSnap);
  const [capital, setCapital] = useState(100000), [seed, setSeed] = useState(101), [duration, setDuration] = useState(1500);
  const [scenario, setScenario] = useState('balanced'), [risk, setRisk] = useState('balanced');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const profile = risk === 'cautious' ? { max_position: .10, max_exposure: .30, max_drawdown: .04 }
      : risk === 'assertive' ? { max_position: .30, max_exposure: .90, max_drawdown: .12 }
      : { max_position: .20, max_exposure: .60, max_drawdown: .08 };
    try { setSnap(await startRun({ capital, seed, duration, scenario, ...profile })); close(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const running = arena && !terminal(arena.status);
  return <dialog ref={dialog} className="experiment-dialog" onCancel={close} onClick={event => { if (event.target === dialog.current) close(); }}><form onSubmit={submit}>
    <div className="dialog-heading"><div className="eyebrow">A NEW MARKET. A FRESH ACCOUNT.</div><button type="button" className="icon-button" onClick={close} aria-label="Close experiment setup">×</button></div>
    <h1>Fund an experiment.</h1><p>Atlas and buy-and-hold receive the same starting capital. Both trade in the same order book.</p>
    <div className="form-grid"><label>Starting capital · USD<input type="number" min="1000" max="1000000" step="1000" required value={capital} onChange={e => setCapital(Number(e.target.value))}/></label><label>Market seed<input type="number" min="0" max="4294967295" required value={seed} onChange={e => setSeed(Number(e.target.value))}/></label></div>
    <label>Market environment<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="balanced">Balanced · full participant mix</option><option value="volatile">Volatile · more news and liquidity shocks</option><option value="retail">Retail crowd · more FOMO and panic sellers</option></select></label>
    <div className="form-grid"><label>Trading duration<select value={duration} onChange={e => setDuration(Number(e.target.value))}><option value="500">500 ticks · quick experiment</option><option value="1500">1,500 ticks · standard run</option><option value="3000">3,000 ticks · extended run</option></select></label><label>Risk profile<select value={risk} onChange={e => setRisk(e.target.value)}><option value="cautious">Cautious · 30% exposure / 4% stop</option><option value="balanced">Balanced · 60% exposure / 8% stop</option><option value="assertive">Assertive · 90% exposure / 12% stop</option></select></label></div>
    <div className="form-note">60 warmup ticks precede trading. At the end, accounts attempt to close all positions. Unfilled inventory stays visible in the result.</div>
    {running && <div className="notice">The current experiment is still {arena.status}. <button className="text-button" type="button" onClick={finish}>Finish and settle it first ↗</button></div>}
    {error && <div role="alert" className="notice negative">{error}</div>}
    <button className="button primary full-width" type="submit" disabled={busy || !!running || !arena?.model_ready}>{busy ? 'Creating experiment…' : 'Fund accounts & start trading'} <span>↗</span></button>
    <div className="dialog-footer">SIMULATED CAPITAL ONLY · NO BROKER CONNECTION</div>
  </form></dialog>;
}
