import { useEffect, useRef } from 'react';
import { createChart, ColorType, type UTCTimestamp, type Time } from 'lightweight-charts';
import type { ReplaySnapshot } from '../store';
import { useChartPalette } from '../chartTheme';

const percent = (n: number | null | undefined) => n == null ? '—' : `${(n * 100).toFixed(1)}%`;
const num = (n: number | null | undefined) => n == null ? '—' : n.toFixed(3);
const names = { transfer: 'Atlas · synthetic transfer', historical: 'Atlas · real-data trained', persistence: 'Last-direction baseline', majority: 'Training-majority baseline' };

function ReplayChart({ bars }: { bars: ReplaySnapshot['replay']['bars'] }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<ReturnType<typeof createChart>>();
  const fitted = useRef(false);
  const series = useRef<ReturnType<ReturnType<typeof createChart>['addCandlestickSeries']>>();
  const palette = useChartPalette();
  useEffect(() => {
    if (!box.current) return;
    const c = createChart(box.current, { autoSize: true, layout: { background: { type: ColorType.Solid, color: palette.bg }, textColor: palette.text, attributionLogo: false },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      timeScale: { borderColor: palette.grid, tickMarkFormatter: (t: Time) => `Day ${Number(t)}` },
      rightPriceScale: { borderColor: palette.grid }, localization: { timeFormatter: (t: Time) => `Day ${Number(t)}` } });
    chart.current = c;
    fitted.current = false;
    series.current = c.addCandlestickSeries({ upColor: palette.up, downColor: palette.down, borderVisible: false, wickUpColor: palette.up, wickDownColor: palette.down });
    return () => { series.current = undefined; chart.current = undefined; c.remove(); };
  }, []);
  useEffect(() => {
    chart.current?.applyOptions({
      layout: { background: { type: ColorType.Solid, color: palette.bg }, textColor: palette.text },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      timeScale: { borderColor: palette.grid }, rightPriceScale: { borderColor: palette.grid },
    });
    series.current?.applyOptions({ upColor: palette.up, downColor: palette.down, wickUpColor: palette.up, wickDownColor: palette.down });
  }, [palette]);
  useEffect(() => {
    series.current?.setData(bars.map(b => ({ time: b.day as UTCTimestamp, open: b.open, high: b.high, low: b.low, close: b.close })));
    if (!fitted.current && bars.length) { chart.current?.timeScale().fitContent(); fitted.current = true; }
  }, [bars]);
  return <div className="chartbox" ref={box} aria-label="Revealed daily bars for Asset A"/>;
}

export default function ReplayView({ snapshot }: { snapshot: ReplaySnapshot }) {
  const { arena: a, replay: r } = snapshot;
  return <>
    <div className="page-heading"><div><div className="eyebrow">BLIND HISTORICAL EXPERIMENT</div><h1>{r.reveal ? r.reveal.symbol : r.asset} · historical replay</h1><p>Day {a.elapsed} / {a.settings.duration} · 20-session forecasts · {a.status}</p></div><span className="version-tag">REAL BARS · SIMULATED DECISIONS</span></div>
    {a.error && <div role="alert" className="notice negative">{a.error}</div>}
    <div className="notice">59 context bars precede day 1; each model uses a 60-bar price window. Synthetic transfer uses zero for missing book, flow, spread, and valuation inputs; its 20 simulation ticks are tested as 20 daily sessions. This is an out-of-distribution comparison.</div>
    <section className="panel chart"><h2>{r.asset} · adjusted price units</h2><ReplayChart key={a.id} bars={r.bars}/></section>
    <div className="replay-models">{(['transfer', 'historical'] as const).map(name => {
      const signal = r.latest?.models[name];
      return <section className="panel signal" key={name}><h2>{names[name]}</h2>{signal ? <><div className="forecast-price"><strong>{num(signal.price)}</strong><span>{signal.return_pct.toFixed(2)}%</span></div><p>Target: day {r.latest?.target_day} · higher-close probability {percent(signal.prob)}</p><p>80% interval: {num(signal.lower)} – {num(signal.upper)}</p></> : <p>Waiting for first revealed bar.</p>}</section>;
    })}</div>
    <section className="panel"><div className="panel-heading"><div><h2>Forecast evidence</h2><p>{r.metrics.n} matured, non-overlapping checkpoints · {r.unscored_checkpoints} unresolved. Flat closes count as non-up.</p></div></div>
      <div className="table-scroll"><table><thead><tr><th>Model</th><th>Direction</th><th>Balanced</th><th>Price MAE</th><th>Return MAE · bps</th><th>Interval coverage</th><th>Descriptive result</th></tr></thead><tbody>
        {(Object.keys(names) as (keyof typeof names)[]).map(name => { const m = r.metrics[name]; return <tr key={name}><td>{names[name]}</td><td>{percent(m.accuracy)}</td><td>{percent(m.balanced_accuracy)}</td><td>{num(m.mae)}</td><td>{num(m.return_mae_bps)}</td><td>{percent(m.coverage)}</td><td>{m.verdict ?? 'Baseline'}</td></tr>; })}
      </tbody></table></div><div className="panel-footer">Unchanged-price MAE: {num(r.metrics.historical.baseline_mae)} · return MAE: {num(r.metrics.historical.baseline_return_mae_bps)} bps. Balanced accuracy needs both outcome classes. “Useful signal” means beating these baselines in this sample; it is not a significance test.</div>
    </section>
    <section className="panel"><div className="panel-heading"><div><h2>Illustrative paper trades</h2><p>One share · next open to target close · 1 bp per side · no liquidity or slippage model</p></div></div><div className="table-scroll"><table><thead><tr><th>Model</th><th>Closed trades</th><th>Realized P&amp;L</th><th>Fees paid</th><th>Open inventory</th><th>Marked unrealized P&amp;L</th></tr></thead><tbody>
      {(['transfer', 'historical'] as const).map(name => { const p = r.paper[name]; return <tr key={name}><td>{names[name]}</td><td>{p.trades}</td><td>{num(p.net_pnl)}</td><td>{num(p.fees)}</td><td>{p.position ? `1 share; target day ${p.position.target_day}` : p.pending ? 'Entry pending' : 'None'}</td><td>{num(p.unrealized_pnl)}</td></tr>; })}
    </tbody></table></div><div className="panel-footer">Price and P&amp;L use source price units. End-of-data positions remain marked, not liquidated at invented prices.</div></section>
    <section className="panel"><div className="panel-heading"><h2>Matured forecast journal</h2></div><div className="table-scroll"><table><thead><tr><th>Decision day</th><th>Target day</th><th>Initial</th><th>Actual</th><th>Transfer forecast</th><th>Real-data forecast</th></tr></thead><tbody>
      {r.outcomes.slice().reverse().map(c => <tr key={c.day}><td>{c.day}</td><td>{c.target_day}</td><td>{num(c.initial)}</td><td>{num(c.actual)}</td><td>{num(c.models.transfer.price)}</td><td>{num(c.models.historical.price)}</td></tr>)}
      {!r.outcomes.length && <tr><td colSpan={6}>First checkpoint matures on day 21.</td></tr>}
    </tbody></table></div></section>
    {r.reveal && <section className="panel"><h2>Experiment revealed</h2><p>{r.reveal.symbol} · {r.reveal.start} – {r.reveal.end ?? 'No bars revealed'} · planned end {r.reveal.planned_end}</p><p>Training through {r.reveal.splits.train_end}; calibration {r.reveal.splits.calibration_start} – {r.reveal.splits.calibration_end}; blind test {r.reveal.splits.test_start} – {r.reveal.splits.test_end}.</p></section>}
    <details className="panel"><summary>Reproducibility</summary><p className="replay-fingerprint">Dataset SHA-256: {r.dataset_id}</p>{Object.entries(r.model_fingerprints).map(([name, hash]) => <p className="replay-fingerprint" key={name}>{name}: {hash}</p>)}<p>Seed {a.settings.seed}. Earlier data trains and calibrates a frozen model. Repeated or overlapping historical windows are not independent trials.</p></details>
  </>;
}
