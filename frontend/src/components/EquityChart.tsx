import { useState } from 'react';
import type { CurvePoint } from '../store';
import { money, pct } from '../format';

export default function EquityChart({ points }: { points: CurvePoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [returns, setReturns] = useState(false);
  if (!points.length) return null;
  const initial = points[0].cash;
  const value = (n: number) => returns ? (n / initial - 1) * 100 : n;
  const values = points.flatMap(p => [value(p.agent), value(p.hold), value(p.cash)]);
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * .18, returns ? .05 : initial * .0005);
  const low = min - pad, high = max + pad;
  const end = Math.max(1, points[points.length - 1].tick);
  const x = (tick: number) => 70 + tick / end * 805;
  const y = (v: number) => 20 + (high - value(v)) / (high - low) * 200;
  const path = (key: 'agent' | 'hold' | 'cash') => points.map((p, i) => `${i ? 'L' : 'M'}${x(p.tick).toFixed(2)},${y(p[key]).toFixed(2)}`).join(' ');
  const active = points[hover ?? points.length - 1];
  return <div className="equity-chart">
    <div className="panel-heading">
      <div><h2>Capital performance</h2><p>Equity, buy-and-hold benchmark, and cash over time.</p></div>
      <div className="segmented"><button className={!returns ? 'active' : ''} onClick={() => setReturns(false)}>Equity</button><button className={returns ? 'active' : ''} onClick={() => setReturns(true)}>Return %</button></div>
    </div>
    <div className="chart-legend">
      <span><i className="dot teal" />Atlas <b>{returns ? pct(value(active.agent)) : money(active.agent, 2)}</b></span>
      <span><i className="dot amber" />Buy &amp; hold <b>{returns ? pct(value(active.hold)) : money(active.hold, 2)}</b></span>
      <span><i className="dot gray" />Cash</span>
      {hover != null && <em>Tick {active.tick}</em>}
    </div>
    <svg viewBox="0 0 900 255" role="img" aria-label="Agent equity compared with buy-and-hold and cash" onPointerLeave={() => setHover(null)} onPointerMove={event => {
      const rect = event.currentTarget.getBoundingClientRect();
      const tick = Math.max(0, Math.min(1, ((event.clientX - rect.left) / rect.width * 900 - 70) / 805)) * end;
      let nearest = 0;
      points.forEach((p, i) => { if (Math.abs(p.tick - tick) < Math.abs(points[nearest].tick - tick)) nearest = i; });
      setHover(nearest);
    }}>
      <defs><linearGradient id="equity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#557A95" stopOpacity=".18"/><stop offset="100%" stopColor="#557A95" stopOpacity="0"/></linearGradient></defs>
      {[0, 1, 2, 3, 4].map(i => {
        const v = high - i / 4 * (high - low), cy = 20 + i * 50;
        return <g key={i}><line x1="70" x2="875" y1={cy} y2={cy} className="gridline"/><text x="57" y={cy + 4} textAnchor="end">{returns ? `${v.toFixed(2)}%` : money(v)}</text></g>;
      })}
      <path d={`${path('agent')} L${x(end)},220 L70,220 Z`} fill="url(#equity-fill)"/>
      <path d={path('cash')} className="cash-line"/>
      <path d={path('hold')} className="hold-line"/>
      <path d={path('agent')} className="agent-line"/>
      {[0, 1, 2, 3, 4].map(i => <text key={i} x={70 + i / 4 * 805} y="246" textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>T{Math.round(end * i / 4)}</text>)}
      {hover != null && <g><line x1={x(active.tick)} x2={x(active.tick)} y1="20" y2="220" className="cursor-line"/><circle cx={x(active.tick)} cy={y(active.agent)} r="4" fill="#557A95" stroke="#F3F7F9" strokeWidth="2"/></g>}
    </svg>
    <div className="chart-footnote"><span>Marked to market · Fees included</span><span>Simulation ticks</span></div>
  </div>;
}
