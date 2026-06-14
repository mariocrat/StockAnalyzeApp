import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import JournalTradeChart from './JournalTradeChart';

const sideLabels = { buy: '매수', sell: '매도' };
const DEFAULT_FEE_RATE = '0.015';
const DEFAULT_TAX_RATE = '0.15';
const DEV_AUTH_TOKEN = import.meta.env.VITE_DEV_AUTH_TOKEN || 'dev-token';
const DEV_AD_REWARD_TOKEN = import.meta.env.VITE_DEV_AD_REWARD_TOKEN || 'dev-ad-reward';
const DEV_ACCESS_PLAN = import.meta.env.VITE_DEV_ACCESS_PLAN || 'free';
const DEV_PRO_ENTITLEMENT_TOKEN = import.meta.env.VITE_DEV_PRO_ENTITLEMENT_TOKEN || 'dev-pro-entitlement';
const DEV_ENTITLEMENT_TOKEN = DEV_ACCESS_PLAN === 'pro' ? DEV_PRO_ENTITLEMENT_TOKEN : '';
const AUTH_STORAGE_KEY = 'alphamate.devAuth.v1';
const DEV_LOGIN_PROFILES = {
  kakao: { label: '카카오', provider_user_id: 'dev-kakao-user', display_name: '카카오 테스트' },
  naver: { label: '네이버', provider_user_id: 'dev-naver-user', display_name: '네이버 테스트' },
};
const REVIEW_PRODUCTS = [
  ['basic_review_30', '일반 복기 이용권 30회', '2,900원'],
  ['basic_review_100', '일반 복기 이용권 100회', '6,900원'],
  ['advanced_review_5', '심층 복기 이용권 5회', '2,900원'],
  ['advanced_review_10', '심층 복기 이용권 10회', '4,900원'],
];
const chartIntervalLabel = { '1m': '1분봉', '3m': '3분봉', '1d': '일봉' };
const reviewSourceLabels = {
  signup_basic: '가입 축하 제공량',
  free_daily_basic: '무료 일일 제공량',
  rewarded_ad_basic: '광고 보상 제공량',
  pro_monthly_basic: 'Pro 월 제공량',
  pro_monthly_advanced: 'Pro 심층 제공량',
  weekly_ad_advanced: '광고 보상 심층권',
  purchased_basic: '구매한 일반 복기 이용권',
  purchased_advanced: '구매한 심층 복기 이용권',
  purchased_advanced_as_basic: '심층 이용권 전환 사용',
};

const emptyForm = {
  trade_date: '',
  ticker: '',
  name: '',
  side: 'buy',
  price: '',
  quantity: '',
  fee: '',
  tax: '',
  memo: '',
};

function money(value) {
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value || 0);
}

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function reviewAccessText(access) {
  if (!access?.quota) return '';
  const plan = access.plan === 'pro' ? 'Pro' : '무료';
  const type = access.review_type === 'advanced' ? '심층 복기' : '일반 복기';
  const source = reviewSourceLabels[access.source] || access.source || '제공량';
  if (access.review_type === 'advanced') {
    const advanced = access.quota.advanced || {};
    return `${plan} · ${type} · ${source} · Pro ${advanced.pro_monthly_remaining || 0}회 · 광고 보상 ${advanced.weekly_reward_remaining || 0}회 · 구매 ${advanced.purchased_remaining || 0}회`;
  }
  const basic = access.quota.basic || {};
  return `${plan} · ${type} · ${source} · 오늘 무료 ${basic.free_daily_max_remaining || 0}회 · 구매 ${basic.purchased_remaining || 0}회`;
}

export default function TradingJournal({ apiBase }) {
  const oneTimeMode = import.meta.env.VITE_JOURNAL_STORAGE_MODE !== 'persisted';
  const [trades, setTrades] = useState([]);
  const [review, setReview] = useState(null);
  const [aiReview, setAiReview] = useState(null);
  const [chartReview, setChartReview] = useState({ charts: [] });
  const [activeChartTicker, setActiveChartTicker] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReviewType, setAiReviewType] = useState('basic');
  const [entitlements, setEntitlements] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiConsentAccepted, setAiConsentAccepted] = useState(false);
  const [stockQuery, setStockQuery] = useState('');
  const [stockResults, setStockResults] = useState([]);
  const [showStockResults, setShowStockResults] = useState(false);
  const [feeRate, setFeeRate] = useState(DEFAULT_FEE_RATE);
  const [taxRate, setTaxRate] = useState(DEFAULT_TAX_RATE);
  const [feeFree, setFeeFree] = useState(false);
  const [authSession, setAuthSession] = useState(loadStoredAuth);
  const [dataSummary, setDataSummary] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const stockSearchSeq = useRef(0);
  const suppressStockSearchRef = useRef(false);

  const activeAuthToken = authSession?.session_token || DEV_AUTH_TOKEN;
  const authHeaders = { Authorization: `Bearer ${activeAuthToken}` };
  const savedJournalMode = Boolean(authSession?.session_token && authSession?.user?.journal_storage_enabled);
  const transientJournalMode = oneTimeMode && !savedJournalMode;

  const loadDataSummary = async (tokenOverride = '') => {
    const token = tokenOverride || authSession?.session_token;
    if (!token) {
      setDataSummary(null);
      return null;
    }
    try {
      const res = await axios.get(`${apiBase}/api/me/data-summary`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDataSummary(res.data || null);
      return res.data || null;
    } catch {
      setDataSummary(null);
      return null;
    }
  };

  const loadEntitlements = async (tokenOverride = '') => {
    try {
      const res = await axios.get(`${apiBase}/api/journal/entitlements`, {
        params: { entitlement_token: DEV_ENTITLEMENT_TOKEN },
        headers: { Authorization: `Bearer ${tokenOverride || activeAuthToken}` },
      });
      setEntitlements(res.data || null);
    } catch {
      setEntitlements(null);
    }
  };

  const loadPersistedJournal = async (token) => {
    const headers = { Authorization: `Bearer ${token}` };
    const [tradeRes, reviewRes, chartRes] = await Promise.all([
      axios.get(`${apiBase}/api/journal/trades`, { headers }),
      axios.get(`${apiBase}/api/journal/review`, { headers }),
      axios.get(`${apiBase}/api/journal/charts`, { headers }),
    ]);
    setTrades(tradeRes.data || []);
    setReview(reviewRes.data || null);
    setChartReview(chartRes.data || { charts: [] });
    setActiveChartTicker(chartRes.data?.charts?.[0]?.ticker || '');
  };

  const handleDevLogin = async (provider) => {
    const profile = DEV_LOGIN_PROFILES[provider];
    if (!profile) return;
    setAuthLoading(true);
    try {
      const res = await axios.post(`${apiBase}/api/auth/dev-login`, {
        provider,
        provider_user_id: profile.provider_user_id,
        display_name: profile.display_name,
      });
      const session = res.data || null;
      setAuthSession(session);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
      await loadEntitlements(session?.session_token || '');
      await loadDataSummary(session?.session_token || '');
      if (session?.user?.journal_storage_enabled && session?.session_token) {
        await loadPersistedJournal(session.session_token);
      }
      setMessage(`${profile.label} 개발 계정으로 로그인했습니다.`);
    } catch (err) {
      setMessage(err.response?.data?.detail || '개발 로그인을 처리하지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    setAuthLoading(true);
    try {
      if (authSession?.session_token) {
        await axios.post(`${apiBase}/api/auth/logout`, {}, {
          headers: { Authorization: `Bearer ${authSession.session_token}` },
        });
      }
    } catch {
      // Local logout still clears the development session.
    } finally {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      setAuthSession(null);
      setDataSummary(null);
      await loadEntitlements(DEV_AUTH_TOKEN);
      setMessage('로그아웃했습니다.');
      setAuthLoading(false);
    }
  };

  const handleJournalStorageToggle = async (enabled) => {
    if (!authSession?.session_token) {
      setMessage('매매 이력 저장 설정은 로그인 후 변경할 수 있습니다.');
      return;
    }
    setAuthLoading(true);
    try {
      const res = await axios.patch(
        `${apiBase}/api/me/journal-storage`,
        { enabled },
        { headers: { Authorization: `Bearer ${authSession.session_token}` } },
      );
      const nextSession = {
        ...authSession,
        user: res.data,
      };
      setAuthSession(nextSession);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextSession));
      if (enabled) {
        await loadPersistedJournal(authSession.session_token);
      } else {
        setTrades([]);
        setReview(null);
        setChartReview({ charts: [] });
        setActiveChartTicker('');
      }
      await loadDataSummary(authSession.session_token);
      setMessage(enabled ? '매매 이력 저장을 켰습니다.' : '매매 이력 저장을 껐습니다.');
    } catch (err) {
      setMessage(err.response?.data?.detail || '매매 이력 저장 설정을 바꾸지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleClearSavedTrades = async () => {
    if (!savedJournalMode) {
      setMessage('저장된 매매 이력 삭제는 로그인 후 저장 기능을 켠 상태에서 사용할 수 있습니다.');
      return;
    }
    const ok = window.confirm('현재 로그인 계정의 저장된 매매 기록을 모두 삭제할까요?');
    if (!ok) return;
    setAuthLoading(true);
    try {
      const res = await axios.delete(`${apiBase}/api/journal/trades`, { headers: authHeaders });
      setTrades([]);
      setReview(null);
      setChartReview({ charts: [] });
      setActiveChartTicker('');
      setAiReview(null);
      setDataSummary(prev => prev ? { ...prev, saved_trade_count: 0 } : prev);
      setMessage(`저장된 매매 기록 ${res.data?.deleted_count || 0}건을 삭제했습니다.`);
    } catch (err) {
      setMessage(err.response?.data?.detail || '저장된 매매 기록을 삭제하지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const loadJournal = async (nextTrades = trades) => {
    if (transientJournalMode) {
      const reviewRes = await axios.post(`${apiBase}/api/journal/review-once`, { trades: nextTrades });
      setTrades(nextTrades);
      setReview(reviewRes.data || null);
      return;
    }

    const [tradeRes, reviewRes] = await Promise.all([
      axios.get(`${apiBase}/api/journal/trades`, { headers: authHeaders }),
      axios.get(`${apiBase}/api/journal/review`, { headers: authHeaders }),
    ]);
    setTrades(tradeRes.data || []);
    setReview(reviewRes.data || null);
  };

  const loadAiReview = async (nextTrades = trades, reviewType = aiReviewType) => {
    if (!nextTrades.length) {
      setMessage('AI 분석을 하려면 먼저 매매 기록을 입력하세요.');
      return;
    }
    if (!aiConsentAccepted) {
      setMessage('AI 분석 전 개인정보 및 매매 기록 전송 동의가 필요합니다.');
      return;
    }

    setAiLoading(true);
    try {
      const res = transientJournalMode
        ? await axios.post(
          `${apiBase}/api/journal/ai-review-once`,
          {
            trades: nextTrades,
            review_type: reviewType,
            ad_reward_token: reviewType === 'basic' && DEV_ACCESS_PLAN !== 'pro' ? DEV_AD_REWARD_TOKEN : '',
            entitlement_token: DEV_ENTITLEMENT_TOKEN,
            privacy_consent: aiConsentAccepted,
          },
          { headers: authHeaders },
        )
        : await axios.get(`${apiBase}/api/journal/ai-review`, { headers: authHeaders });
      setAiReview(res.data || null);
      if (res.data?.access?.wallet) setEntitlements(res.data.access.wallet);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'AI 분석을 불러오지 못했습니다.');
      setAiReview({
        status: 'error',
        summary: 'AI 복기 분석을 불러오지 못했습니다.',
        chart_reviews: [],
      });
    } finally {
      setAiLoading(false);
    }
  };

  const loadChartReview = async (nextTrades = trades) => {
    try {
      const res = transientJournalMode
        ? await axios.post(`${apiBase}/api/journal/charts-once`, { trades: nextTrades })
        : await axios.get(`${apiBase}/api/journal/charts`, { headers: authHeaders });
      const data = res.data || { charts: [] };
      setChartReview(data);
      if (!activeChartTicker && data.charts?.[0]?.ticker) {
        setActiveChartTicker(data.charts[0].ticker);
      }
    } catch {
      setChartReview({ charts: [] });
    }
  };

  useEffect(() => {
    loadJournal()
      .then(() => Promise.all([loadChartReview(), loadEntitlements(), loadDataSummary()]))
      .catch(() => setMessage('매매 기록을 불러오지 못했습니다.'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = review?.summary || {};

  const updateForm = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  useEffect(() => {
    const query = stockQuery.trim();
    if (suppressStockSearchRef.current) {
      suppressStockSearchRef.current = false;
      return;
    }
    if (!query) {
      setStockResults([]);
      setShowStockResults(false);
      return;
    }

    const requestId = stockSearchSeq.current + 1;
    stockSearchSeq.current = requestId;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await axios.get(`${apiBase}/api/search`, {
          params: { q: query },
          signal: controller.signal,
        });
        if (stockSearchSeq.current !== requestId) return;
        setStockResults(res.data || []);
        setShowStockResults(true);
      } catch (err) {
        if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
        if (stockSearchSeq.current === requestId) setStockResults([]);
      }
    }, 180);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [stockQuery, apiBase]);

  useEffect(() => {
    setForm(prev => {
      const amount = Number(prev.price || 0) * Number(prev.quantity || 0);
      const nextFee = feeFree ? 0 : Math.round(amount * (Number(feeRate || 0) / 100));
      const nextTax = prev.side === 'sell'
        ? Math.round(amount * (Number(taxRate || 0) / 100))
        : 0;
      if (Number(prev.fee || 0) === nextFee && Number(prev.tax || 0) === nextTax) return prev;
      return { ...prev, fee: String(nextFee), tax: String(nextTax) };
    });
  }, [form.price, form.quantity, form.side, feeRate, taxRate, feeFree]);

  const handleStockQueryChange = (value) => {
    setStockQuery(value);
    setForm(prev => ({ ...prev, name: value, ticker: '' }));
  };

  const selectStock = (result) => {
    const ticker = result.Ticker || result.ticker || '';
    const name = result.Name || result.name || ticker;
    suppressStockSearchRef.current = true;
    setStockQuery(name);
    setShowStockResults(false);
    setForm(prev => ({ ...prev, ticker, name }));
  };

  const devPurchaseProduct = async (productId) => {
    try {
      const res = await axios.post(
        `${apiBase}/api/journal/dev-purchase`,
        { product_id: productId, entitlement_token: DEV_ENTITLEMENT_TOKEN },
        { headers: authHeaders },
      );
      setEntitlements(res.data || null);
      setMessage('개발용 복기권을 충전했습니다. 실제 배포에서는 Google Play 결제로 교체됩니다.');
    } catch (err) {
      setMessage(err.response?.data?.detail || '복기권 구매 처리를 실패했습니다.');
    }
  };

  const submitManual = async () => {
    if (!form.trade_date || !form.name || !form.price || !form.quantity) {
      setMessage('일시, 종목명, 가격, 수량은 꼭 입력해야 합니다.');
      return;
    }
    setLoading(true);
    try {
      if (transientJournalMode) {
        const nextTrade = {
          id: Date.now(),
          ...form,
          price: Number(form.price),
          quantity: Number(form.quantity),
          fee: Number(form.fee || 0),
          tax: Number(form.tax || 0),
        };
        const nextTrades = [...trades, nextTrade];
        setForm(emptyForm);
        setStockQuery('');
        setMessage('복기 기록을 이번 화면에만 추가했습니다.');
        await loadJournal(nextTrades);
        setAiReview(null);
        await loadChartReview(nextTrades);
        return;
      }

      await axios.post(
        `${apiBase}/api/journal/trades`,
        {
          ...form,
          price: Number(form.price),
          quantity: Number(form.quantity),
          fee: Number(form.fee || 0),
          tax: Number(form.tax || 0),
        },
        { headers: authHeaders },
      );
      setForm(emptyForm);
      setStockQuery('');
      setMessage('매매 기록을 저장했습니다.');
      await loadJournal();
      await loadDataSummary();
      setAiReview(null);
      await loadChartReview();
    } catch {
      setMessage('저장하지 못했습니다. 입력값을 확인해주세요.');
    } finally {
      setLoading(false);
    }
  };

  const removeTrade = async (id) => {
    if (transientJournalMode) {
      const nextTrades = trades.filter(trade => trade.id !== id);
      await loadJournal(nextTrades);
      setAiReview(null);
      await loadChartReview(nextTrades);
      return;
    }

    await axios.delete(`${apiBase}/api/journal/trades/${id}`, { headers: authHeaders });
    await loadJournal();
    await loadDataSummary();
    setAiReview(null);
    await loadChartReview();
  };

  const activeTradeChart = (chartReview.charts || []).find(chart => chart.ticker === activeChartTicker)
    || chartReview.charts?.[0];
  const activeIdentity = authSession?.user?.identities?.[0];
  const activeProviderLabel = activeIdentity ? DEV_LOGIN_PROFILES[activeIdentity.provider]?.label || activeIdentity.provider : '';
  const connectedProviderText = (dataSummary?.connected_providers || [])
    .map(provider => DEV_LOGIN_PROFILES[provider]?.label || provider)
    .join(', ') || '-';

  return (
    <div className="journal-page">
      <div className="journal-header">
        <div>
          <h2>매매복기</h2>
          <p>매수와 매도 기록을 남기고 실현손익, 승률, 반복 패턴을 점검합니다.</p>
        </div>
      </div>

      <div className="journal-summary">
        <div><span>기록</span><strong>{summary.trade_count || 0}건</strong></div>
        <div><span>실현손익</span><strong className={(summary.realized_pnl || 0) >= 0 ? 'positive' : 'negative'}>{money(summary.realized_pnl)}원</strong></div>
        <div><span>수익률</span><strong>{summary.realized_return_pct || 0}%</strong></div>
        <div><span>승률</span><strong>{summary.win_rate_pct || 0}%</strong></div>
      </div>

      {message && <div className="journal-message">{message}</div>}

      <section className="journal-panel journal-account-panel">
        <div className="journal-panel-title">
          <h3>계정/데이터 관리</h3>
          <span className="journal-chart-mode">{authSession ? activeProviderLabel : '개발 모드'}</span>
        </div>
        <div className="journal-auth-box">
          <div>
            <strong>{authSession ? `${authSession.user?.display_name || activeProviderLabel} 로그인 중` : '로그인 안 됨'}</strong>
            <span>{authSession ? `사용자 ${String(authSession.user?.id || '').slice(0, 8)}` : '기본 개발 계정으로 표시됩니다.'}</span>
          </div>
          <div className="journal-auth-actions">
            <button className="journal-secondary" disabled={authLoading} onClick={() => handleDevLogin('kakao')}>
              카카오
            </button>
            <button className="journal-secondary" disabled={authLoading} onClick={() => handleDevLogin('naver')}>
              네이버
            </button>
            {authSession && (
              <button className="journal-secondary" disabled={authLoading} onClick={handleLogout}>
                로그아웃
              </button>
            )}
          </div>
        </div>
        <div className="journal-data-grid">
          <div>
            <span>계정 상태</span>
            <strong>{authSession ? '로그인됨' : '로그인 안 됨'}</strong>
          </div>
          <div>
            <span>연결 로그인</span>
            <strong>{connectedProviderText}</strong>
          </div>
          <div>
            <span>저장된 매매 기록</span>
            <strong>{authSession ? `${dataSummary?.saved_trade_count ?? 0}건` : '0건'}</strong>
          </div>
          <div>
            <span>AI 분석 기록</span>
            <strong>{dataSummary?.server_keeps_ai_review_history ? '서버 저장' : '서버 저장 안 함'}</strong>
          </div>
        </div>
        <label className="journal-auth-toggle">
          <input
            type="checkbox"
            checked={Boolean(authSession?.user?.journal_storage_enabled)}
            disabled={!authSession || authLoading}
            onChange={e => handleJournalStorageToggle(e.target.checked)}
          />
          <span>매매 이력 저장</span>
          <em>{authSession?.user?.journal_storage_enabled ? '켜짐' : '꺼짐'}</em>
        </label>
        {savedJournalMode && (
          <button className="journal-danger" disabled={authLoading || !trades.length} onClick={handleClearSavedTrades}>
            저장 기록 전체 삭제
          </button>
        )}
        <p className="journal-privacy-note">
          저장 기능을 켠 로그인 계정의 매매 기록만 서버에 보관됩니다. 전체 삭제는 현재 로그인 계정의 저장 기록에만 적용됩니다.
        </p>
      </section>

      <section className="journal-panel">
        <h3>매매 기록 입력</h3>
        <div className="journal-form">
          <input type="datetime-local" value={form.trade_date} onChange={e => updateForm('trade_date', e.target.value)} />
          <div className="journal-stock-search">
            <input
              placeholder="종목명 검색"
              value={stockQuery}
              onChange={e => handleStockQueryChange(e.target.value)}
              onFocus={() => stockResults.length && setShowStockResults(true)}
              onBlur={() => setTimeout(() => setShowStockResults(false), 180)}
            />
            {showStockResults && stockResults.length > 0 && (
              <ul className="journal-stock-results">
                {stockResults.map(result => {
                  const ticker = result.Ticker || result.ticker;
                  const name = result.Name || result.name || ticker;
                  return (
                    <li key={ticker} onMouseDown={() => selectStock(result)}>
                      <span>{name}</span>
                      <em>{ticker}</em>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <input placeholder="종목코드" value={form.ticker} onChange={e => updateForm('ticker', e.target.value)} />
          <select value={form.side} onChange={e => updateForm('side', e.target.value)}>
            <option value="buy">매수</option>
            <option value="sell">매도</option>
          </select>
          <input type="number" placeholder="가격" value={form.price} onChange={e => updateForm('price', e.target.value)} />
          <input type="number" placeholder="수량" value={form.quantity} onChange={e => updateForm('quantity', e.target.value)} />
          <label className="journal-check">
            <input type="checkbox" checked={feeFree} onChange={e => setFeeFree(e.target.checked)} />
            수수료 무료
          </label>
          <input type="number" step="0.001" placeholder="수수료율(%)" value={feeRate} disabled={feeFree} onChange={e => setFeeRate(e.target.value)} />
          <input type="number" step="0.01" placeholder="세금률(%)" value={taxRate} onChange={e => setTaxRate(e.target.value)} />
          <input type="number" placeholder="수수료" value={form.fee} readOnly />
          <input type="number" placeholder="세금" value={form.tax} readOnly />
          <textarea placeholder="매매 이유, 감정, 실수 메모" value={form.memo} onChange={e => updateForm('memo', e.target.value)} />
        </div>
        <button className="journal-primary" disabled={loading} onClick={submitManual}>저장</button>
      </section>

      <section className="journal-panel">
        <div className="journal-panel-title">
          <h3>이용권</h3>
          <span className="journal-chart-mode">{entitlements?.plan === 'pro' ? 'Pro' : '무료'}</span>
        </div>
        <div className="journal-entitlement-grid">
          <div><span>무료 일반 복기</span><strong>{(entitlements?.basic?.signup_remaining || 0) + (entitlements?.basic?.free_daily_max_remaining || 0)}</strong></div>
          <div><span>Pro 일반 복기</span><strong>{entitlements?.basic?.pro_monthly_remaining || 0}</strong></div>
          <div><span>구매 일반 이용권</span><strong>{entitlements?.basic?.purchased_remaining || 0}</strong></div>
          <div><span>Pro 심층 복기</span><strong>{entitlements?.advanced?.pro_monthly_remaining || 0}</strong></div>
          <div><span>광고 보상 심층권</span><strong>{entitlements?.advanced?.weekly_reward_remaining || 0}</strong></div>
          <div><span>구매 심층 이용권</span><strong>{entitlements?.advanced?.purchased_remaining || 0}</strong></div>
        </div>
        <div className="journal-product-list">
          {REVIEW_PRODUCTS.map(([id, label, price]) => (
            <button key={id} className="journal-secondary" onClick={() => devPurchaseProduct(id)}>
              {label} · {price}
            </button>
          ))}
        </div>
      </section>

      <section className="journal-panel">
        <div className="journal-panel-title">
          <h3>매매 차트</h3>
          <span className="journal-chart-mode">
            {chartIntervalLabel[activeTradeChart?.interval] || (activeTradeChart?.timeframe === 'intraday' ? '분봉' : '일봉')} · {activeTradeChart?.source || '-'}
          </span>
        </div>
        {chartReview.charts?.length > 1 && (
          <div className="journal-chart-tabs">
            {chartReview.charts.map(chart => (
              <button
                key={chart.ticker}
                className={chart.ticker === activeTradeChart?.ticker ? 'active' : ''}
                onClick={() => setActiveChartTicker(chart.ticker)}
              >
                {chart.name}
              </button>
            ))}
          </div>
        )}
        <JournalTradeChart chartData={activeTradeChart} />
        <div className="journal-chart-review-list">
          {(activeTradeChart?.reviews || []).map((item, idx) => (
            <div className="journal-ai-card" key={`${item.title || idx}-${idx}`}>
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
              {item.metrics && (
                <div className="journal-ai-metrics">
                  {item.metrics.price_vs_close_pct != null && <span>체결/종가 {item.metrics.price_vs_close_pct}%</span>}
                  {item.metrics.after_5_bars != null && <span>이후 5봉 {item.metrics.after_5_bars}%</span>}
                  {item.metrics.after_later_bars != null && <span>이후 흐름 {item.metrics.after_later_bars}%</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="journal-panel">
        <div className="journal-panel-title">
          <h3>복기 조언</h3>
          <div className="journal-review-actions">
            <button
              className="journal-secondary"
              disabled={aiLoading || !trades.length || !aiConsentAccepted}
              onClick={() => { setAiReviewType('basic'); loadAiReview(trades, 'basic'); }}
            >
              {aiLoading && aiReviewType === 'basic' ? '분석중' : '일반 복기'}
            </button>
            <button
              className="journal-secondary"
              disabled={aiLoading || !trades.length || !aiConsentAccepted}
              onClick={() => { setAiReviewType('advanced'); loadAiReview(trades, 'advanced'); }}
            >
              {aiLoading && aiReviewType === 'advanced' ? '분석중' : '심층 복기'}
            </button>
          </div>
        </div>
        <label className="journal-ai-consent">
          <input
            type="checkbox"
            checked={aiConsentAccepted}
            onChange={e => setAiConsentAccepted(e.target.checked)}
          />
          <span>AI 분석을 위해 입력한 매매 기록과 차트 정보가 서버 및 AI 제공업체로 전송되는 것에 동의합니다.</span>
        </label>
        <div className="journal-advice">
          {(review?.advice || []).map((item, idx) => <p key={idx}>{item}</p>)}
        </div>
        <div className="journal-ai-review">
          {aiLoading ? (
            <p>매매 시점 차트 데이터를 읽고 있습니다.</p>
          ) : aiReview ? (
            <>
              <div className={`journal-ai-status ${aiReview.status || 'ready'}`}>
                {aiReview.source === 'openai' ? 'AI 분석' : '차트 기반 기본 분석'}
              </div>
              <p className="journal-ai-summary">{aiReview.summary}</p>
              {aiReview.access && (
                <div className="journal-ai-entitlement">
                  {reviewAccessText(aiReview.access)}
                </div>
              )}
              {(aiReview.chart_reviews || []).map((item, idx) => (
                <div className="journal-ai-card" key={`${item.title || idx}-${idx}`}>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  {item.metrics && (
                    <div className="journal-ai-metrics">
                      {item.metrics.rsi14 != null && <span>RSI {item.metrics.rsi14}</span>}
                      {item.metrics.return_10d_before != null && <span>10일전 {item.metrics.return_10d_before}%</span>}
                      {item.metrics.volume_ratio_20d != null && <span>거래량 {item.metrics.volume_ratio_20d}배</span>}
                      {item.metrics.next_5d_return != null && <span>이후 5일 {item.metrics.next_5d_return}%</span>}
                      {item.metrics.next_20d_return != null && <span>이후 20일 {item.metrics.next_20d_return}%</span>}
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            <p>AI 차트 분석을 실행하면 매매 시점의 차트 흐름까지 함께 복기합니다.</p>
          )}
        </div>
      </section>

      <section className="journal-panel">
        <h3>종목별 결과</h3>
        <div className="journal-table">
          <div className="journal-row journal-row-head">
            <span>종목</span><span>매수금액</span><span>매도금액</span><span>실현손익</span><span>미청산</span>
          </div>
          {(review?.by_symbol || []).map(row => (
            <div className="journal-row" key={row.ticker || row.name}>
              <span>{row.name} {row.ticker && <em>{row.ticker}</em>}</span>
              <span>{money(row.buy_amount)}</span>
              <span>{money(row.sell_amount)}</span>
              <span className={(row.realized_pnl || 0) >= 0 ? 'positive' : 'negative'}>{money(row.realized_pnl)}</span>
              <span>{row.open_quantity}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="journal-panel">
        <h3>최근 기록</h3>
        <div className="journal-table">
          {trades.map(trade => (
            <div className="journal-row" key={trade.id}>
              <span>{trade.trade_date}</span>
              <span>{trade.name} <em>{trade.ticker}</em></span>
              <span className={trade.side === 'buy' ? 'negative' : 'positive'}>{sideLabels[trade.side]}</span>
              <span>{money(trade.price)} x {trade.quantity}</span>
              <button onClick={() => removeTrade(trade.id)}>삭제</button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
