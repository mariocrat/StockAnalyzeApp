import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import StockChart from './components/StockChart';
import './App.css';

const API_BASE = 'http://localhost:8000';

// ── Helpers ───────────────────────────────────────────────────────────────
const fmt8 = (d) => d.toISOString().split('T')[0].replace(/-/g, '');

function periodDates(p) {
  const end = new Date();
  const start = new Date();
  if (p === '1D') start.setDate(end.getDate() - 1);
  else if (p === '1W') start.setDate(end.getDate() - 7);
  else if (p === '1M') start.setMonth(end.getMonth() - 1);
  else if (p === '1Y') start.setFullYear(end.getFullYear() - 1);
  return { start: fmt8(start), end: fmt8(end) };
}

// ── Indicator definitions ─────────────────────────────────────────────────
const IND_DEFS = [
  { key: 'MA_5',   label: 'MA 5',   color: '#e040fb' },
  { key: 'MA_10',  label: 'MA 10',  color: '#ff9800' },
  { key: 'MA_20',  label: 'MA 20',  color: '#f6c90e' },
  { key: 'MA_60',  label: 'MA 60',  color: '#4fc3f7' },
  { key: 'MA_120', label: 'MA 120', color: '#ff7043' },
  { key: 'BB',     label: 'BB',     color: '#b39ddb' },
  { key: 'RSI',    label: 'RSI',    color: '#26a69a' },
];

const CHART_PERIODS  = ['1M', '3M', '6M', '1Y'];
const CANDLE_PERIODS = [
  { label: '일봉', value: 'D' },
  { label: '주봉', value: 'W' },
  { label: '월봉', value: 'M' },
];
const THEME_PERIODS = ['1D', '1W', '1M', '1Y'];

// ── App ───────────────────────────────────────────────────────────────────
export default function App() {
  // ── Theme state ──────────────────────────────────────────────────────
  const [themes,          setThemes]         = useState([]);
  const [themesLoading,   setThemesLoading]  = useState(true);
  const [themePeriod,     setThemePeriod]    = useState('1D');
  const [customStart,     setCustomStart]    = useState('');
  const [customEnd,       setCustomEnd]      = useState('');
  const [showCustom,      setShowCustom]     = useState(false);
  const [activeTheme,     setActiveTheme]    = useState(null);
  const [selectedStocks,  setSelectedStocks] = useState([]);

  // ── Stock data ───────────────────────────────────────────────────────
  const [stockData,     setStockData]     = useState({});
  const [loadingStocks, setLoadingStocks] = useState({});

  // ── Search ───────────────────────────────────────────────────────────
  const [searchQuery,   setSearchQuery]   = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showResults,   setShowResults]   = useState(false);

  // ── Global chart controls (lifted state) ─────────────────────────────
  const [chartPeriod,  setChartPeriod]  = useState('3M');
  const [candlePeriod, setCandlePeriod] = useState('D');  // 일봉/주봉/월봉
  const [scaleMode,    setScaleMode]    = useState('linear'); // linear | log
  const [activeInds,   setActiveInds]   = useState({
    MA_5: false, MA_10: false, MA_20: true, MA_60: false, MA_120: false, BB: false, RSI: false,
  });
  const [bbPeriod,     setBbPeriod]     = useState(20);
  const [bbMultiplier, setBbMultiplier] = useState(2);

  const chartRefs = useRef({});

  // ── Fetch themes ─────────────────────────────────────────────────────
  const fetchThemes = useCallback(async (period, cStart, cEnd) => {
    setThemesLoading(true);
    try {
      let data;
      if (period === '1D') {
        const { start, end } = periodDates('1D');
        const res = await axios.get(`${API_BASE}/api/themes`, { params: { start_date: start, end_date: end } });
        data = res.data;
      } else if (period === 'custom') {
        if (!cStart || !cEnd) { setThemesLoading(false); return; }
        const res = await axios.get(`${API_BASE}/api/themes_historical`, {
          params: { start_date: cStart.replace(/-/g, ''), end_date: cEnd.replace(/-/g, '') }
        });
        data = res.data;
      } else {
        const { start, end } = periodDates(period);
        const res = await axios.get(`${API_BASE}/api/themes_historical`, { params: { start_date: start, end_date: end } });
        data = res.data;
      }
      setThemes(data || []);
    } catch (err) {
      console.error('[fetchThemes]', err);
    } finally {
      setThemesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchThemes('1D', '', '');
  }, [fetchThemes]);

  const handleThemePeriodChange = (p) => {
    setThemePeriod(p);
    setShowCustom(p === 'custom');
    if (p !== 'custom') fetchThemes(p, '', '');
  };

  const handleCustomApply = () => {
    fetchThemes('custom', customStart, customEnd);
  };

  // ── Theme click ───────────────────────────────────────────────────────
  const handleThemeClick = useCallback(async (e, theme) => {
    e.preventDefault(); e.stopPropagation();
    setActiveTheme(theme.Theme);

    const rawTickers = theme.Tickers || [];
    const tickers = rawTickers.map(t =>
      typeof t === 'string' ? { ticker: t, name: t, return_rate: null } : t
    );

    // Default-select top-2 by return (already sorted by backend)
    const defaultSelected = tickers.slice(0, 2);
    setSelectedStocks(defaultSelected);
    for (const s of defaultSelected) await fetchStockData(s.ticker, s.name);
  }, []); // eslint-disable-line

  // ── Stock data fetch ──────────────────────────────────────────────────
  const fetchStockData = useCallback(async (ticker, name) => {
    if (stockData[ticker]) return; // already loaded
    setLoadingStocks(prev => ({ ...prev, [ticker]: true }));
    try {
      const today = new Date();
      const start = new Date();
      start.setFullYear(today.getFullYear() - 1);
      const res = await axios.get(`${API_BASE}/api/stock/${ticker}`, {
        params: { start_date: fmt8(start), end_date: fmt8(today) }
      });
      setStockData(prev => ({ ...prev, [ticker]: res.data?.data || [] }));
    } catch (err) {
      console.error(`[fetchStockData] ${ticker}`, err);
    } finally {
      setLoadingStocks(prev => ({ ...prev, [ticker]: false }));
    }
  }, [stockData]);

  // ── Stock chip toggle ─────────────────────────────────────────────────
  const handleChipToggle = useCallback(async (e, stock) => {
    e.preventDefault(); e.stopPropagation();
    const { ticker, name } = stock;
    const isSelected = selectedStocks.some(s => s.ticker === ticker);
    if (isSelected) {
      setSelectedStocks(prev => prev.filter(s => s.ticker !== ticker));
    } else {
      setSelectedStocks(prev => [...prev, stock]);
      await fetchStockData(ticker, name);
    }
  }, [selectedStocks, fetchStockData]);

  // ── Global indicator toggle ───────────────────────────────────────────
  const toggleInd = useCallback((key) => {
    setActiveInds(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // ── Search ────────────────────────────────────────────────────────────
  const handleSearch = useCallback(async (q) => {
    setSearchQuery(q);
    if (!q.trim()) { setSearchResults([]); setShowResults(false); return; }
    try {
      const res = await axios.get(`${API_BASE}/api/search`, { params: { q: q.trim() } });
      setSearchResults(res.data || []);
      setShowResults(true);
    } catch {
      setSearchResults([]);
    }
  }, []);

  const handleSearchSelect = useCallback(async (result) => {
    const ticker = result.Ticker || result.ticker;
    const name   = result.Name   || result.name || ticker;
    setSearchQuery(`${name} (${ticker})`);
    setShowResults(false);
    if (!selectedStocks.some(s => s.ticker === ticker)) {
      setSelectedStocks(prev => [...prev, { ticker, name }]);
    }
    await fetchStockData(ticker, name);
  }, [selectedStocks, fetchStockData]);

  // ── Time-range sync across charts ────────────────────────────────────
  const handleTimeRangeChange = useCallback((sourceTicker, range) => {
    Object.entries(chartRefs.current).forEach(([t, ref]) => {
      if (t !== sourceTicker && ref?.setVisibleTimeRange) {
        try { ref.setVisibleTimeRange(range); } catch (_) {}
      }
    });
  }, []);

  // ── Render current theme's ticker list ───────────────────────────────
  const activeThemeObj = themes.find(t => t.Theme === activeTheme);
  const themeTickers = (activeThemeObj?.Tickers || [])
    .map(t => typeof t === 'string' ? { ticker: t, name: t, return_rate: null } : t)
    .sort((a, b) => {
      if (a.return_rate == null && b.return_rate == null) return 0;
      if (a.return_rate == null) return 1;
      if (b.return_rate == null) return -1;
      return b.return_rate - a.return_rate;
    });

  // ── Inline styles for controls ────────────────────────────────────────
  const separatorStyle = {
    width: '1px', height: '20px', background: '#2a2e39', margin: '0 4px',
  };

  return (
    <div className="app-container">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div className="sidebar">
        <h2 className="sidebar-title">AlphaMate</h2>

        {/* Search */}
        <div className="search-box">
          <input
            placeholder="종목 검색 (이름, 초성, 코드)"
            value={searchQuery}
            onChange={e => handleSearch(e.target.value)}
            onFocus={() => searchResults.length && setShowResults(true)}
            onBlur={() => setTimeout(() => setShowResults(false), 200)}
          />
          {showResults && searchResults.length > 0 && (
            <ul className="search-results">
              {searchResults.map(r => {
                const ticker = r.Ticker || r.ticker;
                const name   = r.Name   || r.name || ticker;
                return (
                  <li key={ticker} onMouseDown={() => handleSearchSelect(r)}>
                    <span>{name}</span>
                    <span style={{ color: '#555', fontSize: '11px' }}>{ticker}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Theme section header */}
        <div className="section-header">
          <h3 className="section-title">상승률 상위 테마</h3>
        </div>

        {/* Theme period tabs */}
        <div style={{ marginBottom: '10px' }}>
          <div className="theme-period-tabs">
            {THEME_PERIODS.map(p => (
              <button
                key={p}
                className={themePeriod === p ? 'active' : ''}
                onClick={() => handleThemePeriodChange(p)}
              >{p}</button>
            ))}
            <button
              className={themePeriod === 'custom' ? 'active' : ''}
              onClick={() => handleThemePeriodChange('custom')}
            >직접입력</button>
          </div>

          {/* Custom date range */}
          {showCustom && (
            <div className="custom-range-row" style={{ marginTop: '8px' }}>
              <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)} />
              <span style={{ color: '#555' }}>~</span>
              <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)} />
              <button onClick={handleCustomApply}>조회</button>
            </div>
          )}
        </div>

        {/* Theme list */}
        {themesLoading ? (
          <div className="themes-loading">
            {themePeriod === '1D' ? '로딩중…' : '수익률 계산 중… (최대 20초)'}
          </div>
        ) : (
          themes.map((theme, i) => {
            const ret = theme['Avg Return (%)'] ?? theme['Return'] ?? 0;
            const isActive = activeTheme === theme.Theme;
            return (
              <div
                key={theme.Theme + i}
                className={`theme-item ${isActive ? 'active' : ''}`}
                onClick={(e) => handleThemeClick(e, theme)}
              >
                <span className="theme-name">{theme.Theme}</span>
                <span className={ret >= 0 ? 'positive' : 'negative'}>
                  {ret >= 0 ? '+' : ''}{typeof ret === 'number' ? ret.toFixed(2) : ret}%
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <div className="main-content">

        {/* Stock chip selector */}
        {themeTickers.length > 0 && (
          <div className="theme-stocks-selector">
            <h3 style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#aaa', display: 'flex', justifyContent: 'space-between' }}>
              <span>{activeTheme}</span>
              <span style={{ color: '#555', fontSize: '11px', fontWeight: 400 }}>{themeTickers.length}개 종목</span>
            </h3>
            {/* List UI with return_rate */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxHeight: '220px', overflowY: 'auto' }}>
              {themeTickers.map((stock) => {
                const { ticker, name, return_rate } = stock;
                const isSel     = selectedStocks.some(s => s.ticker === ticker);
                const isLoading = loadingStocks[ticker];
                const retColor  = return_rate == null ? '#555' : return_rate >= 0 ? '#ef5350' : '#26a69a';
                const retLabel  = return_rate == null ? '' : `${return_rate >= 0 ? '+' : ''}${return_rate.toFixed(2)}%`;
                return (
                  <div key={ticker}
                    onClick={(e) => handleChipToggle(e, stock)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '6px 10px', borderRadius: '5px', cursor: 'pointer',
                      background: isSel ? '#1a2a4a' : 'transparent',
                      border: `1px solid ${isSel ? '#2962ff' : '#1e222d'}`,
                      transition: 'all 0.15s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isSel ? '#2962ff' : '#2a2e39', flexShrink: 0 }} />
                      <span style={{ fontSize: '13px', color: isSel ? '#fff' : '#b0b3c0' }}>
                        {isLoading ? '⏳ ' : ''}{name}
                      </span>
                    </div>
                    {retLabel && (
                      <span style={{ fontSize: '12px', fontWeight: 700, color: retColor, marginLeft: '8px', flexShrink: 0 }}>
                        {retLabel}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {selectedStocks.length > 0 && (
          <div className="global-controls">

            {/* 봉 선택 */}
            <div className="controls-group">
              <span className="controls-label">봉</span>
              {CANDLE_PERIODS.map(p => (
                <button key={p.value}
                  className={`ctrl-btn ${candlePeriod === p.value ? 'active' : ''}`}
                  onClick={() => setCandlePeriod(p.value)}
                >{p.label}</button>
              ))}
            </div>

            <div style={separatorStyle} />

            {/* 기간 */}
            <div className="controls-group">
              <span className="controls-label">기간</span>
              {CHART_PERIODS.map(p => (
                <button key={p}
                  className={`ctrl-btn ${chartPeriod === p ? 'active' : ''}`}
                  onClick={() => setChartPeriod(p)}
                >{p}</button>
              ))}
            </div>

            <div style={separatorStyle} />

            {/* 스케일 */}
            <div className="controls-group">
              <span className="controls-label">스케일</span>
              {[{l:'선형',v:'linear'},{l:'로그',v:'log'}].map(s => (
                <button key={s.v}
                  className={`ctrl-btn ${scaleMode === s.v ? 'active' : ''}`}
                  onClick={() => setScaleMode(s.v)}
                >{s.l}</button>
              ))}
            </div>

            <div style={separatorStyle} />

            {/* 지표 */}
            <div className="controls-group">
              <span className="controls-label">지표</span>
              {IND_DEFS.map(ind => {
                const isOn = activeInds[ind.key] ?? false;
                return (
                  <label key={ind.key} className="ind-toggle-label"
                    onClick={(e) => { e.preventDefault(); toggleInd(ind.key); }}>
                    <div className="toggle-pill" style={{ background: isOn ? ind.color : '#2a2e39' }}>
                      <div className="toggle-knob" style={{ left: isOn ? '17px' : '3px' }} />
                    </div>
                    <span style={{ color: isOn ? ind.color : '#555', fontSize: '12px' }}>{ind.label}</span>
                  </label>
                );
              })}
            </div>

            {/* BB params */}
            {activeInds.BB && (
              <>
                <div style={separatorStyle} />
                <div className="controls-group bb-param-group">
                  <span className="controls-label">BB</span>
                  <label>기간<input type="number" min={2} max={200} value={bbPeriod}
                    onChange={e => setBbPeriod(Math.max(2, parseInt(e.target.value) || 20))}
                  /></label>
                  <label>배수<input type="number" min={0.5} max={5} step={0.5} value={bbMultiplier}
                    onChange={e => setBbMultiplier(Math.max(0.5, parseFloat(e.target.value) || 2))}
                  /></label>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Charts ──────────────────────────────────────────────────── */}
        <div className="charts-container">
          {selectedStocks.map(s => {
            const data = stockData[s.ticker];
            if (!data) {
              return (
                <div key={s.ticker} style={{
                  height: '80px', background: '#131722', borderRadius: '8px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#555', fontSize: '13px', marginBottom: '4px',
                }}>
                  {loadingStocks[s.ticker] ? `${s.name} 데이터 로딩 중...` : `${s.name} No data`}
                </div>
              );
            }
            return (
              <StockChart
                key={s.ticker}
                ref={el => { chartRefs.current[s.ticker] = el; }}
                ticker={s.ticker}
                name={s.name}
                data={data}
                chartPeriod={chartPeriod}
                candlePeriod={candlePeriod}
                scaleMode={scaleMode}
                activeInds={activeInds}
                bbPeriod={bbPeriod}
                bbMultiplier={bbMultiplier}
                onTimeRangeChange={handleTimeRangeChange}
              />
            );
          })}
        </div>

        {/* Empty state */}
        {selectedStocks.length === 0 && (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', color: '#333',
          }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>📈</div>
            <div style={{ fontSize: '14px' }}>좌측에서 테마를 선택하거나 종목을 검색하세요</div>
          </div>
        )}
      </div>
    </div>
  );
}
