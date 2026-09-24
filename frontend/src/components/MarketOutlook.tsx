import { useStore, type Model, type OutlookCheckpoint, type Sym } from '../store';
import { money, pct } from '../format';

const points = (n: number) => n.toFixed(2);

export default function MarketOutlook({ model, symbols }: { model?: Model | null; symbols: Pick<Sym, 'symbol' | 'name' | 'last'>[] }) {
  const selected = useStore(s => s.selected);
  const select = useStore(s => s.select);
  const outlook = model?.outlook;
  if (!outlook) return null; // Older archives and historical replay have no synthetic outlook.
  const current = symbols.find(s => s.symbol === selected) ?? symbols[0];
  const checkpoints = outlook.series;
  return <section className="panel market-outlook" aria-label="Longer-horizon market outlook">
    <div className="outlook-heading"><div><h2>Market outlook</h2><p>Independently trained 20-, 60- and 120-tick forecasts · ticks are simulation steps, not market hours.</p></div><span>Six-stock normalized index · not tradable</span></div>
    <div className="outlook-index"><span>Index now <strong>{points(outlook.index_now)}</strong></span><small>Base 100 at starting prices · equal weight</small></div>
    {checkpoints.length ? <>
      <div className="outlook-checkpoints" aria-label="Evaluated index checkpoints">
        {checkpoints.map(c => <article className="outlook-card" key={c.horizon}>
          <div className="outlook-card-head"><strong>{c.horizon} ticks</strong><span>Target T{c.target_tick}</span></div>
          <div className="outlook-card-value">{points(c.index_price)} <small>index points</small></div>
          <div className={c.index_return_pct >= 0 ? 'up' : 'down'}>{pct(c.index_return_pct)} from now</div>
          <div className="outlook-card-meta"><span>Forecast interval <b>{points(c.index_lower)} – {points(c.index_upper)}</b></span><span>Unseen-market error <b>{points(c.evaluation.mae)} pts</b></span><span>Unchanged baseline <b>{points(c.evaluation.baseline_mae)} pts</b></span><span>Interval coverage <b>{(c.evaluation.coverage * 100).toFixed(1)}%</b></span></div>
        </article>)}
      </div>
      <div className="outlook-trajectory-grid">
        <div className="outlook-trajectory"><h3>Index checkpoints</h3><Trajectory title="Index" now={outlook.index_now} series={checkpoints.map(c => ({ horizon: c.horizon, tick: c.target_tick, value: c.index_price, lower: c.index_lower, upper: c.index_upper }))} unit="points"/></div>
        <div className="outlook-trajectory"><div className="outlook-stock-heading"><h3>Stock checkpoints</h3><select aria-label="Stock to inspect" value={current?.symbol ?? ''} onChange={e => select(e.target.value)}>{symbols.map(s => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}</select></div>
          {current && <><p>Current {current.symbol} price: <strong>{money(current.last, 2)}</strong></p><Trajectory title={current.symbol} now={current.last} unit="USD" series={checkpoints.filter(c => c.stocks[current.symbol]).map(c => ({ horizon: c.horizon, tick: c.target_tick, value: c.stocks[current.symbol].price, lower: c.stocks[current.symbol].lower, upper: c.stocks[current.symbol].upper }))}/>
            <div className="outlook-stock-checkpoints">{checkpoints.map((c: OutlookCheckpoint) => { const stock = c.stocks[current.symbol]; return stock && <div key={c.horizon}><b>{c.horizon} ticks · T{c.target_tick}</b><span>{money(stock.price, 2)} <span className={stock.return_pct >= 0 ? 'up' : 'down'}>{pct(stock.return_pct)}</span></span><small>Range {money(stock.lower, 2)} – {money(stock.upper, 2)}</small></div>; })}</div>
          </>}
        </div>
      </div>
      <p className="outlook-note">Markers are separate target-tick estimates; dashed lines only guide the eye. Intermediate prices are not predicted. Index intervals are calibrated separately on held-out simulation markets.</p>
    </> : <p className="outlook-empty" role="status">Collecting price history. Checkpoints appear after 60 observed ticks.</p>}
  </section>;
}

type Point = { horizon: number; tick: number; value: number; lower: number; upper: number };
function Trajectory({ title, now, series, unit }: { title: string; now: number; series: Point[]; unit: string }) {
  if (!series.length) return <p className="outlook-empty">No forecasts available yet.</p>;
  const values = [now, ...series.flatMap(p => [p.lower, p.upper])];
  const min = Math.min(...values), max = Math.max(...values), pad = Math.max((max - min) * .12, .01);
  const low = min - pad, high = max + pad;
  const x = (h: number) => 62 + h / 120 * 490;
  const y = (n: number) => 16 + (high - n) / (high - low) * 160;
  const path = [{ horizon: 0, value: now }, ...series].map((p, i) => `${i ? 'L' : 'M'}${x(p.horizon).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
  return <div className="outlook-chart-scroll" role="region" tabIndex={0} aria-label={`${title} chart, scroll horizontally for later ticks`}><svg className="outlook-chart" viewBox="0 0 600 220" role="img" aria-label={`${title} now ${points(now)} ${unit}; ${series.map(p => `${p.horizon} ticks: ${points(p.value)} ${unit}`).join('; ')}`}>
    {[0, .5, 1].map(f => { const v = high - f * (high - low), yy = y(v); return <g key={f}><line x1="62" x2="552" y1={yy} y2={yy} className="outlook-gridline"/><text x="54" y={yy + 4} textAnchor="end">{points(v)}</text></g>; })}
    <path d={path} className="outlook-guide"/>
    <circle cx={x(0)} cy={y(now)} r="4" className="outlook-dot"/>
    <text x={x(0)} y="210" textAnchor="middle">Now</text>
    {series.map(p => <g key={p.horizon}><line x1={x(p.horizon)} x2={x(p.horizon)} y1={y(p.lower)} y2={y(p.upper)} className="outlook-range"/><circle cx={x(p.horizon)} cy={y(p.value)} r="4" className="outlook-dot"/><text x={x(p.horizon)} y="210" textAnchor="middle">T{p.tick}</text></g>)}
  </svg></div>;
}
