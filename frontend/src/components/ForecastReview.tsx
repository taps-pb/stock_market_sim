import { useStore, type Model, type Sym, type ForecastReviewData } from '../store';
import { money } from '../format';

const price = (n: number | null) => n == null ? '—' : money(n, 2);
const rate = (n: number | null) => n == null ? '—' : `${(n * 100).toFixed(1)}%`;

export default function ForecastReview({ model, symbols }: { model?: Model | null; symbols: Pick<Sym, 'symbol' | 'name'>[] }) {
  const selected = useStore(s => s.selected);
  const select = useStore(s => s.select);
  const review = model?.review;
  if (!review) return null; // Older saved runs lack review data.

  const active = symbols.some(s => s.symbol === selected) ? selected : symbols[0]?.symbol ?? '';
  const calls = review.recent.filter(call => call.symbol === active);
  const stats = review.by_symbol[active];
  return <section className="panel forecast-review" aria-label="Forecast versus reality">
    <div className="forecast-review-heading">
      <div><h2>Forecast versus reality</h2><p>Predictions checked against prices at their target tick · {model.horizon}-tick horizon</p></div>
    </div>
    <div className="forecast-review-stocks" aria-label="Forecast results by stock">
      {symbols.map(s => {
        const row = review.by_symbol[s.symbol];
        return <button type="button" key={s.symbol} className="forecast-review-stock" aria-pressed={active === s.symbol} onClick={() => select(s.symbol)}>
          <span className="forecast-review-stock-name"><strong>{s.symbol}</strong><small>{s.name}</small></span>
          <span className="forecast-review-stock-metrics"><span><small>Price error</small><b>{price(row?.mae ?? null)}</b></span><span><small>Unchanged baseline</small><b>{price(row?.baseline_mae ?? null)}</b></span><span><small>Interval hit</small><b>{rate(row?.coverage ?? null)}</b></span><span><small>Calls</small><b>{row?.n ?? 0}</b></span></span>
        </button>;
      })}
    </div>
    <div className="forecast-review-detail">
      <h3>{active} · recent resolved forecasts</h3>
      {calls.length ? <>
        <ForecastChart calls={calls.slice(0, 12).reverse()} symbol={active}/>
        <div className="forecast-review-legend"><span><i className="predicted"/>Predicted</span><span><i className="actual"/>Actual</span></div>
        <div className="forecast-review-scroll" tabIndex={0} aria-label={`Recent ${active} forecast results`}><table>
          <thead><tr><th>Issued</th><th>Target</th><th>Predicted</th><th>Actual</th><th>Abs. error</th><th>Forecast range</th><th>Interval</th></tr></thead>
          <tbody>{calls.map(c => <tr key={`${c.symbol}-${c.issued_tick}-${c.target_tick}`}>
            <td data-label="Issued">T{c.issued_tick}</td><td data-label="Target">T{c.target_tick}</td>
            <td data-label="Predicted">{price(c.predicted_price)}</td><td data-label="Actual">{price(c.actual_price)}</td>
            <td data-label="Abs. error">{price(c.abs_error)}</td><td data-label="Forecast range">{price(c.lower)} – {price(c.upper)}</td>
            <td data-label="Interval">{c.covered ? 'Hit' : 'Miss'}</td>
          </tr>)}</tbody>
        </table></div>
      </> : <p className="forecast-review-empty">{stats?.n ? 'No calls for this stock in the recent window.' : 'No forecasts matured yet. Results appear at their target tick.'}</p>}
      <p className="forecast-review-footnote">Price error is mean absolute error (MAE). Baseline assumes price stays unchanged. Each tick issues overlapping calls; stock scores include all matured calls. Recent details show the latest 120 calls across stocks.</p>
    </div>
  </section>;
}

function ForecastChart({ calls, symbol }: { calls: ForecastReviewData['recent']; symbol: string }) {
  const values = calls.flatMap(c => [c.predicted_price, c.actual_price]);
  const min = Math.min(...values), max = Math.max(...values);
  const padding = Math.max((max - min) * .1, .01);
  const low = min - padding, high = max + padding;
  const x = (i: number) => 68 + i / Math.max(1, calls.length - 1) * 680;
  const y = (value: number) => 14 + (high - value) / (high - low) * 184;
  const path = (field: 'predicted_price' | 'actual_price') => calls.map((c, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(c[field]).toFixed(1)}`).join(' ');
  return <div className="forecast-review-chart-scroll" role="region" tabIndex={0} aria-label={`${symbol} forecast chart, scroll horizontally for later ticks`}><svg className="forecast-review-chart" viewBox="0 0 780 230" role="img" aria-label={`${symbol}: predicted and actual prices for ${calls.length} matured calls, target ticks ${calls[0].target_tick} to ${calls[calls.length - 1].target_tick}`}>
    {[0, .5, 1].map(f => { const value = high - f * (high - low), pos = y(value); return <g key={f}><line x1="68" x2="748" y1={pos} y2={pos} className="review-gridline"/><text x="60" y={pos + 4} textAnchor="end">{price(value)}</text></g>; })}
    <path d={path('predicted_price')} className="review-predicted"/>
    <path d={path('actual_price')} className="review-actual"/>
    {calls.map((c, i) => <g key={c.target_tick}><circle cx={x(i)} cy={y(c.predicted_price)} r="3" className="review-predicted-dot"/><circle cx={x(i)} cy={y(c.actual_price)} r="3" className="review-actual-dot"/></g>)}
    <text x="68" y="224">T{calls[0].target_tick}</text><text x="748" y="224" textAnchor="end">T{calls[calls.length - 1].target_tick}</text>
  </svg></div>;
}
