import { useStore } from '../store';
import { money, pct } from '../format';

export default function MarketForecastBoard() {
  const symbols = useStore(s => s.snap?.symbols ?? []);
  const model = useStore(s => s.snap?.model);
  const selected = useStore(s => s.selected);
  const select = useStore(s => s.select);

  return <section className="panel market-forecast-board" aria-label="Market forecasts">
    <div className="forecast-board-heading">
      <div><h2>Market forecast board</h2><p>{model ? `All listed stocks · next ${model.horizon} ticks · ${Math.round(model.interval_coverage * 100)}% forecast interval` : 'All listed stocks · awaiting forecasts'}</p></div>
      <span className="quiet-label">Select stock for chart details</span>
    </div>
    <div className="forecast-board-grid">
      {symbols.map(sym => {
        const signal = model?.signals?.[sym.symbol];
        return <button key={sym.symbol} type="button" className="forecast-card" aria-pressed={selected === sym.symbol} onClick={() => select(sym.symbol)}>
          <span className="forecast-card-head"><strong>{sym.symbol}</strong><span>{sym.name}</span></span>
          <span className="forecast-card-prices"><span><small>Current</small><b>{money(sym.last, 2)}</b></span><span><small>Predicted</small><b>{signal ? money(signal.price, 2) : '—'}</b></span></span>
          {signal ? <>
            <span className={`forecast-card-return ${signal.return_pct >= 0 ? 'up' : 'down'}`}>{pct(signal.return_pct)} <small>expected change</small></span>
            <span className="forecast-card-details">
              <span><small>Chance of higher close</small><b>{Math.round(signal.prob * 100)}%</b></span>
              <span><small>Forecast range</small><b>{money(signal.lower, 2)} – {money(signal.upper, 2)}</b></span>
              <span><small>Target tick</small><b>{signal.target_tick}</b></span>
            </span>
          </> : <span className="forecast-card-empty">{model ? 'Collecting price history…' : 'Forecast unavailable'}</span>}
        </button>;
      })}
      {!symbols.length && <div className="empty-inline">Waiting for listed stocks.</div>}
    </div>
  </section>;
}
