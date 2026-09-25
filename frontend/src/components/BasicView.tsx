import { money, signedMoney, pct, terminal } from '../format';
import type { ReplaySnapshot, Snapshot } from '../store';

type Props = {
  snap?: Snapshot;
  replay?: ReplaySnapshot;
  connected: boolean;
  busy: boolean;
  onControl: (action: string) => void;
  onNewExperiment: () => void;
};

const statusWords: Record<string, string> = { running: 'Running', paused: 'Paused', settling: 'Closing positions', completed: 'Completed', failed: 'Failed', interrupted: 'Interrupted' };
const statusWord = (status: string) => statusWords[status] ?? status;

function Actions({ paused, disabled, newDisabled, onControl, onNewExperiment }: { paused: boolean; disabled: boolean; newDisabled: boolean; onControl: Props['onControl']; onNewExperiment: Props['onNewExperiment'] }) {
  return <div className="basic-actions">
    <button className="button" type="button" disabled={disabled} onClick={() => onControl(paused ? 'resume' : 'pause')}>{paused ? 'Resume simulation' : 'Pause simulation'}</button>
    <button className="button primary" type="button" disabled={newDisabled} onClick={onNewExperiment}>Start a new experiment</button>
  </div>;
}

function Synthetic({ snap, connected, busy, onControl, onNewExperiment }: Props & { snap: Snapshot }) {
  const arena = snap.arena, a = arena.agent;
  const done = terminal(arena.status), settling = arena.status === 'settling', paused = arena.status === 'paused';
  const warmingUp = !done && snap.tick < arena.warmup;
  const signals = !warmingUp && !done && !paused && snap.model?.signals
    ? snap.symbols.flatMap(s => snap.model?.signals[s.symbol] ? [{ name: s.name, signal: snap.model.signals[s.symbol] }] : []).slice(0, 2)
    : [];
  const headline = done ? 'This experiment has ended.' : paused ? 'The simulation is paused.' : settling ? 'The experiment is finishing.' : warmingUp ? 'Atlas is getting ready.' : 'Here’s how Atlas is doing.';
  const update = done ? 'This run has ended. You can review it in Runs.' : paused ? 'Trading is on hold until you resume.' : settling ? 'The experiment is closing positions.' : arena.agent_halted ? 'Atlas has stopped trading.' : warmingUp ? 'Atlas is collecting market history before it can trade.' : 'Atlas checks prices and waits for an opportunity that meets its rules.';
  return <div className="basic-view">
    <div className="basic-head"><div><span className="eyebrow">{connected ? 'Live · your simulation' : 'Offline · last update'}</span><h1>{headline}</h1><p>A simple view of the market and your simulated account.</p></div><span className="basic-label">{!connected ? 'Offline' : paused ? 'Paused' : warmingUp ? 'Getting ready' : arena.agent_halted ? 'Atlas stopped' : statusWord(arena.status)}</span></div>
    {!connected && <div className="notice" role="status">Showing the last update. Simulation controls will work when the server reconnects.</div>}
    {arena.error && <div className="notice negative" role="alert">{arena.error}</div>}
    <div className="basic-overview">
      <section className={`basic-result ${a.net_pnl < 0 ? 'negative' : ''}`}><span className="eyebrow">Atlas result so far</span><strong>{signedMoney(a.net_pnl)}</strong><p>{pct(a.return_pct)} from the {money(a.initial)} starting amount.{a.positions.length ? ' Includes shares still held, valued at their latest price.' : ''}</p></section>
      <section className="basic-balance"><span className="eyebrow">Account value now</span><strong>{money(a.total)}</strong><p>Includes cash and shares Atlas owns.</p></section>
    </div>
    <div className="basic-grid">
      <section aria-labelledby="basic-stocks-heading"><div className="basic-section-head"><h2 id="basic-stocks-heading">The six companies</h2><p>Prices in this simulated market right now.</p></div><div className="basic-stock-list">
        {snap.symbols.slice(0, 6).map(s => { const change = s.open ? (s.last / s.open - 1) * 100 : 0; return <div className="basic-stock-row" key={s.symbol}><div><strong>{s.name}</strong><small>{s.symbol}</small></div><b>{money(s.last, 2)}</b><em className={change >= 0 ? 'positive' : 'negative'}>{pct(change)}</em></div>; })}
        {!snap.symbols.length && <div className="empty-inline">Waiting for the listed companies.</div>}
      </div></section>
      <section aria-labelledby="basic-now-heading"><div className="basic-section-head"><h2 id="basic-now-heading">What’s happening</h2><p>Plain-language update from the experiment.</p></div><div className="basic-update"><h3>{update}</h3>
        {signals.map(({ name, signal }) => <p className="basic-call" key={name}><strong>{name}</strong> <span className={signal.dir === 'up' ? 'positive' : 'negative'}>{signal.dir === 'up' ? 'may rise' : 'may fall'}</span> over the next {snap.model?.horizon} simulation steps.</p>)}
        <p className="basic-caveat">These are guesses in a made-up market, not advice or promises.</p>
      </div></section>
    </div>
    <Actions paused={paused} disabled={busy || !connected || done || settling} newDisabled={busy || !connected || settling} onControl={onControl} onNewExperiment={onNewExperiment}/>
    <p className="basic-note">Simulated market and money only. Want charts, detailed forecasts, and the decision journal? Switch to Pro mode.</p>
  </div>;
}

function Replay({ replay, connected, busy, onControl, onNewExperiment }: Props & { replay: ReplaySnapshot }) {
  const a = replay.arena, r = replay.replay;
  const done = terminal(a.status), settling = a.status === 'settling', paused = a.status === 'paused';
  return <div className="basic-view">
    <div className="basic-head"><div><span className="eyebrow">Historical replay · simulated decisions</span><h1>{done ? 'This replay has ended.' : paused ? 'The replay is paused.' : 'A historical replay is running.'}</h1><p>Models make guesses about hidden past prices. This does not show a real trading result.</p></div><span className="basic-label">{connected ? statusWord(a.status) : 'Offline'}</span></div>
    {!connected && <div className="notice" role="status">Showing the last update. Simulation controls will work when the server reconnects.</div>}
    {a.error && <div className="notice negative" role="alert">{a.error}</div>}
    <div className="basic-overview"><section className="basic-result"><span className="eyebrow">Replay progress</span><strong>Day {a.elapsed}</strong><p>of {a.settings.duration} days of historical prices.</p></section><section className="basic-balance"><span className="eyebrow">Forecasts checked</span><strong>{r.metrics.n}</strong><p>Completed guesses measured against what happened.</p></section></div>
    <section className="basic-update"><h2>What’s happening</h2><p>{done ? 'The replay has stopped. See Runs for the recap.' : paused ? 'This replay is on hold until you resume.' : 'Each model makes a guess before the next real price is revealed.'}</p><p className="basic-caveat">Past prices are used for practice. No real orders or funds are involved.</p></section>
    <Actions paused={paused} disabled={busy || !connected || done || settling} newDisabled={busy || !connected || settling} onControl={onControl} onNewExperiment={onNewExperiment}/>
    <p className="basic-note">For detailed model results, switch to Pro mode.</p>
  </div>;
}

export default function BasicView({ snap, replay, connected, ...rest }: Props) {
  if (replay) return <Replay {...rest} replay={replay} connected={connected}/>;
  if (snap) return <Synthetic {...rest} snap={snap} connected={connected}/>;
  return <div className="basic-view"><div className="empty-state"><div className="loading-orbit"/><h2>{connected ? 'Getting the simulation ready' : 'The simulation is offline'}</h2><p>{connected ? 'Waiting for the first update.' : 'The app will reconnect to the local simulation server automatically.'}</p></div></div>;
}
