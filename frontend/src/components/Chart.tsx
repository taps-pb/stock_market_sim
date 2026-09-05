import { useEffect, useRef } from "react";
import {
  createChart, ColorType, LineStyle, type IChartApi,
  type ISeriesApi, type UTCTimestamp,
} from "lightweight-charts";
import { useStore } from "../store";
import { getCandles } from "../api";

export default function Chart() {
  const selected = useStore((s) => s.selected);
  const phase = useStore((s) => s.snap?.symbols.find((x) => x.symbol === selected)?.phase);
  const forecast = useStore((s) => s.snap?.model?.signals[selected]);
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candle = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const vol = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!box.current) return;
    const c = createChart(box.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#0e1117" }, textColor: "#c9d1d9" },
      grid: { vertLines: { color: "#1b2029" }, horzLines: { color: "#1b2029" } },
      timeScale: { borderColor: "#30363d" },
      rightPriceScale: { borderColor: "#30363d" },
    });
    candle.current = c.addCandlestickSeries({
      upColor: "#26a67a", downColor: "#e05561", borderVisible: false,
      wickUpColor: "#26a67a", wickDownColor: "#e05561",
    });
    vol.current = c.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
    vol.current.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    chart.current = c;
    return () => {
      candle.current = null;
      vol.current = null;
      chart.current = null;
      c.remove();
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const load = () =>
      getCandles(selected).then((cs) => {
        if (!alive || !candle.current || !vol.current) return;
        candle.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, open: c.o, high: c.h, low: c.l, close: c.c,
        })));
        vol.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, value: c.v, color: c.c >= c.o ? "#26a67a55" : "#e0556155",
        })));
      }).catch(() => {});
    load();
    const id = setInterval(load, 1000); // poll the live candle once a second
    return () => { alive = false; clearInterval(id); };
  }, [selected]);

  useEffect(() => {
    const series = candle.current;
    if (!series || !forecast) return;
    const lines = [
      { price: forecast.price, title: "Forecast median", color: "#9db7ff" },
      { price: forecast.lower, title: "Forecast low", color: "#526995" },
      { price: forecast.upper, title: "Forecast high", color: "#526995" },
    ].map((line) => series.createPriceLine({ ...line, lineWidth: 1, lineStyle: LineStyle.Dashed }));
    return () => {
      if (candle.current === series) lines.forEach((line) => series.removePriceLine(line));
    };
  }, [forecast]);

  return (
    <div className="panel chart">
      <h2>
        {selected}
        {phase && <span className={`phase ${phase}`} title="Simulator insight; hidden from the forecast model">
          smart money: {phase}
        </span>}
      </h2>
      <div ref={box} className="chartbox" />
    </div>
  );
}
