import { useStore } from "../store";

export default function Watchlist() {
  const snap = useStore((s) => s.snap);
  const selected = useStore((s) => s.selected);
  const select = useStore((s) => s.select);
  if (!snap) return <div className="panel">connecting…</div>;
  return (
    <div className="panel">
      <h2>Markets</h2>
      <table className="watchlist">
        <tbody>
          {snap.symbols.map((s) => {
            const chg = s.open ? (s.last - s.open) / s.open : 0;
            const dir = snap.model?.signals?.[s.symbol]?.dir;
            return (
              <tr
                key={s.symbol}
                className={s.symbol === selected ? "row sel" : "row"}
                onClick={() => select(s.symbol)}
              >
                <td className="tk">{s.symbol}</td>
                <td className={dir === "up" ? "up sig-a" : dir === "down" ? "down sig-a" : "sig-a"}
                    title="model signal">{dir === "up" ? "▲" : dir === "down" ? "▼" : ""}</td>
                <td className="px">{s.last.toFixed(2)}</td>
                <td className={chg >= 0 ? "up" : "down"}>
                  {chg >= 0 ? "+" : ""}{(chg * 100).toFixed(2)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
