import { useEffect, useRef } from "react";
import {
  createChart, ColorType, LineStyle, type IChartApi,
  type ISeriesApi, type UTCTimestamp, type Time,
} from "lightweight-charts";
import { useStore } from "../store";
import { getCandles } from "../api";

export default function Chart() {
  const selected = useStore((s) => s.selected);
  const runId = useStore((s) => s.snap?.arena.id);
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
      layout: { background: { type: ColorType.Solid, color: "#F3F7F9" }, textColor: "#26343D", fontSize: 10, attributionLogo: false },
      grid: { vertLines: { color: "#D8E3E8" }, horzLines: { color: "#D8E3E8" } },
      timeScale: { borderColor: "#C9D8E0", tickMarkFormatter: (time: Time) => `T${Number(time) * 20}` },
      localization: { timeFormatter: (time: Time) => `Tick ${Number(time) * 20}` },
      rightPriceScale: { borderColor: "#C9D8E0" },
    });
    candle.current = c.addCandlestickSeries({
      upColor: "#2F7A5B", downColor: "#A3464A", borderVisible: false,
      wickUpColor: "#2F7A5B", wickDownColor: "#A3464A",
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
    let first = true;
    candle.current?.setData([]);
    vol.current?.setData([]);
    const load = () =>
      getCandles(selected).then((cs) => {
        if (!alive || !candle.current || !vol.current) return;
        candle.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, open: c.o, high: c.h, low: c.l, close: c.c,
        })));
        vol.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, value: c.v, color: c.c >= c.o ? "#2F7A5B55" : "#A3464A55",
        })));
        if (first && cs.length) { chart.current?.timeScale().fitContent(); first = false; }
      }).catch(() => {});
    load();
    const id = setInterval(load, 1000); // poll the live candle once a second
    return () => { alive = false; clearInterval(id); };
  }, [selected, runId]);

  useEffect(() => {
    const series = candle.current;
    if (!series || !forecast) return;
    const lines = [
      { price: forecast.price, title: "Forecast median", color: "#557A95" },
      { price: forecast.lower, title: "Forecast low", color: "#26343D" },
      { price: forecast.upper, title: "Forecast high", color: "#26343D" },
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
          phase: {phase}
        </span>}
      </h2>
      <div ref={box} className="chartbox" />
    </div>
  );
}
