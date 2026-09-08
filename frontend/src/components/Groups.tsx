import { useStore } from '../store';
import { compact, money, pct } from '../format';

const descriptions: Record<string, [string, string]> = {
  institution: ['Institutions', 'Build positions patiently, then distribute into strength.'],
  whale: ['Whales', 'Large value buyers with conviction and deep reserves.'],
  pension: ['Pension funds', 'Slow accumulation. Long horizons. Low turnover.'],
  market_maker: ['Market makers', 'Quote both sides; widen spreads when risk rises.'],
  value: ['Value investors', 'Buy perceived discounts and wait for convergence.'],
  momentum: ['Momentum funds', 'Follow sustained trends and crowd direction.'],
  contrarian: ['Contrarians', 'Lean against the crowd when prices stretch.'],
  swing: ['Swing traders', 'Trade medium-term moves around perceived value.'],
  scalper: ['Scalpers', 'Short horizons and frequent, small orders.'],
  fomo: ['FOMO retail', 'Chase rallies. Grow confident after prices rise.'],
  weak_hands: ['Nervous retail', 'Small drawdowns trigger fear and rapid exits.'],
  retail: ['Everyday retail', 'A mix of trend following, emotion and limited capital.'],
  bagholder: ['Reluctant sellers', 'Hold losing positions and resist realizing losses.'],
  noise: ['Noise traders', 'Small, unpredictable trades add background activity.'],
};

export default function Groups() {
  const arena = useStore(s => s.snap?.arena);
  if (!arena) return null;
  const groups = arena.population;
  const total = groups.reduce((s, g) => s + g.count, 0);
  const capital = groups.reduce((s, g) => s + g.capital, 0);
  const retail = groups.filter(g => ['fomo', 'weak_hands', 'retail', 'bagholder', 'noise'].includes(g.name));
  const retailCount = retail.reduce((s, g) => s + g.count, 0);
  const fear = retail.reduce((s, g) => s + g.fear * g.count, 0) / Math.max(1, retailCount);
  return <>
    <div className="page-heading"><div><div className="eyebrow">THE OTHER SIDE OF EVERY TRADE</div><h1>A market made of different minds.</h1><p>Every participant has its own capital, conviction, horizon and emotional state.</p></div><span className="version-tag">OBSERVER VIEW</span></div>
    <div className="population-summary"><div><span>Independent traders</span><strong>{total}</strong></div><div><span>Starting participant capital</span><strong>{money(capital)}</strong></div><div><span>Retail crowd</span><strong>{retailCount}<small> traders</small></strong></div><div><span>Retail fear</span><strong>{(fear * 100).toFixed(0)}<small> / 100</small></strong></div></div>
    <div className="notice">This is an observer's view into the simulation. Atlas cannot see individual emotions, institutional phases or hidden intrinsic values.</div>
    <section className="panel population-panel"><div className="panel-heading"><div><h2>The participant landscape</h2><p>Capital is concentrated. Reactions are not.</p></div><span className="quiet-label">14 BEHAVIOR TYPES</span></div>
      <div className="table-scroll"><table><thead><tr><th>Participant</th><th>Traders</th><th>Starting capital</th><th>Buy / sell flow</th><th>Fear</th><th className="align-right">Group return</th></tr></thead><tbody>{groups.map((g, i) => {
        const [name, description] = descriptions[g.name] ?? [g.name, ''];
        const share = g.buy_volume / (g.buy_volume + g.sell_volume || 1) * 100;
        return <tr key={g.name}><td><div className="participant-name"><span className={`participant-avatar tier-${i < 4 ? 'large' : 'small'}`}>{name.charAt(0)}</span><div><strong>{name}</strong><small>{description}</small></div></div></td><td className="mono">{g.count}</td><td className="mono">${compact(g.capital)}<small>{(g.capital / capital * 100).toFixed(1)}% of market capital</small></td><td><div className="flow-bar"><i style={{ width: `${share}%` }}/></div><small className="mono">${compact(g.buy_volume)} / ${compact(g.sell_volume)}</small></td><td><div className="fear-gauge"><i style={{ width: `${g.fear * 100}%` }}/></div><small>{(g.fear * 100).toFixed(0)} / 100</small></td><td className={`align-right mono ${g.return_pct >= 0 ? 'up' : 'down'}`}>{pct(g.return_pct)}</td></tr>;
      })}</tbody></table></div>
    </section>
  </>;
}
