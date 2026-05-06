import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

const StockChart = forwardRef(({ data, ticker, name, onTimeRangeChange, onCrosshairMove }, ref) => {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    setVisibleTimeRange: (range) => {
      if (chartRef.current) {
        chartRef.current.timeScale().setVisibleRange(range);
      }
    },
    setCrosshairPosition: (price, time, series) => {
        // Unfortunately lightweight-charts doesn't natively expose an easy API to programmatically move crosshair
        // A common workaround is to sync the tooltip or let the parent handle a floating tooltip
    }
  }));

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: '#131722' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: 'rgba(197, 203, 206, 0.8)',
      },
      timeScale: {
        borderColor: 'rgba(197, 203, 206, 0.8)',
        timeVisible: true,
      },
    });

    chartRef.current = chart;

    // Candlestick Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#ef5350',
      downColor: '#26a69a',
      borderDownColor: '#26a69a',
      borderUpColor: '#ef5350',
      wickDownColor: '#26a69a',
      wickUpColor: '#ef5350',
    });
    candleSeriesRef.current = candleSeries;

    // Volume Series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // set as an overlay
      scaleMargins: {
        top: 0.8, // lower 20% of the chart
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    if (data && data.length > 0) {
      const validData = data.filter(d => d.Close != null && d.Open != null);
      const uniqueDates = new Set();
      const candleData = [];
      const volumeData = [];

      validData.forEach(d => {
        if (!uniqueDates.has(d.Date)) {
          uniqueDates.add(d.Date);
          candleData.push({
            time: d.Date,
            open: d.Open,
            high: d.High,
            low: d.Low,
            close: d.Close
          });
          volumeData.push({
            time: d.Date,
            value: d.Volume || 0,
            color: d.Close >= d.Open ? 'rgba(239, 83, 80, 0.5)' : 'rgba(38, 166, 154, 0.5)'
          });
        }
      });

      // Sort by time just in case to strictly enforce ascending order required by lightweight-charts
      candleData.sort((a, b) => new Date(a.time) - new Date(b.time));
      volumeData.sort((a, b) => new Date(a.time) - new Date(b.time));

      if (candleData.length > 0) {
        candleSeries.setData(candleData);
        volumeSeries.setData(volumeData);
      }
    }

    // Handlers
    chart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
      if (onTimeRangeChange && timeRange) {
        onTimeRangeChange(ticker, timeRange);
      }
    });

    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMove) {
        onCrosshairMove(ticker, param);
      }
    });

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  return (
    <div style={{ marginBottom: '20px' }}>
      <h3 style={{ color: 'white', margin: '0 0 10px 0' }}>{name} ({ticker})</h3>
      <div ref={chartContainerRef} style={{ width: '100%', height: '350px' }} />
    </div>
  );
});

export default StockChart;
