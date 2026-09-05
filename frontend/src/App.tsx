import { useEffect } from "react";
import { useStore } from "./store";
import { connectWs } from "./ws";
import { getPortfolio } from "./api";
import Watchlist from "./components/Watchlist";
import Groups from "./components/Groups";
import Chart from "./components/Chart";
import DepthLadder from "./components/DepthLadder";
import Tape from "./components/Tape";
import TradeTicket from "./components/TradeTicket";
import PortfolioView from "./components/PortfolioView";
import Sentiment from "./components/Sentiment";
import Signal from "./components/Signal";

export default function App() {
  const setSnap = useStore((s) => s.setSnap);
  const setPortfolio = useStore((s) => s.setPortfolio);

  useEffect(() => {
    const disconnect = connectWs(setSnap);
    const refresh = () => getPortfolio().then(setPortfolio).catch(() => {});
    refresh();
    const id = setInterval(refresh, 1500);
    return () => { disconnect(); clearInterval(id); };
  }, [setSnap, setPortfolio]);

  return (
    <div className="app">
      <header>
        <h1>Stock Market Simulator</h1>
        <Sentiment />
      </header>
      <div className="grid">
        <aside className="left"><Watchlist /><Groups /></aside>
        <main className="center">
          <Chart />
          <Tape />
        </main>
        <aside className="right">
          <Signal />
          <TradeTicket />
          <DepthLadder />
          <PortfolioView />
        </aside>
      </div>
    </div>
  );
}
