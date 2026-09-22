import { useEffect, useState } from 'react';
import { useStore } from './store';
import { connectWs } from './ws';
import { control, getPortfolio } from './api';
import { money, pct, terminal } from './format';
import ArenaView from './components/ArenaView';
import Groups from './components/Groups';
import RunHistory from './components/RunHistory';
import NewExperiment from './components/NewExperiment';
import TradeTicket from './components/TradeTicket';
import PortfolioView from './components/PortfolioView';
import Chart from './components/Chart';
import Watchlist from './components/Watchlist';
import DepthLadder from './components/DepthLadder';
import Tape from './components/Tape';
import ReplayView from './components/ReplayView';

const views = [['arena', 'Live arena', 'arena', 'Live'], ['participants', 'Market participants', 'people', 'People'], ['history', 'Run history', 'history', 'History'], ['desk', 'Manual trading desk', 'chart', 'Trade']] as const;
function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    arena: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    people: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    history: 'M3 11a9 9 0 1 1 2.7 7 M3 3v8h8 M12 7v5l3 2',
    chart: 'M3 3v18h18 M6 14l4-4 4 3 6-7',
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

export default function App() {
  const [view, setView] = useState('arena'), [setup, setSetup] = useState(false);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const { snap, replay, connected, setSnap, setConnected, setPortfolio, select } = useStore();
  const arena = replay?.arena ?? snap?.arena;
  useEffect(() => {
    const disconnect = connectWs(setSnap, setConnected);
    const refresh = () => { if (!useStore.getState().replay) getPortfolio().then(p => { if (!useStore.getState().replay) setPortfolio(p); }).catch(() => {}); };
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => { disconnect(); clearInterval(timer); };
  }, [setSnap, setConnected, setPortfolio]);
  async function act(action: string, speed?: number) {
    setError(''); setBusy(true);
    try { setSnap(await control(action, speed)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const done = arena ? terminal(arena.status) : false;
  const activeView = views.find(v => v[0] === view);
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={e => { e.preventDefault(); setView('arena'); }}><span className="brand-mark"><i/><i/><i/></span><span>market<span className="brand-light">lab</span></span></a>
      <div className="workspace-label"><span className="workspace-icon">M</span><div>Local workspace<small>Simulated</small></div></div>
      <div className="nav-label">Navigation</div>
      <nav>{views.map(([id, label, icon]) => <button key={id} onClick={() => setView(id)} aria-label={label} className={view === id ? 'selected' : ''} aria-current={view === id ? 'page' : undefined}><Icon name={icon}/><span>{label}</span>{id === 'arena' && <i className="nav-live"/>}</button>)}</nav>
      <div className="sidebar-experiment"><div className="eyebrow">Current experiment</div><strong>{replay ? 'Historical replay' : snap ? money(snap.arena.settings.capital) : '—'}</strong><p>{replay ? 'Two frozen models' : 'Atlas + buy-and-hold'}<br/>Seed {arena?.settings.seed ?? '—'} · <span className="capitalize">{replay ? 'Daily OHLCV' : snap?.arena.settings.scenario ?? 'balanced'}</span></p><button className="button primary full-width" onClick={() => setSetup(true)}>New experiment</button></div>
    </aside>
    <div className={`main-shell view-shell-${view}`}>
      <header className="topbar">
        <span className="mobile-brand"><span className="brand-mark"><i/><i/><i/></span>Market Lab</span>
        <div className="breadcrumb">Workspace <span>/</span> <strong>{activeView?.[1]}</strong></div>
        <span className={`mobile-status ${done ? 'finished' : ''}`}><i/>{!connected ? 'OFFLINE' : arena?.status === 'running' ? 'LIVE' : (arena?.status ?? 'LOADING').toUpperCase()}</span>
        <div className="topbar-controls">
          <div className="desktop-controls">
            <span className={`status-label ${done ? 'finished' : ''}`}><i/>{!connected ? 'OFFLINE' : arena?.status === 'running' ? replay ? 'REPLAY RUNNING' : 'MARKET LIVE' : (arena?.status ?? 'LOADING').toUpperCase()}</span>
            <div className="segmented speed-control" aria-label="Simulation speed">{[1, 5, 20].map(speed => <button key={speed} disabled={busy || !connected} onClick={() => act('speed', speed)} className={arena?.speed === speed ? 'active' : ''} aria-pressed={arena?.speed === speed}>{speed}×</button>)}</div>
            <button className="button compact-button" onClick={() => act(arena?.status === 'paused' ? 'resume' : 'pause')} disabled={busy || !connected || done || arena?.status === 'settling'}>{arena?.status === 'paused' ? 'Resume' : 'Pause'}</button>
            <button className="button compact-button finish-button" onClick={() => act('finish')} disabled={busy || !connected || done || arena?.status === 'settling'}>Finish run</button>
            <button className="button compact-button mobile-fund" onClick={() => setSetup(true)}>New experiment</button>
          </div>
          <details className="mobile-run-controls">
            <summary className="mobile-run-summary" aria-label="Run controls"><span aria-hidden="true">•••</span></summary>
            <div className="mobile-run-menu">
              <span className={`status-label ${done ? 'finished' : ''}`}><i/>{!connected ? 'OFFLINE' : arena?.status === 'running' ? replay ? 'REPLAY RUNNING' : 'MARKET LIVE' : (arena?.status ?? 'LOADING').toUpperCase()}</span>
              <div className="segmented speed-control" aria-label="Simulation speed">{[1, 5, 20].map(speed => <button key={speed} disabled={busy || !connected} onClick={() => act('speed', speed)} className={arena?.speed === speed ? 'active' : ''} aria-pressed={arena?.speed === speed}>{speed}×</button>)}</div>
              <button className="button compact-button" onClick={() => act(arena?.status === 'paused' ? 'resume' : 'pause')} disabled={busy || !connected || done || arena?.status === 'settling'}>{arena?.status === 'paused' ? 'Resume' : 'Pause'}</button>
              <button className="button compact-button finish-button" onClick={() => act('finish')} disabled={busy || !connected || done || arena?.status === 'settling'}>Finish run</button>
              <button className="button compact-button" onClick={() => setSetup(true)}>New experiment</button>
            </div>
          </details>
        </div>
      </header>
      <section className="ticker" aria-label="Market prices">
        {(snap?.symbols ?? []).slice(0, 6).map(s => {
          const change = (s.last / s.open - 1) * 100;
          return <button className="ticker-item" key={s.symbol} onClick={() => { select(s.symbol); setView('desk'); }} title={`${s.symbol} · ${s.sector}`}>
            <b>{s.symbol}</b>
            <strong className="mono">{s.last.toFixed(2)}</strong>
            <small>{s.sector}</small>
            <em className={change >= 0 ? 'up' : 'down'}>{pct(change)}</em>
          </button>;
        })}
      </section>
      <main className={`workspace-content view-${view}`}>
        {error && <div className="notice negative" role="alert">{error}<button onClick={() => setError('')} className="icon-button" aria-label="Dismiss error">×</button></div>}
        {view === 'arena' && (replay ? <ReplayView snapshot={replay}/> : <ArenaView onControl={act}/>)}
        {view === 'participants' && (replay ? <div className="notice">Historical replay follows recorded bars. Synthetic participants are available in synthetic experiments.</div> : <Groups/>)}
        {view === 'history' && <RunHistory/>}
        {view === 'desk' && replay && <div className="notice">Historical replay measures forecasts and illustrative paper trades. Manual orders require a synthetic experiment.</div>}
        {view === 'desk' && !replay && <section className="desk-view">
          <div className="page-heading"><div><div className="eyebrow">Manual trading</div><h1>Trade alongside the agent</h1><p>Your orders affect the same market. Your account is separate from Atlas.</p></div><span className="version-tag">Manual orders</span></div>
          <Watchlist/><div className="manual-grid"><Chart/><div className="market-side"><TradeTicket/><DepthLadder/></div></div><div className="lower-grid"><PortfolioView/><Tape/></div>
        </section>}
      </main>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        {views.map(([id, label, icon, shortLabel]) => <button key={id} onClick={() => setView(id)} className={view === id ? 'selected' : ''} aria-current={view === id ? 'page' : undefined} aria-label={label}><Icon name={icon}/><span>{shortLabel}</span></button>)}
      </nav>
      <footer className="workspace-footer"><span><i className="dot teal"/> Market Lab <b>/</b> Simulated trading experiments</span><span>{replay ? 'Historical data · Simulated trades' : 'Simulated market · No real funds'} · <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts powered by TradingView</a></span></footer>
    </div>
    <NewExperiment open={setup} close={() => { setSetup(false); setView('arena'); }} finish={() => act('finish')}/>
  </div>;
}
