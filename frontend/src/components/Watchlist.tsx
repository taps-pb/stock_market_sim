import { useStore } from '../store';
import { pct } from '../format';

export default function Watchlist() {
  const symbols = useStore(s => s.snap?.symbols ?? []);
  const selected = useStore(s => s.selected);
  const select = useStore(s => s.select);
  return <div className="market-strip" aria-label="Select a stock">
    {symbols.map(s => {
      const change = (s.last / s.open - 1) * 100;
      const min = Math.min(...s.history), range = Math.max(...s.history) - min || 1;
      const path = s.history.map((v, i) => `${i ? 'L' : 'M'}${i / Math.max(1, s.history.length - 1) * 72},${26 - (v - min) / range * 22}`).join(' ');
      return <button key={s.symbol} className={`market-chip ${selected === s.symbol ? 'selected' : ''}`} onClick={() => select(s.symbol)} aria-pressed={selected === s.symbol}>
        <div><strong>{s.symbol}</strong><span>{s.sector}</span></div>
        <svg viewBox="0 0 74 30" aria-hidden="true"><path d={path} fill="none" stroke={change >= 0 ? '#2F7A5B' : '#A3464A'} strokeWidth="1.5"/></svg>
        <div><b>{s.last.toFixed(2)}</b><small className={change >= 0 ? 'up' : 'down'}>{pct(change)}</small></div>
      </button>;
    })}
  </div>;
}
