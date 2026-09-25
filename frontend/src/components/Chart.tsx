import { useEffect, useRef } from "react";
import {
  createChart, ColorType, LineStyle, type IChartApi,
  type ISeriesApi, type UTCTimestamp, type Time,
} from "lightweight-charts";
import { useStore } from "../store";
import { getCandles } from "../api";
import { useChartPalette } from "../chartTheme";

export default function Chart() {
  const selected = useStore((s) => s.selected);
  const runId = useStore((s) => s.snap?.arena.id);
  const phase = useStore((s) => s.snap?.symbols.find((x) => x.symbol === selected)?.phase);
  const forecast = useStore((s) => s.snap?.model?.signals[selected]);
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candle = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const vol = useRef<ISeriesApi<"Histogram"> | null>(null);
  const palette = useChartPalette();
  const colors = useRef(palette);
  colors.current = palette;
  const candles = useRef<Awaited<ReturnType<typeof getCandles>>>([]);

  useEffect(() => {
    if (!box.current) return;
    const c = createChart(box.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: palette.bg }, textColor: palette.text, fontSize: 12, attributionLogo: false },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      timeScale: { borderColor: palette.grid, tickMarkFormatter: (time: Time) => `T${Number(time) * 20}` },
      localization: { timeFormatter: (time: Time) => `Tick ${Number(time) * 20}` },
      rightPriceScale: { borderColor: palette.grid },
    });
    candle.current = c.addCandlestickSeries({
      upColor: palette.up, downColor: palette.down, borderVisible: false,
      wickUpColor: palette.up, wickDownColor: palette.down,
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
    chart.current?.applyOptions({
      layout: { background: { type: ColorType.Solid, color: palette.bg }, textColor: palette.text },
      grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
      timeScale: { borderColor: palette.grid }, rightPriceScale: { borderColor: palette.grid },
    });
    candle.current?.applyOptions({ upColor: palette.up, downColor: palette.down, wickUpColor: palette.up, wickDownColor: palette.down });
    vol.current?.setData(candles.current.map(c => ({ time: c.t as UTCTimestamp, value: c.v, color: c.c >= c.o ? `${palette.up}55` : `${palette.down}55` })));
  }, [palette]);

  useEffect(() => {
    let alive = true;
    let first = true;
    candle.current?.setData([]);
    vol.current?.setData([]);
    const load = () =>
      getCandles(selected).then((cs) => {
        if (!alive || !candle.current || !vol.current) return;
        candles.current = cs;
        candle.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, open: c.o, high: c.h, low: c.l, close: c.c,
        })));
        vol.current.setData(cs.map((c) => ({
          time: c.t as UTCTimestamp, value: c.v, color: c.c >= c.o ? `${colors.current.up}55` : `${colors.current.down}55`,
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
      { price: forecast.price, title: "Forecast median", color: palette.accent },
      { price: forecast.lower, title: "Forecast low", color: palette.text },
      { price: forecast.upper, title: "Forecast high", color: palette.text },
    ].map((line) => series.createPriceLine({ ...line, lineWidth: 1, lineStyle: LineStyle.Dashed }));
    return () => {
      if (candle.current === series) lines.forEach((line) => series.removePriceLine(line));
    };
  }, [forecast, palette]);

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
