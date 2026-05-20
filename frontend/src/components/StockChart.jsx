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
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c) || h < l || c <= 0) continue;
    seen.add(d.Date);
    candles.push({ time: d.Date, open: o, high: h, low: l, close: c, volume: v });
    vols.push({ time: d.Date, value: v, color: c >= o ? 'rgba(239,83,80,0.6)' : 'rgba(38,166,154,0.6)' });
  }
  candles.sort((a, b) => a.time.localeCompare(b.time));
  vols.sort((a, b) => a.time.localeCompare(b.time));
  return { candles, vols };
}

// resampleCandles removed, backend handles it

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
function applyAllData(st, bbPer, bbMul, rawData) {
  const { series, allCandles, allVols } = st;
  if (!allCandles || allCandles.length === 0) return;
  if (!series.candle) return;
  st.currentCandles = allCandles;

  try {
    series.candle.setData(allCandles);
    if (allVols.length > 0) series.vol?.setData(allVols);

    for (const { key, w } of MA_CONFIG) {
      const maData = computeMA(allCandles, w);
      if (maData.length > 0) series[key]?.setData(maData);
    }
    
    const { upper, basis, lower } = computeBB(allCandles, bbPer||20, bbMul||2);
    if (upper.length > 0) series.BB_U?.setData(upper); 
    if (basis.length > 0) series.BB_M?.setData(basis); 
    if (lower.length > 0) series.BB_L?.setData(lower);
    
    const rsiData = computeRSI(allCandles, 14);
    if (rsiData.length > 0) series.RSI?.setData(rsiData);

    // Handle MACD, Stoch, Ichimoku from backend if available
    if (rawData && rawData.length) {
      const macdData = [], signalData = [], histData = [];
      const stochK = [], stochD = [];
      const ichiT = [], ichiK = [], ichiSA = [], ichiSB = [];

      rawData.forEach(d => {
        if (!d.Date) return;
        
        if (d.MACD !== undefined && d.MACD !== null) {
          macdData.push({ time: d.Date, value: d.MACD });
          signalData.push({ time: d.Date, value: d.MACD_Signal });
          histData.push({ time: d.Date, value: d.MACD_Hist, color: d.MACD_Hist >= 0 ? 'rgba(38,166,154,0.8)' : 'rgba(239,83,80,0.8)' });
        }
        if (d.Stoch_K !== undefined && d.Stoch_K !== null) {
          stochK.push({ time: d.Date, value: d.Stoch_K });
          if (d.Stoch_D !== null) stochD.push({ time: d.Date, value: d.Stoch_D });
        }
        // Ichimoku components
        if (d.Ichi_Tenkan !== undefined && d.Ichi_Tenkan !== null) ichiT.push({ time: d.Date, value: d.Ichi_Tenkan });
        if (d.Ichi_Kijun !== undefined && d.Ichi_Kijun !== null) ichiK.push({ time: d.Date, value: d.Ichi_Kijun });
        if (d.Ichi_Senkou_A !== undefined && d.Ichi_Senkou_A !== null) ichiSA.push({ time: d.Date, value: d.Ichi_Senkou_A });
        if (d.Ichi_Senkou_B !== undefined && d.Ichi_Senkou_B !== null) ichiSB.push({ time: d.Date, value: d.Ichi_Senkou_B });
      });

      if (macdData.length > 0) {
        if (series.MACD) series.MACD.setData(macdData);
        if (series.MACD_S) series.MACD_S.setData(signalData);
        if (series.MACD_H) series.MACD_H.setData(histData);
      }
      
      if (stochK.length > 0) {
        if (series.STOCH_K) series.STOCH_K.setData(stochK);
        if (series.STOCH_D) series.STOCH_D.setData(stochD);
      }
      
      if (ichiT.length > 0) {
        if (series.ICHI_T) series.ICHI_T.setData(ichiT);
        if (series.ICHI_K) series.ICHI_K.setData(ichiK);
      }
      if (ichiSA.length > 0 && series.ICHI_SA) series.ICHI_SA.setData(ichiSA);
      if (ichiSB.length > 0 && series.ICHI_SB) series.ICHI_SB.setData(ichiSB);
    }
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
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [localInds, setLocalInds] = React.useState(activeInds || {});

  useImperativeHandle(ref, () => ({
    setVisibleTimeRange: (range) => { try { stateRef.current.chart?.timeScale().setVisibleRange(range); } catch(err){ console.debug(err); } },
  }));

  // Sync external indicators to local, but prioritize local if in fullscreen
  useEffect(() => { if (!isFullscreen) setLocalInds(activeInds); }, [activeInds, isFullscreen]);

  // Keep activeIndsRef in sync
  useEffect(() => { activeIndsRef.current = isFullscreen ? localInds : activeInds; }, [activeInds, localInds, isFullscreen]);

  // ── Build chart once ──────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || !data || !Array.isArray(data) || data.length === 0) return;
    const { candles, vols } = buildCandleRows(data);
    if (!candles || candles.length === 0) return;

    // Destroy old
    if (stateRef.current.chart) {
      try { stateRef.current.chart.remove(); } catch(err){ console.debug(err); }
      stateRef.current = { chart: null, series: {}, allCandles: [], allVols: [], currentCandles: [] };
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
    stateRef.current.allVols = vols;

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
      visible: activeIndsRef.current?.RSI ?? false,
    }, 2);
    stateRef.current.series.RSI = rsiSeries;

    // RSI 30/70 reference lines
    rsiSeries.createPriceLine({ price: 70, color: '#ef535066', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    rsiSeries.createPriceLine({ price: 30, color: '#26a69a66', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });

    // ── Pane 3: MACD (Expert Mode) ────────────────────────────────────
    const macdSeries = chart.addSeries(LineSeries, {
      color: '#2962ff', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, visible: activeIndsRef.current?.MACD ?? false,
    }, 3);
    const signalSeries = chart.addSeries(LineSeries, {
      color: '#ff9800', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, visible: activeIndsRef.current?.MACD ?? false,
    }, 3);
    const histSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, visible: activeIndsRef.current?.MACD ?? false,
    }, 3);
    stateRef.current.series.MACD = macdSeries;
    stateRef.current.series.MACD_S = signalSeries;
    stateRef.current.series.MACD_H = histSeries;

    // ── Pane 4: Stochastic (Expert Mode) ──────────────────────────────
    const stochK = chart.addSeries(LineSeries, {
      color: '#ff5252', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, visible: activeIndsRef.current?.STOCH ?? false,
      priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
    }, 4);
    const stochD = chart.addSeries(LineSeries, {
      color: '#448aff', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, visible: activeIndsRef.current?.STOCH ?? false,
    }, 4);
    stochK.createPriceLine({ price: 80, color: '#ef535066', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    stochK.createPriceLine({ price: 20, color: '#26a69a66', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    stateRef.current.series.STOCH_K = stochK;
    stateRef.current.series.STOCH_D = stochD;

    // ── Ichimoku Cloud (Main Pane 0) ──────────────────────────────────
    const ichiBase = { lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, visible: activeIndsRef.current?.ICHI ?? false };
    stateRef.current.series.ICHI_T = chart.addSeries(LineSeries, { ...ichiBase, color: '#2962ff' }, 0); // Tenkan
    stateRef.current.series.ICHI_K = chart.addSeries(LineSeries, { ...ichiBase, color: '#ff5252' }, 0); // Kijun
    stateRef.current.series.ICHI_SA = chart.addSeries(LineSeries, { ...ichiBase, color: '#81c784', lineStyle: 2 }, 0); // Senkou A
    stateRef.current.series.ICHI_SB = chart.addSeries(LineSeries, { ...ichiBase, color: '#e57373', lineStyle: 2 }, 0); // Senkou B

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
      
      const candles = stateRef.current.currentCandles;
      const idx = candles.findIndex(c => c.time === param.time);
      let pctStr = '';
      if (idx > 0) {
        const prevClose = candles[idx - 1].close;
        const pct = ((ohlc.close - prevClose) / prevClose) * 100;
        const pctColor = pct > 0 ? '#ef5350' : pct < 0 ? '#26a69a' : '#888';
        const sign = pct > 0 ? '+' : '';
        pctStr = ` <span style="color:${pctColor}">(${sign}${pct.toFixed(2)}%)</span>`;
      }

      const lines = [
        `<span style="color:#888">${param.time}</span>`,
        `시 <b>${intFmt(ohlc.open)}</b>  고 <b style="color:#ef5350">${intFmt(ohlc.high)}</b>  저 <b style="color:#26a69a">${intFmt(ohlc.low)}</b>  종 <b>${intFmt(ohlc.close)}</b>${pctStr}`,
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
      
      const macdV = param.seriesData.get(macdSeries);
      const sigV = param.seriesData.get(signalSeries);
      const histV = param.seriesData.get(histSeries);
      if (inds?.MACD && macdV?.value != null && sigV?.value != null) {
        lines.push(`<span>MACD(12,26) <b style="color:#2962ff">${macdV.value.toFixed(2)}</b> / Sig(9) <b style="color:#ff9800">${sigV.value.toFixed(2)}</b> / Hist <b style="color:${histV.value>=0?'#26a69a':'#ef5350'}">${histV.value.toFixed(2)}</b></span>`);
      }

      const sK = param.seriesData.get(stochK);
      const sD = param.seriesData.get(stochD);
      if (inds?.STOCH && sK?.value != null && sD?.value != null) {
        lines.push(`<span>Stoch(14,3) %K <b style="color:#ff5252">${sK.value.toFixed(1)}</b> / %D <b style="color:#448aff">${sD.value.toFixed(1)}</b></span>`);
      }

      const iT = param.seriesData.get(stateRef.current.series.ICHI_T);
      const iK = param.seriesData.get(stateRef.current.series.ICHI_K);
      if (inds?.ICHI && iT?.value != null && iK?.value != null) {
        lines.push(`<span>일목 전환 <b style="color:#2962ff">${iT.value.toFixed(0)}</b> / 기준 <b style="color:#ff5252">${iK.value.toFixed(0)}</b></span>`);
      }

      tooltip.innerHTML = lines.filter(Boolean).join('<br>');
      tooltip.style.display = 'block';
    });

    // ── Apply initial data ────────────────────────────────────────────
    applyAllData(stateRef.current, bbPeriod ?? 20, bbMultiplier ?? 2, data);

    // Initial zoom
    const days = PERIOD_DAYS[chartPeriod] ?? 90;
    try { chart.timeScale().setVisibleRange(getVisibleRange(days)); }
    catch(_) { try { chart.timeScale().fitContent(); } catch(err2){ console.debug(err2); } }

    // Apply scale mode
    try {
      chart.priceScale('right').applyOptions({
        mode: scaleMode === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      });
    } catch(err){ console.debug(err); }

    return () => {
      try { chart.remove(); } catch(err){ console.debug(err); }
      if (stateRef.current.chart === chart) stateRef.current = { chart: null, series: {}, allCandles: [], allVols: [], currentCandles: [] };
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, ticker]);

  // ── candlePeriod → resample done via backend, just zoom out ────────
  useEffect(() => {
    if (!stateRef.current.chart || !chartPeriod) return;
    try { stateRef.current.chart.timeScale().setVisibleRange(getVisibleRange(PERIOD_DAYS[chartPeriod] ?? 90)); } catch(err){ console.debug(err); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candlePeriod]);

  // ── chartPeriod → zoom only ───────────────────────────────────────────
  useEffect(() => {
    if (!stateRef.current.chart || !chartPeriod) return;
    try { stateRef.current.chart.timeScale().setVisibleRange(getVisibleRange(PERIOD_DAYS[chartPeriod] ?? 90)); } catch(err){ console.debug(err); }
  }, [chartPeriod]);

  // ── scaleMode ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!stateRef.current.chart) return;
    try {
      stateRef.current.chart.priceScale('right').applyOptions({
        mode: scaleMode === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      });
    } catch(err){ console.debug(err); }
  }, [scaleMode]);

  // ── activeInds (local or global) → visibility ──────────────────────────
  useEffect(() => {
    const { series } = stateRef.current;
    const currentInds = activeIndsRef.current;
    if (!series.candle || !currentInds) return;
    try {
      for (const { key } of MA_CONFIG) series[key]?.applyOptions({ visible: currentInds[key] ?? false });
      const bbV = currentInds.BB ?? false;
      series.BB_U?.applyOptions({ visible: bbV }); series.BB_M?.applyOptions({ visible: bbV }); series.BB_L?.applyOptions({ visible: bbV });
      series.RSI?.applyOptions({ visible: currentInds.RSI ?? false });
      
      const macdV = currentInds.MACD ?? false;
      series.MACD?.applyOptions({ visible: macdV });
      series.MACD_S?.applyOptions({ visible: macdV });
      series.MACD_H?.applyOptions({ visible: macdV });

      const stochV = currentInds.STOCH ?? false;
      series.STOCH_K?.applyOptions({ visible: stochV });
      series.STOCH_D?.applyOptions({ visible: stochV });

      const ichiV = currentInds.ICHI ?? false;
      series.ICHI_T?.applyOptions({ visible: ichiV });
      series.ICHI_K?.applyOptions({ visible: ichiV });
      series.ICHI_SA?.applyOptions({ visible: ichiV });
      series.ICHI_SB?.applyOptions({ visible: ichiV });
    } catch(err){ console.debug(err); }
  }, [localInds, activeInds, isFullscreen]);

  // ── bbPeriod/bbMultiplier → recompute BB ─────────────────────────────
  useEffect(() => {
    const { series, currentCandles } = stateRef.current;
    if (!series.BB_U || !currentCandles?.length) return;
    try {
      const { upper, basis, lower } = computeBB(currentCandles, bbPeriod ?? 20, bbMultiplier ?? 2);
      series.BB_U.setData(upper); series.BB_M.setData(basis); series.BB_L.setData(lower);
    } catch(err){ console.debug(err); }
  }, [bbPeriod, bbMultiplier]);

  return (
    <div style={isFullscreen ? {
        position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
        zIndex: 9999, background: '#151924', padding: '20px', boxSizing: 'border-box',
        display: 'flex', flexDirection: 'column'
      } : { 
        marginBottom: '8px', background: '#151924', borderRadius: '8px', 
        padding: '10px 12px', boxShadow: '0 1px 8px rgba(0,0,0,0.4)' 
      }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <h3 style={{ color: '#fff', margin: 0, fontSize: '14px', fontWeight: 600 }}>
          {name}
          <span style={{ color: '#444', fontWeight: 400, fontSize: '12px', marginLeft: '6px' }}>({ticker})</span>
        </h3>
        
        {/* Fullscreen HTS Toggles */}
        {isFullscreen && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {['MA_5', 'MA_10', 'MA_20', 'MA_60', 'MA_120', 'BB', 'RSI', 'MACD', 'STOCH', 'ICHI'].map(ind => (
              <label key={ind} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: localInds[ind] ? '#2962ff' : '#888' }}>
                <input type="checkbox" checked={localInds[ind] || false} onChange={() => setLocalInds(p => ({ ...p, [ind]: !p[ind] }))} style={{ margin: 0 }} />
                {ind.replace('MA_', '')}
              </label>
            ))}
          </div>
        )}

        <button 
          onClick={() => {
            setIsFullscreen(!isFullscreen);
            // Trigger a resize on next tick to ensure fitContent works well
            setTimeout(() => {
              if (stateRef.current.chart) {
                try { stateRef.current.chart.timeScale().fitContent(); } catch(err){ console.debug(err); }
              }
            }, 50);
          }}
          style={{ 
            background: '#2962ff', color: '#fff', border: 'none', 
            borderRadius: '4px', padding: '4px 10px', fontSize: '12px', cursor: 'pointer',
            fontWeight: 600
          }}>
          {isFullscreen ? '<닫기>' : '<자세히 보기>'}
        </button>
      </div>
      <div style={{ position: 'relative', flex: isFullscreen ? 1 : 'none' }}>
        <div ref={containerRef} style={{ width: '100%', height: isFullscreen ? '100%' : '500px', backgroundColor: '#151924' }} />
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
