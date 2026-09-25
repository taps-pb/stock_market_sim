import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useStore, type Dataset } from '../store';
import { startRun, startReplay, getDatasets, importDataset } from '../api';
import { money, terminal } from '../format';

const riskChoices = [
  { key: 'cautious', name: 'Cautious', summary: 'Smaller positions. Up to 10% per company and 30% invested; Atlas stops trading after a 4% account drop.' },
  { key: 'balanced', name: 'Balanced', summary: 'A middle setting. Up to 20% per company and 60% invested; Atlas stops trading after an 8% account drop.' },
  { key: 'assertive', name: 'Assertive', summary: 'Atlas can invest more. Up to 30% per company and 90% invested; Atlas stops trading after a 12% account drop.' },
  { key: 'super_risky', name: 'Super risky', summary: 'High risk: Atlas trades more often and has no automatic account loss halt. Losses, slippage, and fees can add up quickly.' },
] as const;

export default function NewExperiment({ open, close, finish, basic = false }: { open: boolean; close: () => void; finish: () => void; basic?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const arena = useStore(s => s.snap?.arena);
  const replay = useStore(s => s.replay);
  const setSnap = useStore(s => s.setSnap);
  const [capital, setCapital] = useState(100000), [seed, setSeed] = useState(101), [duration, setDuration] = useState(1500);
  const [basicCapital, setBasicCapital] = useState('100000');
  const [scenario, setScenario] = useState('balanced'), [risk, setRisk] = useState('balanced');
  const [basicScenario, setBasicScenario] = useState('balanced');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [mode, setMode] = useState('synthetic'), [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState(''), [sessions, setSessions] = useState(100);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  useEffect(() => { if (open && !basic) getDatasets().then(setDatasets).catch(e => setError(e.message)); }, [open, basic]);
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true); setError('');
    try { const data = await importDataset(file); setDataset(data.id); setDatasets(await getDatasets()); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (basic && !basicCapitalValid) return;
    setBusy(true); setError('');
    const profile = risk === 'cautious' ? { max_position: .10, max_exposure: .30, max_drawdown: .04 }
      : risk === 'assertive' ? { max_position: .30, max_exposure: .90, max_drawdown: .12 }
      : risk === 'super_risky' ? { max_position: .30, max_exposure: .90, max_drawdown: .30,
          stop_loss: .15, min_probability: .50, min_edge_bps: 0, slippage_bps: 100, participation: .50 }
      : { max_position: .20, max_exposure: .60, max_drawdown: .08 };
    try { setSnap(basic ? await startRun({ capital: Number(basicCapital), seed: Date.now() >>> 0, duration: 1500, scenario: basicScenario, risk_profile: risk, ...profile })
      : mode === 'historical' ? await startReplay({ dataset_id: dataset, seed, duration: sessions })
      : await startRun({ capital, seed, duration, scenario, risk_profile: risk, ...profile })); close(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const current = replay?.arena ?? arena;
  const running = current && !terminal(current.status);
  const amount = Number(basicCapital);
  const basicCapitalValid = basicCapital !== '' && Number.isFinite(amount) && amount >= 1000 && amount <= 1000000 && amount % 1000 === 0;
  const riskIndex = Math.max(0, riskChoices.findIndex(choice => choice.key === risk));
  const selectedRisk = riskChoices[riskIndex];
  return <dialog ref={dialog} className={`experiment-dialog ${basic ? 'basic-dialog' : ''}`} onCancel={close} onClick={event => { if (event.target === dialog.current) close(); }}><form onSubmit={submit}>
    <div className="dialog-heading"><div className="eyebrow">New experiment</div><button type="button" className="icon-button" onClick={close} aria-label="Close experiment setup">×</button></div>
    <h1>{basic ? 'Start a new simulation' : 'Start an experiment'}</h1>
    {basic ? <><p className="experiment-intro">Atlas and a simple comparison each start with <strong className="basic-intro-amount">{basicCapitalValid ? money(amount) : 'your chosen amount'}</strong> in simulated money. This is not real trading.</p>
      <div className="basic-capital-field"><label htmlFor="basic-capital">Starting money · USD</label><div className="basic-money-field"><span aria-hidden="true">$</span><input id="basic-capital" type="number" inputMode="numeric" min="1000" max="1000000" step="1000" required value={basicCapital} aria-invalid={!basicCapitalValid} aria-describedby="basic-capital-hint" disabled={busy} onChange={e => setBasicCapital(e.target.value)}/></div><p className="hint" id="basic-capital-hint">{basicCapitalValid ? 'Choose $1,000 to $1,000,000 in steps of $1,000.' : 'Enter $1,000–$1,000,000 in steps of $1,000.'}</p></div>
      <label>Market style<select value={basicScenario} onChange={e => setBasicScenario(e.target.value)} disabled={busy}><option value="balanced">Balanced · a little of everything</option><option value="volatile">Volatile · bigger price moves</option><option value="retail">Retail crowd · more individual traders</option></select></label>
      <div className="basic-risk"><div className="basic-risk-heading"><label htmlFor="basic-risk">Risk level</label><output className="basic-risk-name" htmlFor="basic-risk">{selectedRisk.name}</output></div>
        <input className="basic-risk-range" id="basic-risk" type="range" min="0" max="3" step="1" value={riskIndex} aria-valuetext={selectedRisk.name} aria-describedby="basic-risk-explain" disabled={busy} onChange={e => setRisk(riskChoices[Number(e.target.value)].key)}/>
        <div className="basic-risk-stops" role="group" aria-label="Choose risk level">{riskChoices.map((choice, index) => <button key={choice.key} type="button" aria-pressed={index === riskIndex} disabled={busy} onClick={() => setRisk(choice.key)}>{choice.name}</button>)}</div>
        <p id="basic-risk-explain" className={`basic-risk-explain${risk === 'super_risky' ? ' high' : ''}`} aria-live="polite">{selectedRisk.summary}</p>
      </div>
      <p className="form-note">Standard run length. Switch to Pro to adjust duration and seed.</p>
    </> : <>
    <label>Experiment type<select value={mode} onChange={e => setMode(e.target.value)} disabled={busy}><option value="synthetic">Synthetic exchange</option><option value="historical">Blind historical replay</option></select></label>
    {mode === 'historical' ? <>
      <p className="experiment-intro">Compare a synthetic-trained Atlas against a real-data model on hidden historical bars.</p>
      <label>Import adjusted daily OHLCV<input type="file" accept=".csv,text/csv" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }}/></label>
      <div className="form-note">CSV columns: date,symbol,open,high,low,close,volume. Dates: YYYY-MM-DD, ordered within each symbol. Positive OHLC prices, nonnegative volume. Use consistently split/dividend-adjusted prices. Maximum 10 MiB / 100,000 rows. Roughly 800+ sessions per symbol.</div>
      <label>Local dataset<select required value={dataset} onChange={e => setDataset(e.target.value)} disabled={busy}><option value="">Select imported dataset</option>{datasets.map(d => <option key={d.id} value={d.id}>{d.name} · {d.rows.toLocaleString()} rows · {d.start} – {d.end}</option>)}</select></label>
      <div className="form-grid"><label>Replay seed<input type="number" required min="0" max="4294967295" step="1" value={seed} onChange={e => setSeed(Number(e.target.value))}/></label><label>Replay sessions<input type="number" required min="100" max={Math.min(10000, datasets.find(d => d.id === dataset)?.max_duration ?? 10000)} step="1" value={sessions} onChange={e => setSessions(Number(e.target.value))}/></label></div>
      <div className="form-note">70% train / 15% calibrate / 15% blind test, with purged targets and 20-session embargoes. Starting replay fits a frozen real-data model locally. Ticker and dates reveal when the run ends.</div>
    </> : <>
    <p className="experiment-intro">Atlas and buy-and-hold receive the same starting capital. Both trade in the same order book.</p>
    <div className="form-grid">
      <label>Starting capital · USD
        <div className="number-control">
          <button type="button" className="step" aria-label="Decrease starting capital" onClick={() => setCapital(value => Math.max(1000, value - 1000))}>−</button>
          <input type="number" min="1000" max="1000000" step="1000" required value={capital} aria-describedby="capital-hint" onChange={e => setCapital(Number(e.target.value))}/>
          <button type="button" className="step" aria-label="Increase starting capital" onClick={() => setCapital(value => Math.min(1000000, value + 1000))}>+</button>
        </div>
        <span className="hint" id="capital-hint">Between $1,000 and $1,000,000</span>
      </label>
      <label>Market seed
        <div className="number-control">
          <button type="button" className="step" aria-label="Decrease market seed" onClick={() => setSeed(value => Math.max(0, value - 1))}>−</button>
          <input type="number" min="0" max="4294967295" required value={seed} aria-describedby="seed-hint" onChange={e => setSeed(Number(e.target.value))}/>
          <button type="button" className="step" aria-label="Increase market seed" onClick={() => setSeed(value => Math.min(4294967295, value + 1))}>+</button>
        </div>
        <span className="hint" id="seed-hint">Reuse a seed to replay market conditions</span>
      </label>
    </div>
    <label>Market environment<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="balanced">Balanced · full participant mix</option><option value="volatile">Volatile · more news and liquidity shocks</option><option value="retail">Retail crowd · more FOMO and panic sellers</option></select></label>
    <div className="form-grid"><label>Trading duration<select value={duration} onChange={e => setDuration(Number(e.target.value))}><option value="500">500 ticks · quick experiment</option><option value="1500">1,500 ticks · standard run</option><option value="3000">3,000 ticks · extended run</option></select></label><label>Risk profile<select value={risk} onChange={e => setRisk(e.target.value)}><option value="cautious">Cautious</option><option value="balanced">Balanced</option><option value="assertive">Assertive</option><option value="super_risky">Super risky</option></select></label></div>
    {risk === 'super_risky' && <div className="notice negative">High-risk profile: Atlas acts on every tick, enters on any bullish forecast regardless of edge, accumulates to its position cap, and exits on a bearish flip or after three ticks. Assumes 1% entry slippage, takes 50% of visible depth, and risks 30% per stock / 90% total. No automatic account loss halt — it will keep trading through losses until stopped or until it cannot fund a trade. Churn and fees can erode capital.</div>}
    <div className="form-note experiment-note">60 warmup ticks precede trading. At the end, accounts attempt to close all positions. Unfilled inventory stays visible in the result.</div>
    </>}
    </>}
    {running && <div className="notice">The current experiment is still {current.status}. <button className="text-button" type="button" onClick={finish}>Finish it first</button></div>}
    {error && <div role="alert" className="notice negative">{error}</div>}
    <button className="button primary full-width" type="submit" disabled={busy || !!running || (basic && !basicCapitalValid) || (!basic && mode === 'historical' && !dataset)}>{busy ? 'Preparing experiment…' : basic ? 'Start simulation' : mode === 'historical' ? 'Train models & start replay' : 'Start experiment'}</button>
    <div className="dialog-footer">Simulated capital only · No broker connection</div>
  </form></dialog>;
}
