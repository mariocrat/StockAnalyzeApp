import { useEffect, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CrosshairMode,
  createSeriesMarkers,
} from 'lightweight-charts';

const intFmt = (value) => new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value || 0);
const maFmt = (value) => new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(value || 0);

function candleRows(candles) {
  const candleData = [];
  const volumeData = [];
  const ma5 = [];
  const ma20 = [];
  for (const row of candles || []) {
    const item = {
      time: row.time,
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
    };
    if (!Number.isFinite(item.close) || item.close <= 0) continue;
    candleData.push(item);
    volumeData.push({
      time: row.time,
      value: Number(row.volume || 0),
      color: item.close >= item.open ? 'rgba(239,83,80,0.55)' : 'rgba(38,166,154,0.55)',
    });
    if (row.ma5) ma5.push({ time: row.time, value: Number(row.ma5) });
    if (row.ma20) ma20.push({ time: row.time, value: Number(row.ma20) });
  }
  return { candleData, volumeData, ma5, ma20 };
}

export default function JournalTradeChart({ chartData }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !chartData?.candles?.length) return undefined;
    const { candleData, volumeData, ma5, ma20 } = candleRows(chartData.candles);
    if (!candleData.length) return undefined;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 430,
      layout: { background: { type: 'solid', color: '#151924' }, textColor: '#c0c3cc', fontSize: 12 },
      grid: { vertLines: { color: 'rgba(42,46,57,0.4)' }, horzLines: { color: 'rgba(42,46,57,0.4)' } },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: { borderColor: 'rgba(197,203,206,0.3)' },
      timeScale: {
        borderColor: 'rgba(197,203,206,0.3)',
        timeVisible: chartData.timeframe === 'intraday',
        secondsVisible: false,
      },
      localization: { dateFormat: 'yyyy-MM-dd' },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef5350',
      downColor: '#26a69a',
      borderUpColor: '#ef5350',
      borderDownColor: '#26a69a',
      wickUpColor: '#ef5350',
      wickDownColor: '#26a69a',
      priceFormat: { type: 'custom', formatter: (p) => intFmt(p), minMove: 1 },
    }, 0);
    candleSeries.setData(candleData);

    const ma5Series = chart.addSeries(LineSeries, {
      color: '#f6c90e',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'custom', formatter: (p) => maFmt(p) },
    }, 0);
    ma5Series.setData(ma5);

    const ma20Series = chart.addSeries(LineSeries, {
      color: '#4fc3f7',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'custom', formatter: (p) => maFmt(p) },
    }, 0);
    ma20Series.setData(ma20);

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'right',
    }, 1);
    volumeSeries.setData(volumeData);

    const markers = chartData.markers || [];
    createSeriesMarkers(candleSeries, markers);
    const markersByTime = new Map(markers.map(marker => [String(marker.time), marker]));

    const tooltip = document.createElement('div');
    tooltip.className = 'journal-marker-tooltip';
    tooltip.style.display = 'none';
    containerRef.current.appendChild(tooltip);

    chart.subscribeCrosshairMove((param) => {
      if (!param?.point || param.time == null) {
        tooltip.style.display = 'none';
        return;
      }
      const marker = markersByTime.get(String(param.time));
      if (!marker?.tooltip) {
        tooltip.style.display = 'none';
        return;
      }
      const prices = (marker.tooltip.prices || []).map(price => intFmt(price)).join(', ');
      tooltip.replaceChildren();
      const title = document.createElement('strong');
      title.textContent = `${marker.tooltip.label}${marker.tooltip.count > 1 ? ` ${marker.tooltip.count}건` : ''}`;
      const summary = document.createElement('span');
      summary.textContent = `평균 ${intFmt(marker.tooltip.avg_price)}원 · 수량 ${marker.tooltip.total_quantity}`;
      const detail = document.createElement('em');
      detail.textContent = `${prices}원`;
      tooltip.append(title, summary, detail);
      const x = Math.min(Math.max(param.point.x + 12, 8), containerRef.current.clientWidth - 210);
      const y = Math.min(Math.max(param.point.y + 12, 8), containerRef.current.clientHeight - 92);
      tooltip.style.left = `${x}px`;
      tooltip.style.top = `${y}px`;
      tooltip.style.display = 'block';
    });
    chart.timeScale().fitContent();

    return () => {
      tooltip.remove();
      chart.remove();
    };
  }, [chartData]);

  if (!chartData?.candles?.length) {
    return <div className="journal-chart-empty">표시할 차트 데이터가 없습니다.</div>;
  }

  return <div className="journal-trade-chart" ref={containerRef} />;
}
