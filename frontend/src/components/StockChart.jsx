import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import {
  createChart, CrosshairMode, PriceScaleMode,
  CandlestickSeries, HistogramSeries, LineSeries,
} from 'lightweight-charts';

// ── Constants ─────────────────────────────────────────────────────────────
const PERIOD_DAYS = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365 };
const MA_CONFIG = [
  { key: 'MA_5',   color: '#e040fb', w: 5  },
  { key: 'MA_10',  color: '#ff9800', w: 10 },
  { key: 'MA_20',  color: '#f6c90e', w: 20 },
  { key: 'MA_60',  color: '#4fc3f7', w: 60 },
  { key: 'MA_120', color: '#ff7043', w: 120 },
];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// ── Number formatters ─────────────────────────────────────────────────────
const intFmt = (v) => new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(v);
const maFmt  = (v) => new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(v);
const volFmt = (v) => new Intl.NumberFormat('ko-KR', { notation: 'compact', maximumFractionDigits: 1 }).format(v);

// ── Data helpers ──────────────────────────────────────────────────────────
function buildCandleRows(data) {
  const seen = new Set(), candles = [], vols = [];
  for (const d of data) {
    if (!d?.Date || !DATE_RE.test(d.Date) || seen.has(d.Date)) continue;
    const o = +d.Open, h = +d.High, l = +d.Low, c = +d.Close, v = Math.max(+d.Volume || 0, 0);
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c) || h < l) continue;
    seen.add(d.Date);
    candles.push({ time: d.Date, open: o, high: h, low: l, close: c, volume: v });
    vols.push({ time: d.Date, value: v, color: c >= o ? 'rgba(239,83,80,0.6)' : 'rgba(38,166,154,0.6)' });
  }
  candles.sort((a, b) => a.time.localeCompare(b.time));
  vols.sort((a, b) => a.time.localeCompare(b.time));
  return { candles, vols };
}

function resampleCandles(candles, period) {
  if (period === 'D') {
    return {
      rCandles: candles,
      rVols: candles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? 'rgba(239,83,80,0.6)' : 'rgba(38,166,154,0.6)' })),
    };
  }
  const groups = new Map();
  for (const c of candles) {
    let key = c.time;
    if (period === 'W') {
      const d = new Date(c.time), day = d.getDay();
      d.setDate(d.getDate() + (day === 0 ? -6 : 1 - day));
      key = d.toISOString().split('T')[0];
    } else if (period === 'M') {
      key = c.time.substring(0, 7) + '-01';
    }
    if (!groups.has(key)) groups.set(key, { time: key, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume });
    else {
      const g = groups.get(key);
      g.high = Math.max(g.high, c.high); g.low = Math.min(g.low, c.low);
      g.close = c.close; g.volume += c.volume;
    }
  }
  const rCandles = [...groups.values()].sort((a, b) => a.time.localeCompare(b.time));
  const rVols = rCandles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? 'rgba(239,83,80,0.6)' : 'rgba(38,166,154,0.6)' }));
  return { rCandles, rVols };
}

const computeMA  = (candles, w) => candles.slice(w - 1).map((_, i) => ({ time: candles[i + w - 1].time, value: candles.slice(i, i + w).reduce((s, c) => s + c.close, 0) / w }));
const computeBB  = (candles, p, m) => { const u=[],b=[],l=[]; candles.slice(p-1).forEach((_,i)=>{ const sl=candles.slice(i,i+p), mn=sl.reduce((s,c)=>s+c.close,0)/p, sd=Math.sqrt(sl.reduce((s,c)=>s+(c.close-mn)**2,0)/p); b.push({time:candles[i+p-1].time,value:mn}); u.push({time:candles[i+p-1].time,value:mn+m*sd}); l.push({time:candles[i+p-1].time,value:mn-m*sd}); }); return {upper:u,basis:b,lower:l}; };
const computeRSI = (candles, period=14) => {
  if (candles.length < period + 1) return [];
  const closes = candles.map(c => c.close), res = [];
  let ag = 0, al = 0;
  for (let i = 1; i <= period; i++) { const d = closes[i] - closes[i-1]; d > 0 ? ag += d : al -= d; }
  ag /= period; al /= period;
  for (let i = period; i < candles.length; i++) {
    if (i > period) { const d = closes[i] - closes[i-1]; ag = (ag*(period-1)+Math.max(d,0))/period; al = (al*(period-1)+Math.max(-d,0))/period; }
    res.push({ time: candles[i].time, value: parseFloat((100 - 100/(1+(al===0?Infinity:ag/al))).toFixed(2)) });
  }
  return res;
};

function getVisibleRange(days) {
  const e = new Date(), s = new Date();
  s.setDate(e.getDate() - days);
  return { from: s.toISOString().split('T')[0], to: e.toISOString().split('T')[0] };
}

// ── Imperative helper: apply all data to series ───────────────────────────
function applyAllData(st, candlePeriod, bbPer, bbMul) {
  const { series, allCandles } = st;
  if (!series.candle || !allCandles.length) return;
  const { rCandles, rVols } = resampleCandles(allCandles, candlePeriod || 'D');
  st.currentCandles = rCandles;
  try {
    series.candle.setData(rCandles);
    series.vol.setData(rVols);
    for (const { key, w } of MA_CONFIG) series[key]?.setData(computeMA(rCandles, w));
    const { upper, basis, lower } = computeBB(rCandles, bbPer||20, bbMul||2);
    series.BB_U?.setData(upper); series.BB_M?.setData(basis); series.BB_L?.setData(lower);
    series.RSI?.setData(computeRSI(rCandles, 14));
  } catch (e) { console.error('[applyAllData]', e); }
}

// ── Component ─────────────────────────────────────────────────────────────
const StockChart = forwardRef(({
  data, ticker, name,
  chartPeriod, candlePeriod, scaleMode,
  activeInds, bbPeriod, bbMultiplier,
  onTimeRangeChange,
}, ref) => {
  const containerRef    = useRef(null);
  const tooltipRef      = useRef(null);
  const stateRef        = useRef({ chart: null, series: {}, allCandles: [], currentCandles: [] });
  // Ref to always read the LATEST activeInds inside event-handler closures
  const activeIndsRef   = useRef(activeInds);

  useImperativeHandle(ref, () => ({
    setVisibleTimeRange: (range) => { try { stateRef.current.chart?.timeScale().setVisibleRange(range); } catch(_){} },
  }));

  // Keep activeIndsRef in sync whenever the prop changes
  useEffect(() => { activeIndsRef.current = activeInds; }, [activeInds]);

  // ── Build chart once ──────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || !data?.length) return;
    const { candles, vols } = buildCandleRows(data);
    if (!candles.length) return;

    // Destroy old
    if (stateRef.current.chart) {
      try { stateRef.current.chart.remove(); } catch(_){}
      stateRef.current = { chart: null, series: {}, allCandles: [], currentCandles: [] };
    }

    let chart;
    try {
      chart = createChart(containerRef.current, {
        autoSize: true,
        height: 500,
        layout: { background: { type: 'solid', color: '#151924' }, textColor: '#c0c3cc', fontSize: 12 },
        grid: { vertLines: { color: 'rgba(42,46,57,0.4)' }, horzLines: { color: 'rgba(42,46,57,0.4)' } },
        crosshair: { mode: CrosshairMode.Magnet },
        rightPriceScale: { borderColor: 'rgba(197,203,206,0.3)' },
        timeScale: { borderColor: 'rgba(197,203,206,0.3)', timeVisible: false, secondsVisible: false },
        localization: { dateFormat: 'yyyy-MM-dd' },
      });
    } catch(err) { console.error('[StockChart] createChart failed', err); return; }

    stateRef.current.chart = chart;
    stateRef.current.allCandles = candles;

    // ── Pane 0: Candlestick (main chart) ─────────────────────────────
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef5350', downColor: '#26a69a',
      borderUpColor: '#ef5350', borderDownColor: '#26a69a',
      wickUpColor: '#ef5350', wickDownColor: '#26a69a',
      priceFormat: { type: 'custom', formatter: (p) => intFmt(p), minMove: 1 },
    }, 0);
    stateRef.current.series.candle = candleSeries;

    // MA lines — pane 0
    for (const { key, color } of MA_CONFIG) {
      const s = chart.addSeries(LineSeries, {
        color, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        priceFormat: { type: 'custom', formatter: (p) => maFmt(p) },
        visible: activeInds?.[key] ?? false,
      }, 0);
      stateRef.current.series[key] = s;
    }

    // BB — pane 0
    const bbV = activeInds?.BB ?? false;
    const bbBase = { color: '#b39ddb', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: bbV };
    stateRef.current.series.BB_U = chart.addSeries(LineSeries, { ...bbBase, lineStyle: 2 }, 0);
    stateRef.current.series.BB_M = chart.addSeries(LineSeries, { ...bbBase, lineStyle: 0 }, 0);
    stateRef.current.series.BB_L = chart.addSeries(LineSeries, { ...bbBase, lineStyle: 2 }, 0);

    // ── Pane 1: Volume (completely separate pane → NO negative Y values) ─
    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'right',
    }, 1);
    stateRef.current.series.vol = volSeries;

    // ── Pane 2: RSI ───────────────────────────────────────────────────
    const rsiSeries = chart.addSeries(LineSeries, {
      color: '#26a69a', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
      priceScaleId: 'right',
      priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
      visible: activeInds?.RSI ?? false,
    }, 2);
    stateRef.current.series.RSI = rsiSeries;

    // RSI 30/70 reference lines
    rsiSeries.createPriceLine({ price: 70, color: '#ef535066', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    rsiSeries.createPriceLine({ price: 30, color: '#26a69a66', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });

    // ── Cross-chart time sync ─────────────────────────────────────────
    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (onTimeRangeChange && range) onTimeRangeChange(ticker, range);
    });

    // ── Tooltip — reads activeIndsRef so it always sees the CURRENT state ──
    const tooltip = tooltipRef.current;
    chart.subscribeCrosshairMove((param) => {
      if (!tooltip) return;
      if (!param.time || !param.seriesData?.size) { tooltip.style.display = 'none'; return; }
      const ohlc = param.seriesData.get(candleSeries);
      const vol  = param.seriesData.get(volSeries);
      if (!ohlc) { tooltip.style.display = 'none'; return; }

      const inds = activeIndsRef.current;   // ← always latest
      const lines = [
        `<span style="color:#888">${param.time}</span>`,
        `시 <b>${intFmt(ohlc.open)}</b>  고 <b style="color:#ef5350">${intFmt(ohlc.high)}</b>  저 <b style="color:#26a69a">${intFmt(ohlc.low)}</b>  종 <b>${intFmt(ohlc.close)}</b>`,
        vol ? `거래량 <b>${volFmt(vol.value)}</b>` : null,
      ];

      // Loop ALL MA series — only add line when that indicator is toggled ON
      for (const { key, color } of MA_CONFIG) {
        if (inds?.[key]) {
          const v = param.seriesData.get(stateRef.current.series[key]);
          if (v?.value != null) lines.push(
            `<span style="color:${color}">${key.replace('_',' ')} <b>${maFmt(v.value)}</b></span>`
          );
        }
      }
      const rsiV = param.seriesData.get(rsiSeries);
      if (inds?.RSI && rsiV?.value != null)
        lines.push(`<span style="color:#26a69a">RSI(14) <b>${rsiV.value.toFixed(1)}</b></span>`);

      tooltip.innerHTML = lines.filter(Boolean).join('<br>');
      tooltip.style.display = 'block';
    });

    // ── Apply initial data ────────────────────────────────────────────
    applyAllData(stateRef.current, candlePeriod ?? 'D', bbPeriod ?? 20, bbMultiplier ?? 2);

    // Initial zoom
    const days = PERIOD_DAYS[chartPeriod] ?? 90;
    try { chart.timeScale().setVisibleRange(getVisibleRange(days)); }
    catch(_) { try { chart.timeScale().fitContent(); } catch(_2){} }

    // Apply scale mode
    try {
      chart.priceScale('right').applyOptions({
        mode: scaleMode === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      });
    } catch(_){}

    return () => {
      try { chart.remove(); } catch(_){}
      if (stateRef.current.chart === chart) stateRef.current = { chart: null, series: {}, allCandles: [], currentCandles: [] };
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, ticker]);

  // ── candlePeriod → resample + fitContent ─────────────────────────────
  useEffect(() => {
    const st = stateRef.current;
    if (!st.chart || !st.allCandles.length) return;
    applyAllData(st, candlePeriod ?? 'D', bbPeriod ?? 20, bbMultiplier ?? 2);
    try { st.chart.timeScale().fitContent(); } catch(_){}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candlePeriod]);

  // ── chartPeriod → zoom only ───────────────────────────────────────────
  useEffect(() => {
    if (!stateRef.current.chart || !chartPeriod) return;
    try { stateRef.current.chart.timeScale().setVisibleRange(getVisibleRange(PERIOD_DAYS[chartPeriod] ?? 90)); } catch(_){}
  }, [chartPeriod]);

  // ── scaleMode ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!stateRef.current.chart) return;
    try {
      stateRef.current.chart.priceScale('right').applyOptions({
        mode: scaleMode === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      });
    } catch(_){}
  }, [scaleMode]);

  // ── activeInds → visibility ───────────────────────────────────────────
  useEffect(() => {
    const { series } = stateRef.current;
    if (!series.candle || !activeInds) return;
    try {
      for (const { key } of MA_CONFIG) series[key]?.applyOptions({ visible: activeInds[key] ?? false });
      const bbV = activeInds.BB ?? false;
      series.BB_U?.applyOptions({ visible: bbV }); series.BB_M?.applyOptions({ visible: bbV }); series.BB_L?.applyOptions({ visible: bbV });
      series.RSI?.applyOptions({ visible: activeInds.RSI ?? false });
    } catch(_){}
  }, [activeInds]);

  // ── bbPeriod/bbMultiplier → recompute BB ─────────────────────────────
  useEffect(() => {
    const { series, currentCandles } = stateRef.current;
    if (!series.BB_U || !currentCandles?.length) return;
    try {
      const { upper, basis, lower } = computeBB(currentCandles, bbPeriod ?? 20, bbMultiplier ?? 2);
      series.BB_U.setData(upper); series.BB_M.setData(basis); series.BB_L.setData(lower);
    } catch(_){}
  }, [bbPeriod, bbMultiplier]);

  return (
    <div style={{ marginBottom: '8px', background: '#151924', borderRadius: '8px', padding: '10px 12px', boxShadow: '0 1px 8px rgba(0,0,0,0.4)' }}>
      <h3 style={{ color: '#fff', margin: '0 0 6px 0', fontSize: '14px', fontWeight: 600 }}>
        {name}
        <span style={{ color: '#444', fontWeight: 400, fontSize: '12px', marginLeft: '6px' }}>({ticker})</span>
      </h3>
      <div style={{ position: 'relative' }}>
        <div ref={containerRef} style={{ width: '100%', height: '500px', backgroundColor: '#151924' }} />
        <div ref={tooltipRef} style={{
          display: 'none', position: 'absolute', top: '8px', left: '8px', zIndex: 20,
          background: 'rgba(15,18,28,0.93)', border: '1px solid #2a2e39', borderRadius: '6px',
          padding: '8px 12px', fontSize: '12px', lineHeight: '1.75', color: '#d1d4dc',
          pointerEvents: 'none', backdropFilter: 'blur(4px)', boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
          minWidth: '200px',
        }} />
      </div>
    </div>
  );
});

export default StockChart;
