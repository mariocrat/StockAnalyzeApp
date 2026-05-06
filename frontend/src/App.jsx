import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import StockChart from './components/StockChart';
import './App.css';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [themes, setThemes] = useState([]);
  const [selectedStocks, setSelectedStocks] = useState([]);
  const [stockData, setStockData] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  
  const chartRefs = useRef({});

  // Fetch initial themes
  useEffect(() => {
    const fetchThemes = async () => {
      try {
        const today = new Date();
        const start = new Date();
        start.setDate(today.getDate() - 7); // 1W
        
        const formatDt = (d) => d.toISOString().split('T')[0].replace(/-/g, '');
        
        const res = await axios.get(`${API_BASE}/themes`, {
          params: { start_date: formatDt(start), end_date: formatDt(today) }
        });
        setThemes(res.data);
      } catch (e) {
        console.error(e);
      }
    };
    fetchThemes();
  }, []);

  useEffect(() => {
    const delayDebounceFn = setTimeout(async () => {
      if (searchQuery.length >= 1) {
        try {
          const res = await axios.get(`${API_BASE}/search`, { params: { q: searchQuery } });
          setSearchResults(res.data);
        } catch (e) {
          console.error(e);
        }
      } else {
        setSearchResults([]);
      }
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery]);

  const handleSearch = (e) => {
    setSearchQuery(e.target.value);
  };

  const handleStockSelect = async (ticker, name) => {
    if (!selectedStocks.find(s => s.ticker === ticker)) {
      setSelectedStocks(prev => [...prev, { ticker, name }]);
      
      // Fetch stock data
      const today = new Date();
      const start = new Date();
      start.setDate(today.getDate() - 7);
      const formatDt = (d) => d.toISOString().split('T')[0].replace(/-/g, '');
      
      const res = await axios.get(`${API_BASE}/stock/${ticker}`, {
        params: { start_date: formatDt(start), end_date: formatDt(today) }
      });
      
      setStockData(prev => ({ ...prev, [ticker]: res.data.data }));
    }
  };

  const removeStock = (ticker) => {
    setSelectedStocks(prev => prev.filter(s => s.ticker !== ticker));
    setStockData(prev => {
      const newData = { ...prev };
      delete newData[ticker];
      return newData;
    });
  };

  const handleTimeRangeChange = (sourceTicker, timeRange) => {
    // Sync all other charts
    Object.keys(chartRefs.current).forEach(ticker => {
      if (ticker !== sourceTicker && chartRefs.current[ticker]) {
        chartRefs.current[ticker].setVisibleTimeRange(timeRange);
      }
    });
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <h2>Stock Analysis</h2>
        
        <div className="search-box">
          <input 
            type="text" 
            placeholder="Search stock or initial (e.g. ㅅㅅㅈ)" 
            value={searchQuery}
            onChange={handleSearch}
          />
          {searchResults.length > 0 && (
            <ul className="search-results">
              {searchResults.map(res => (
                <li key={res.Ticker} onClick={() => handleStockSelect(res.Ticker, res.Name)}>
                  {res.Name} <small>({res.Themes.join(', ')})</small>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="themes-list">
          <h3>Top Themes (1W)</h3>
          {themes.slice(0, 20).map((t, i) => (
            <div key={i} className="theme-item" onClick={() => {
              // Add top 3 stocks of this theme
              t.Tickers.slice(0, 3).forEach(stockObj => handleStockSelect(stockObj.ticker, stockObj.name));
            }}>
              <span>{t.Theme}</span>
              <span className={t['Avg Return (%)'] > 0 ? 'positive' : 'negative'}>
                {t['Avg Return (%)']}%
              </span>
            </div>
          ))}
        </div>
      </div>
      
      <div className="main-content">
        <div className="selected-stocks-pills">
          {selectedStocks.map(s => (
            <span key={s.ticker} className="pill" onClick={() => removeStock(s.ticker)}>
              {s.name} &times;
            </span>
          ))}
        </div>

        <div className="charts-container">
          {selectedStocks.map(s => (
            <StockChart
              key={s.ticker}
              ref={el => chartRefs.current[s.ticker] = el}
              ticker={s.ticker}
              name={s.name}
              data={stockData[s.ticker]}
              onTimeRangeChange={handleTimeRangeChange}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
