import { lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { ArrowLeft, ChevronDown, ChevronUp, UserRound } from 'lucide-react';
import './App.css';
import appIcon from './assets/app-icon.png';
import { getAdMobRuntimeStatus, removeAppBanner, showAppBanner, showChartDetailInterstitial, showResumeInterstitial } from './mobile/admob';
import { shouldShowBannerAd, shouldShowChartDetailInterstitial, shouldShowResumeInterstitial } from './mobile/admobPolicy';
import { reportClientEvent } from './utils/clientEventLog';
import { nextRootBackAction, requestNestedBack } from './utils/appNavigation';
import { MARKET_DOWN, MARKET_FLAT, MARKET_UP } from './theme/marketColors';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8002';
const APP_NAME = import.meta.env.VITE_APP_NAME || 'AlphaMate';
const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const DEV_TOOLS_ENABLED = APP_ENV !== 'production' && import.meta.env.VITE_ENABLE_DEV_TOOLS !== 'false';
const DEV_ACCESS_PLAN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_ACCESS_PLAN || 'free' : 'free';
const DEV_AUTH_TOKEN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_AUTH_TOKEN || 'dev-token' : '';
const DEV_PRO_ENTITLEMENT_TOKEN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_PRO_ENTITLEMENT_TOKEN || 'dev-pro-entitlement' : '';
const DEV_ENTITLEMENT_TOKEN = DEV_ACCESS_PLAN === 'pro' ? DEV_PRO_ENTITLEMENT_TOKEN : '';
const AUTH_STORAGE_KEY = 'alphamate.devAuth.v1';
const StockChart = lazy(() => import('./components/StockChart'));
const TradingJournal = lazy(() => import('./components/TradingJournal'));

// ── Helpers ───────────────────────────────────────────────────────────────
const fmt8 = (d) => d.toISOString().split('T')[0].replace(/-/g, '');

function loadStoredAuthSession() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
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
  { key: 'MACD',   label: 'MACD',   color: '#2962ff' },
  { key: 'STOCH',  label: 'Stoch',  color: '#ff5252' },
  { key: 'ICHI',   label: '일목균형표', color: '#81c784' },
];

const CHART_PERIODS  = ['1M', '3M', '6M', '1Y'];
const CANDLE_PERIODS = [
  { label: '일봉', value: 'D' },
  { label: '주봉', value: 'W' },
  { label: '월봉', value: 'M' },
  { label: '년봉', value: 'Y' },
];
const THEME_PERIODS = ['1D', '1W', '1M', '1Y'];
const SPLASH_MIN_MS = 1150;
const SPLASH_MAX_MS = 3500;
const SPLASH_FADE_MS = 280;
const THEME_REQUEST_TIMEOUT_MS = 20_000;
const THEME_RETRY_DELAY_MS = 15_000;

function AppSplash({ exiting }) {
  return (
    <div className={exiting ? "app-splash app-splash-exit" : "app-splash"} aria-hidden="true">
      <img className="app-splash-logo" src={appIcon} alt="" />
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────
export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [splashExiting, setSplashExiting] = useState(false);
  const [adPlan, setAdPlan] = useState(DEV_ACCESS_PLAN === 'pro' ? 'pro' : 'free');
  const [bannerReserved, setBannerReserved] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const backgroundedAtRef = useRef(0);
  const lastResumeInterstitialAtRef = useRef(0);
  const resumeInterstitialInFlightRef = useRef(false);
  const chartDetailOpenCountRef = useRef(0);
  const splashStartedAtRef = useRef(null);
  const [activeView, setActiveView] = useState(() => {
    try {
      return new URLSearchParams(window.location.search).get('view') === 'journal' ? 'journal' : 'themes';
    } catch {
      return 'themes';
    }
  });
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);

  useEffect(() => {
    document.title = APP_NAME;
  }, []);

  const reportAppClientEvent = useCallback((eventType, error, details = {}) => {
    const session = loadStoredAuthSession();
    reportClientEvent({
      apiBase: API_BASE,
      sessionToken: session?.session_token || '',
      eventType,
      level: 'warning',
      message: error?.message || `${eventType} failed.`,
      path: '/themes',
      details: {
        ...details,
        errorName: error?.name || error?.constructor?.name || 'Error',
      },
    });
  }, []);
  const reportAdClientEvent = useCallback((eventType, error, details = {}) => {
    const session = loadStoredAuthSession();
    reportClientEvent({
      apiBase: API_BASE,
      sessionToken: session?.session_token || '',
      eventType,
      level: 'warning',
      message: error?.message || `${eventType} failed.`,
      path: '/ads',
      details: {
        ...details,
        errorName: error?.name || error?.constructor?.name || 'Error',
      },
    });
  }, []);

  const refreshAdPlan = useCallback(async () => {
    if (DEV_ACCESS_PLAN === 'pro') {
      setAdPlan('pro');
      return;
    }
    const session = loadStoredAuthSession();
    const token = session?.session_token || DEV_AUTH_TOKEN;
    if (!token) {
      setAdPlan('free');
      return;
    }
    try {
      const res = await axios.get(`${API_BASE}/api/journal/entitlements`, {
        params: { entitlement_token: DEV_ENTITLEMENT_TOKEN },
        headers: { Authorization: `Bearer ${token}` },
      });
      setAdPlan(res.data?.plan === 'pro' ? 'pro' : 'free');
    } catch {
      setAdPlan('free');
    }
  }, []);

  const handleEntitlementsChange = useCallback((wallet) => {
    if (!wallet && DEV_ACCESS_PLAN === 'pro') {
      setAdPlan('pro');
      return;
    }
    if (!wallet) return;
    setAdPlan(wallet?.plan === 'pro' ? 'pro' : 'free');
  }, []);

  useEffect(() => {
    refreshAdPlan();
    window.addEventListener('storage', refreshAdPlan);
    return () => {
      window.removeEventListener('storage', refreshAdPlan);
    };
  }, [refreshAdPlan]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      const nowMs = Date.now();
      if (document.visibilityState === 'hidden') {
        backgroundedAtRef.current = nowMs;
        return;
      }
      if (
        document.visibilityState === 'visible'
        && !resumeInterstitialInFlightRef.current
        && shouldShowResumeInterstitial({
          plan: adPlan,
          backgroundedAtMs: backgroundedAtRef.current,
          nowMs,
          lastShownAtMs: lastResumeInterstitialAtRef.current,
        })
      ) {
        resumeInterstitialInFlightRef.current = true;
        lastResumeInterstitialAtRef.current = nowMs;
        showResumeInterstitial()
          .catch((err) => {
            reportAdClientEvent('ad_resume_interstitial_failed', err, {
              placement: 'resume',
              plan: adPlan,
            });
          })
          .finally(() => {
            resumeInterstitialInFlightRef.current = false;
          });
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [adPlan, reportAdClientEvent]);

  useEffect(() => {
    const status = getAdMobRuntimeStatus();
    const shouldShow = !showSplash && shouldShowBannerAd({ plan: adPlan, native: status.native });
    if (!shouldShow) {
      setBannerReserved(false);
      removeAppBanner().catch((err) => {
        reportAdClientEvent('ad_banner_remove_failed', err, {
          placement: 'bottom_banner',
          plan: adPlan,
          native: status.native,
          reason: 'suppressed',
        });
      });
      return;
    }

    showAppBanner()
      .then((result) => {
        setBannerReserved(Boolean(result?.shown));
      })
      .catch((err) => {
        reportAdClientEvent('ad_banner_show_failed', err, {
          placement: 'bottom_banner',
          plan: adPlan,
          native: status.native,
          platform: status.platform,
        });
        setBannerReserved(false);
      });

    return () => {
      setBannerReserved(false);
      removeAppBanner().catch((err) => {
        reportAdClientEvent('ad_banner_remove_failed', err, {
          placement: 'bottom_banner',
          plan: adPlan,
          native: status.native,
          reason: 'cleanup',
        });
      });
    };
  }, [adPlan, showSplash, reportAdClientEvent]);

  // ── Theme state ──────────────────────────────────────────────────────
  const [themes,          setThemes]         = useState([]);
  const [themesLoading,   setThemesLoading]  = useState(true);
  const [themeError,      setThemeError]     = useState('');
  const [themeRetryRequest, setThemeRetryRequest] = useState(null);
  const [themePeriod,     setThemePeriod]    = useState('1D');
  const [themeBasisText,  setThemeBasisText] = useState('장마감 기준');
  const [themesExpanded,  setThemesExpanded] = useState(true);
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
  const [visibleCandleCount, setVisibleCandleCount] = useState('');
  const [candleCountApplySeq, setCandleCountApplySeq] = useState(0);
  const [scaleMode,    setScaleMode]    = useState('linear'); // linear | log
  const [activeInds,   setActiveInds]   = useState({
    MA_5: false, MA_10: false, MA_20: false, MA_60: false, MA_120: false, BB: false, RSI: false, MACD: false, STOCH: false, ICHI: false
  });
  const [chartPaneLayouts, setChartPaneLayouts] = useState({});
  const [chartDrawings, setChartDrawings] = useState({});
  const [bbPeriod, setBbPeriod] = useState(20);
  const [bbMultiplier, setBbMultiplier] = useState(2.0);

  const chartRefs = useRef({});
  const themeRequestSeq = useRef(0);
  const themeAbortControllerRef = useRef(null);
  const searchRequestSeq = useRef(0);
  const searchCacheRef = useRef({});
  const suppressNextSearchRef = useRef(false);
  const mainContentRef = useRef(null);
  const themeStocksRef = useRef(null);

  const changeActiveView = useCallback((nextView) => {
    setActiveView(nextView);
    if (nextView !== 'journal') setAccountPanelOpen(false);
    try {
      const url = new URL(window.location.href);
      if (nextView === 'journal') url.searchParams.set('view', 'journal');
      else url.searchParams.delete('view');
      window.history.replaceState({}, '', url.toString());
    } catch {
      // The in-memory view still changes when URL APIs are unavailable.
    }
  }, []);

  const paneLayoutKey = ['RSI', 'MACD', 'STOCH'].filter(key => activeInds[key]).join('|') || 'base';
  const handlePaneLayoutChange = useCallback((key, factors) => {
    setChartPaneLayouts(previous => {
      const current = previous[key];
      const unchanged = Array.isArray(current)
        && current.length === factors.length
        && current.every((value, index) => Math.abs(value - factors[index]) < 0.001);
      return unchanged ? previous : { ...previous, [key]: factors };
    });
  }, []);
  const handleChartDrawingsChange = useCallback((ticker, drawings) => {
    setChartDrawings(previous => ({ ...previous, [ticker]: drawings }));
  }, []);

  const handleAppBack = useCallback(() => {
    if (requestNestedBack()) return;

    const action = nextRootBackAction({
      activeView,
      hasThemeSelection: Boolean(activeTheme || selectedStocks.length),
    });
    if (action === 'themes') {
      changeActiveView('themes');
      return;
    }
    if (action === 'clear-theme-selection') {
      setActiveTheme(null);
      setSelectedStocks([]);
      return;
    }
    setShowExitConfirm(true);
  }, [activeTheme, activeView, changeActiveView, selectedStocks.length]);

  const exitApplication = useCallback(async () => {
    setShowExitConfirm(false);
    if (Capacitor.isNativePlatform()) {
      await CapacitorApp.exitApp();
      return;
    }
    if (window.history.length > 1) window.history.back();
  }, []);

  useEffect(() => {
    let listener;
    let mounted = true;
    CapacitorApp.addListener('backButton', () => handleAppBack())
      .then(handle => {
        if (mounted) listener = handle;
        else handle.remove();
      })
      .catch(() => {});
    return () => {
      mounted = false;
      listener?.remove();
    };
  }, [handleAppBack]);

  useEffect(() => {
    if (!showSplash) return undefined;

    if (splashStartedAtRef.current === null) {
      splashStartedAtRef.current = Date.now();
    }

    const elapsedMs = Date.now() - splashStartedAtRef.current;
    const initialDataReady = !themesLoading || Boolean(themeError);
    const waitMs = initialDataReady
      ? Math.max(0, SPLASH_MIN_MS - elapsedMs)
      : Math.max(0, SPLASH_MAX_MS - elapsedMs);
    let hideTimer;

    const exitTimer = window.setTimeout(() => {
      setSplashExiting(true);
      hideTimer = window.setTimeout(() => {
        setShowSplash(false);
      }, SPLASH_FADE_MS);
    }, waitMs);

    return () => {
      window.clearTimeout(exitTimer);
      if (hideTimer) window.clearTimeout(hideTimer);
    };
  }, [showSplash, themesLoading, themeError]);

  // ── Fetch themes ─────────────────────────────────────────────────────
  const fetchThemes = useCallback(async (period, { preserveData = false } = {}) => {
    themeAbortControllerRef.current?.abort();
    const controller = new AbortController();
    themeAbortControllerRef.current = controller;
    const requestId = themeRequestSeq.current + 1;
    themeRequestSeq.current = requestId;
    setThemesLoading(!preserveData);
    setThemeError('');
    setThemeRetryRequest(null);
    if (!preserveData) setThemes([]);
    try {
      const res = await axios.get(`${API_BASE}/api/themes`, {
        params: { period },
        timeout: THEME_REQUEST_TIMEOUT_MS,
        signal: controller.signal,
      });
      const data = res.data;
      if (themeRequestSeq.current === requestId) {
        setThemes(data || []);
        const endDate = data?.[0]?.['End Date'];
        const isRefreshing = data?.[0]?.['Data Status'] === 'updating';
        if (endDate && /^\d{8}$/.test(String(endDate))) {
          setThemeBasisText(`${String(endDate).slice(0, 4)}-${String(endDate).slice(4, 6)}-${String(endDate).slice(6, 8)} 장마감 기준${isRefreshing ? ' · 최신 종가 반영 중' : ''}`);
        } else {
          setThemeBasisText('장마감 기준');
        }
        if (isRefreshing) setThemeRetryRequest({ period, requestId });
      }
    } catch (err) {
      if (axios.isCancel(err)) return;
      reportAppClientEvent('theme_fetch_failed', err, { period });
      if (themeRequestSeq.current === requestId) {
        const isPreparing = err.response?.status === 503;
        const isTimeout = err.code === 'ECONNABORTED';
        const detail = err.response?.data?.detail;
        setThemeError(
          isPreparing
            ? detail || '최신 기간 수익률을 업데이트 중입니다. 잠시 후 자동으로 다시 확인합니다.'
            : isTimeout
              ? '서버 응답이 늦어지고 있습니다. 잠시 후 자동으로 다시 확인합니다.'
              : '테마 상승률을 불러오지 못했습니다. 잠시 후 자동으로 다시 확인합니다.',
        );
        setThemeRetryRequest({ period, requestId });
      }
    } finally {
      if (themeAbortControllerRef.current === controller) {
        themeAbortControllerRef.current = null;
      }
      if (themeRequestSeq.current === requestId) setThemesLoading(false);
    }
  }, [reportAppClientEvent]);

  useEffect(() => {
    if (!themeRetryRequest || activeView !== 'themes') return undefined;
    const timer = window.setTimeout(() => {
      if (themeRequestSeq.current === themeRetryRequest.requestId) {
        fetchThemes(themeRetryRequest.period, { preserveData: true });
      }
    }, THEME_RETRY_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [activeView, fetchThemes, themeRetryRequest]);

  useEffect(() => {
    if (activeView === 'themes') {
      fetchThemes(themePeriod);
    }
  }, [activeView, themePeriod, fetchThemes]);

  useEffect(() => {
    if (activeView === 'themes') return;
    themeRequestSeq.current += 1;
    themeAbortControllerRef.current?.abort();
    themeAbortControllerRef.current = null;
    setThemeRetryRequest(null);
    setThemesLoading(false);
  }, [activeView]);

  const handleThemePeriodChange = (p) => {
    setThemes([]);
    setThemePeriod(p);
  };

  // Reset theme and selected stocks when period changes
  useEffect(() => {
    setActiveTheme(null);
    setSelectedStocks([]);
  }, [themePeriod]);

  // ── Stock data fetch ──────────────────────────────────────────────────
  const fetchStockData = useCallback(async (ticker, name, currentCandlePeriod) => {
    // Determine interval parameter
    const intervalMap = { 'D': '1d', 'W': '1w', 'M': '1m', 'Y': '1y', '1D': '1d', '1W': '1w', '1M': '1m', '1Y': '1y' };
    const interval = intervalMap[currentCandlePeriod || candlePeriod] || '1d';
    const cacheKey = `${ticker}_${interval}`;

    if (stockData[cacheKey]) return; // already loaded for this interval
    setLoadingStocks(prev => ({ ...prev, [ticker]: true }));
    try {
      // Backend now completely ignores start_date/end_date and returns 10-year data
      // but we still pass dummy values for API requirements
      const today = new Date();
      const res = await axios.get(`${API_BASE}/api/stock/${ticker}`, {
        params: { start_date: '20150101', end_date: fmt8(today), interval }
      });
      setStockData(prev => ({ ...prev, [cacheKey]: res.data?.data || [] }));
    } catch (err) {
      reportAppClientEvent('stock_data_fetch_failed', err, { ticker, interval });
    } finally {
      setLoadingStocks(prev => ({ ...prev, [ticker]: false }));
    }
  }, [stockData, candlePeriod, reportAppClientEvent]);

  // When candlePeriod changes, fetch data for all selected stocks
  useEffect(() => {
    selectedStocks.forEach(s => fetchStockData(s.ticker, s.name, candlePeriod));
  }, [candlePeriod]); // eslint-disable-line

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
    setThemesExpanded(false);
    window.requestAnimationFrame(() => {
      mainContentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      themeStocksRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
    await Promise.all(defaultSelected.map(s => fetchStockData(s.ticker, s.name, candlePeriod)));
  }, [fetchStockData, candlePeriod]);

  // ── Stock chip toggle ─────────────────────────────────────────────────
  const handleChipToggle = useCallback(async (e, stock) => {
    e.preventDefault(); e.stopPropagation();
    const { ticker, name } = stock;
    const isSelected = selectedStocks.some(s => s.ticker === ticker);
    if (isSelected) {
      setSelectedStocks(prev => prev.filter(s => s.ticker !== ticker));
    } else {
      setSelectedStocks(prev => [...prev, stock]);
      await fetchStockData(ticker, name, candlePeriod);
    }
  }, [selectedStocks, fetchStockData, candlePeriod]);

  // ── Global indicator toggle ───────────────────────────────────────────
  const toggleInd = useCallback((key) => {
    setActiveInds(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleCandlePeriodChange = useCallback((nextPeriod) => {
    const normalized = ({ '1D': 'D', '1W': 'W', '1M': 'M', '1Y': 'Y' })[nextPeriod] || nextPeriod;
    setCandlePeriod(normalized);
  }, []);

  const applyVisibleCandleCount = useCallback(() => {
    setCandleCountApplySeq(seq => seq + 1);
  }, []);

  const handleChartPeriodChange = useCallback((nextPeriod) => {
    setVisibleCandleCount('');
    setCandleCountApplySeq(seq => seq + 1);
    setChartPeriod(nextPeriod);
  }, []);

  // ── Search ────────────────────────────────────────────────────────────
  const handleSearch = useCallback((q) => {
    setSearchQuery(q);
  }, []);

  useEffect(() => {
    const query = searchQuery.trim();
    if (suppressNextSearchRef.current) {
      suppressNextSearchRef.current = false;
      return;
    }
    if (!query) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }

    const cacheKey = query.toLowerCase();
    if (searchCacheRef.current[cacheKey]) {
      setSearchResults(searchCacheRef.current[cacheKey]);
      setShowResults(true);
      return;
    }

    const requestId = searchRequestSeq.current + 1;
    searchRequestSeq.current = requestId;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/search`, {
          params: { q: query },
          signal: controller.signal,
        });
        if (searchRequestSeq.current !== requestId) return;
        const results = res.data || [];
        searchCacheRef.current[cacheKey] = results;
        setSearchResults(results);
        setShowResults(true);
      } catch (err) {
        if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
        if (searchRequestSeq.current === requestId) setSearchResults([]);
      }
    }, 180);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery]);

  const handleSearchSelect = useCallback(async (result) => {
    const ticker = result.Ticker || result.ticker;
    const name   = result.Name   || result.name || ticker;
    suppressNextSearchRef.current = true;
    setSearchQuery(`${name} (${ticker})`);
    setShowResults(false);
    if (!selectedStocks.some(s => s.ticker === ticker)) {
      setSelectedStocks(prev => [...prev, { ticker, name }]);
    }
    await fetchStockData(ticker, name, candlePeriod);
  }, [selectedStocks, fetchStockData, candlePeriod]);

  // ── Time-range sync across charts ────────────────────────────────────
  const handleTimeRangeChange = useCallback((sourceTicker, range) => {
    Object.entries(chartRefs.current).forEach(([t, ref]) => {
      if (t !== sourceTicker && ref?.setVisibleTimeRange) {
        try { ref.setVisibleTimeRange(range); } catch {
          // Ignore stale chart refs during mount/unmount transitions.
        }
      }
    });
  }, []);

  const handleChartDetailAd = useCallback(async () => {
    const detailOpenCount = chartDetailOpenCountRef.current + 1;
    chartDetailOpenCountRef.current = detailOpenCount;
    if (!shouldShowChartDetailInterstitial({ plan: adPlan, detailOpenCount })) return;
    try {
      await showChartDetailInterstitial();
    } catch (err) {
      reportAdClientEvent('ad_chart_detail_interstitial_failed', err, {
        placement: 'chart_detail',
        detailOpenCount,
        plan: adPlan,
      });
      // Ad failures should not block chart detail access.
    }
  }, [adPlan, reportAdClientEvent]);

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
    <>
    {showSplash && <AppSplash exiting={splashExiting} />}
    <div className={`${bannerReserved ? 'app-container app-container-mobile-banner' : 'app-container'} ${activeView === 'journal' ? 'journal-view' : 'themes-view'} ${themesExpanded ? 'themes-expanded' : 'themes-collapsed'}`}>
      <header className="mobile-app-bar">
        <button type="button" className="mobile-app-back" onClick={handleAppBack} aria-label="뒤로 가기" title="뒤로 가기">
          <ArrowLeft size={21} aria-hidden="true" />
        </button>
        <strong>{APP_NAME}</strong>
        {activeView === 'journal' ? (
          <button
            type="button"
            className="mobile-app-account"
            onClick={() => setAccountPanelOpen(true)}
            aria-label="계정 및 데이터 관리"
            title="계정 및 데이터 관리"
          >
            <UserRound size={20} aria-hidden="true" />
          </button>
        ) : <span className="mobile-app-bar-spacer" aria-hidden="true" />}
      </header>
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div className="sidebar">
        <div className={activeView === 'themes' ? 'theme-sidebar-fixed' : ''}>
          <h2 className="sidebar-title">{APP_NAME}</h2>

          <div className="app-nav">
            <button className={activeView === 'themes' ? 'active' : ''} onClick={() => changeActiveView('themes')}>테마/차트</button>
            <button className={activeView === 'journal' ? 'active' : ''} onClick={() => changeActiveView('journal')}>매매복기</button>
          </div>

          {/* Search */}
          {activeView === 'themes' && (
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
                  {[...searchResults].sort((a, b) => {
                    const aName = a.Name || a.name || a.Ticker || a.ticker || '';
                    const bName = b.Name || b.name || b.Ticker || b.ticker || '';
                    return aName.localeCompare(bName);
                  }).map(r => {
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
          )}
        </div>

        {activeView === 'themes' && (
          <>

            {/* Theme section header */}
            <div className="section-header theme-section-header">
              <h3 className="section-title">상승률 상위 테마</h3>
              <button
                type="button"
                className="theme-collapse-button"
                onClick={() => setThemesExpanded(expanded => !expanded)}
                aria-expanded={themesExpanded}
              >
                {themesExpanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
                {themesExpanded ? '접기' : '펼치기'}
              </button>
            </div>

            {themesExpanded && (
              <>
                {/* Theme period tabs */}
                <div className="theme-controls-sticky">
                  <div className="theme-period-tabs">
                    {THEME_PERIODS.map(p => (
                      <button
                        key={p}
                        className={themePeriod === p ? 'active' : ''}
                        onClick={() => handleThemePeriodChange(p)}
                      >{p}</button>
                    ))}
                  </div>
                  <div className="theme-basis-note">
                    {themeBasisText} · 장 마감 후 순차 업데이트
                  </div>
                </div>

                {/* Theme list */}
                {themesLoading ? (
                  <div className="themes-loading">
                    {themePeriod === '1D' ? '로딩중…' : '기간 수익률 준비 중…'}
                  </div>
                ) : themeError ? (
                  <div className="themes-loading">{themeError}</div>
                ) : themes.length === 0 ? (
                  <div className="themes-loading">표시할 테마가 없습니다.</div>
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
              </>
            )}
          </>
        )}
      </div>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <div className="main-content" ref={mainContentRef}>
        {activeView === 'journal' ? (
          <Suspense fallback={<div className="themes-loading">매매복기 화면을 불러오는 중입니다.</div>}>
            <TradingJournal
              apiBase={API_BASE}
              onEntitlementsChange={handleEntitlementsChange}
              accountPanelOpen={accountPanelOpen}
              onOpenAccountPanel={() => setAccountPanelOpen(true)}
              onCloseAccountPanel={() => setAccountPanelOpen(false)}
            />
          </Suspense>
        ) : (
          <>

        {/* Stock chip selector */}
        {themeTickers.length > 0 && (
          <div className="theme-stocks-selector" ref={themeStocksRef}>
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
                const retColor  = return_rate == null ? MARKET_FLAT : return_rate >= 0 ? MARKET_UP : MARKET_DOWN;
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
                  onClick={() => handleCandlePeriodChange(p.value)}
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
                  onClick={() => handleChartPeriodChange(p)}
                >{p}</button>
              ))}
            </div>

            <div style={separatorStyle} />

            {/* 봉 개수 */}
            <div className="controls-group">
              <span className="controls-label">봉 개수</span>
              <input
                className="candle-count-input"
                type="number"
                min="1"
                value={visibleCandleCount}
                placeholder="자동"
                onChange={(e) => setVisibleCandleCount(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') applyVisibleCandleCount();
                }}
              />
              <button
                className={`ctrl-btn ${visibleCandleCount ? 'active' : ''}`}
                onClick={applyVisibleCandleCount}
              >
                적용
              </button>
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
            
            <div style={separatorStyle} />

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
            const cacheKeyIntv = { 'D': '1d', 'W': '1w', 'M': '1m', 'Y': '1y', '1D': '1d', '1W': '1w', '1M': '1m', '1Y': '1y' }[candlePeriod] || '1d';
            const cacheKey = `${s.ticker}_${cacheKeyIntv}`;
            const data = stockData[cacheKey] || Object.entries(stockData).find(([key]) => key.startsWith(`${s.ticker}_`))?.[1];
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
              <Suspense
                key={s.ticker}
                fallback={(
                  <div style={{
                    height: '80px', background: '#131722', borderRadius: '8px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#555', fontSize: '13px', marginBottom: '4px',
                  }}>
                    {s.name} 차트를 불러오는 중입니다.
                  </div>
                )}
              >
                <StockChart
                  ref={el => { chartRefs.current[s.ticker] = el; }}
                  ticker={s.ticker}
                  name={s.name}
                  data={data}
                  chartPeriod={chartPeriod}
                  candlePeriod={candlePeriod}
                  visibleCandleCount={visibleCandleCount}
                  setVisibleCandleCount={setVisibleCandleCount}
                  candleCountApplySeq={candleCountApplySeq}
                  onApplyCandleCount={applyVisibleCandleCount}
                  scaleMode={scaleMode}
                  activeInds={activeInds}
                  onIndicatorsChange={setActiveInds}
                  paneLayoutKey={paneLayoutKey}
                  paneStretchFactors={chartPaneLayouts[paneLayoutKey]}
                  onPaneStretchFactorsChange={handlePaneLayoutChange}
                  drawings={chartDrawings[s.ticker] || []}
                  onDrawingsChange={(drawings) => handleChartDrawingsChange(s.ticker, drawings)}
                  bbMultiplier={bbMultiplier}
                  onTimeRangeChange={handleTimeRangeChange}
                  onCandlePeriodChange={handleCandlePeriodChange}
                  onChartPeriodChange={handleChartPeriodChange}
                  onOpenDetailAd={handleChartDetailAd}
                  onRemove={() => setSelectedStocks(prev => prev.filter(st => st.ticker !== s.ticker))}
                />
              </Suspense>
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
            <div style={{ fontSize: '14px' }}>테마를 선택하거나 종목을 검색하세요</div>
          </div>
        )}
          </>
        )}
      </div>
    </div>
    {showExitConfirm && (
      <div className="app-exit-backdrop" role="presentation" onClick={() => setShowExitConfirm(false)}>
        <div className="app-exit-dialog" role="dialog" aria-modal="true" aria-labelledby="app-exit-title" onClick={event => event.stopPropagation()}>
          <h2 id="app-exit-title">앱을 종료할까요?</h2>
          <p>종료하면 현재 보고 있던 화면이 닫힙니다.</p>
          <div className="app-exit-actions">
            <button type="button" onClick={() => setShowExitConfirm(false)}>취소</button>
            <button type="button" className="confirm" onClick={exitApplication}>종료</button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
