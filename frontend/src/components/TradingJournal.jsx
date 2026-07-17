import { useEffect, useRef, useState } from 'react';
import { App as CapacitorApp } from '@capacitor/app';
import axios from 'axios';
import { CircleAlert, Clock3, Keyboard, Ticket, UserRound, X } from 'lucide-react';
import kakaoLoginSymbol from '../assets/kakao-login-symbol.svg';
import naverLoginSymbol from '../assets/naver-login-symbol.svg';
import JournalTradeChart from './JournalTradeChart';
import { getAdMobRuntimeStatus, initializeAdMob, showReviewHistoryInterstitial, showRewardedReviewAd } from '../mobile/admob';
import { getBillingRuntimeStatus, initializeBilling, purchaseGooglePlayProduct, recoverGooglePlayPurchases } from '../mobile/billing';
import { shouldFinishGooglePlayTransaction } from '../mobile/billingPolicy';
import { buildAiReviewIdempotencyKey } from '../utils/aiReviewIdempotency';
import { reportClientEvent } from '../utils/clientEventLog';
import { parseOAuthAppReturnUrl } from '../utils/oauthAppReturn';
import { APP_BACK_REQUEST_EVENT } from '../utils/appNavigation';
import { toKoreanUserMessage } from '../utils/userMessage';

const sideLabels = { buy: '매수', sell: '매도' };
const DEFAULT_FEE_RATE = '0.015';
const DEFAULT_TAX_RATE = '0.15';
const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const DEV_TOOLS_ENABLED = APP_ENV !== 'production' && import.meta.env.VITE_ENABLE_DEV_TOOLS !== 'false';
const DEV_AUTH_TOKEN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_AUTH_TOKEN || 'dev-token' : '';
const DEV_AD_REWARD_TOKEN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_AD_REWARD_TOKEN || 'dev-ad-reward' : '';
const DEV_ACCESS_PLAN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_ACCESS_PLAN || 'free' : 'free';
const DEV_PRO_ENTITLEMENT_TOKEN = DEV_TOOLS_ENABLED ? import.meta.env.VITE_DEV_PRO_ENTITLEMENT_TOKEN || 'dev-pro-entitlement' : '';
const DEV_ENTITLEMENT_TOKEN = DEV_ACCESS_PLAN === 'pro' ? DEV_PRO_ENTITLEMENT_TOKEN : '';
const AUTH_STORAGE_KEY = 'alphamate.devAuth.v1';
const OAUTH_STATE_KEY = 'alphamate.oauthState.v1';
const KAKAO_REST_API_KEY = import.meta.env.VITE_KAKAO_REST_API_KEY || '';
const NAVER_CLIENT_ID = import.meta.env.VITE_NAVER_CLIENT_ID || '';
const KAKAO_REDIRECT_URI = import.meta.env.VITE_KAKAO_REDIRECT_URI || '';
const NAVER_REDIRECT_URI = import.meta.env.VITE_NAVER_REDIRECT_URI || '';
const GOOGLE_PLAY_PACKAGE_NAME = import.meta.env.VITE_GOOGLE_PLAY_PACKAGE_NAME || 'com.mariocrat.stockanalyze';
const DEV_LOGIN_PROFILES = {
  kakao: { label: '카카오', provider_user_id: 'dev-kakao-user', display_name: '카카오 테스트' },
  naver: { label: '네이버', provider_user_id: 'dev-naver-user', display_name: '네이버 테스트' },
};
const REVIEW_PRODUCTS = [
  ['basic_review_30', '일반 복기 이용권 30회', '2,900원'],
  ['basic_review_100', '일반 복기 이용권 100회', '6,900원'],
  ['advanced_review_5', '심화 복기 이용권 5회', '2,900원'],
  ['advanced_review_10', '심화 복기 이용권 10회', '4,900원'],
];
const chartIntervalLabel = { '1m': '1분봉', '3m': '3분봉', '1d': '일봉', '1wk': '주봉' };
const reviewSourceLabels = {
  signup_basic: '가입 축하 제공량',
  free_daily_basic: '무료 일일 제공량',
  rewarded_ad_basic: '광고 보상 제공량',
  pro_monthly_basic: 'Pro 월 제공량',
  pro_monthly_advanced: 'Pro 심화 복기 제공량',
  weekly_ad_advanced: '광고 보상 심화 복기 이용권',
  purchased_basic: '구매한 일반 복기 이용권',
  purchased_advanced: '구매한 심화 복기 이용권',
  purchased_advanced_as_basic: '심화 복기 이용권 전환 사용',
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

function dateTimeText(value) {
  if (!value) return '-';
  return String(value).replace('T', ' ').replace(/:00$/, '');
}

function localDateText(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function tradeDatePart(value) {
  return String(value || '').split('T')[0] || '';
}

function tradeTimePart(value) {
  return String(value || '').split('T')[1]?.slice(0, 5) || '';
}

function combineTradeDateTime(currentValue, { date, time }) {
  const nextDate = date ?? tradeDatePart(currentValue) ?? localDateText();
  const nextTime = time ?? tradeTimePart(currentValue);
  return nextDate && nextTime ? `${nextDate}T${nextTime}` : nextDate || '';
}

function normalizeDirectTime(value) {
  const digits = String(value || '').replace(/\D/g, '').slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}

function validTradeDateTime(value) {
  const match = String(value || '').match(/^\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})$/);
  return Boolean(match && Number(match[1]) <= 23 && Number(match[2]) <= 59);
}

function tradePeriodText(row) {
  const first = dateTimeText(row.first_trade_date);
  const last = dateTimeText(row.last_trade_date);
  return first === last ? first : `${first} ~ ${last}`;
}

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function loadStoredOAuthState() {
  try {
    return JSON.parse(localStorage.getItem(OAUTH_STATE_KEY) || 'null');
  } catch {
    return null;
  }
}

function randomState() {
  const bytes = new Uint8Array(16);
  if (window.crypto?.getRandomValues) {
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  }
  return `${Date.now()}-${Math.random()}`;
}

function ProviderIcon({ provider }) {
  const logo = provider === 'kakao' ? kakaoLoginSymbol : naverLoginSymbol;
  const label = provider === 'kakao' ? '카카오' : '네이버';

  return (
    <img className="provider-icon" src={logo} alt="" aria-hidden="true" title={label} />
  );
}

function providerButtonClass(provider) {
  return `journal-secondary provider-button provider-button-${provider}`;
}

function reviewAccessText(access) {
  if (!access?.quota) return '';
  const plan = access.plan === 'pro' ? 'Pro' : '무료';
  const type = access.review_type === 'advanced' ? '심화 복기' : '일반 복기';
  const source = reviewSourceLabels[access.source] || access.source || '제공량';
  if (access.review_type === 'advanced') {
    const advanced = access.quota.advanced || {};
    return `${plan} · ${type} · ${source} · Pro ${advanced.pro_monthly_remaining || 0}회 · 광고 보상 ${advanced.weekly_reward_remaining || 0}회 · 구매 ${advanced.purchased_remaining || 0}회`;
  }
  const basic = access.quota.basic || {};
  return `${plan} · ${type} · ${source} · 오늘 무료 ${basic.free_daily_max_remaining || 0}회 · 구매 ${basic.purchased_remaining || 0}회`;
}

export default function TradingJournal({
  apiBase,
  onEntitlementsChange,
  accountPanelOpen = false,
  onOpenAccountPanel,
  onCloseAccountPanel,
}) {
  const oneTimeMode = import.meta.env.VITE_JOURNAL_STORAGE_MODE !== 'persisted';
  const [trades, setTrades] = useState([]);
  const [review, setReview] = useState(null);
  const [aiReview, setAiReview] = useState(null);
  const [chartReview, setChartReview] = useState({ charts: [] });
  const [activeChartTicker, setActiveChartTicker] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReviewType, setAiReviewType] = useState('basic');
  const [adLoading, setAdLoading] = useState(false);
  const [purchaseLoadingId, setPurchaseLoadingId] = useState('');
  const [purchaseRecoveryLoading, setPurchaseRecoveryLoading] = useState(false);
  const [mobileAdStatus, setMobileAdStatus] = useState(getAdMobRuntimeStatus);
  const [billingStatus, setBillingStatus] = useState(getBillingRuntimeStatus);
  const [entitlements, setEntitlements] = useState(null);
  const [productCatalog, setProductCatalog] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [directTimeEntry, setDirectTimeEntry] = useState(false);
  const [message, setRawMessage] = useState('');
  const [reviewAccessDialog, setReviewAccessDialog] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiConsentAccepted, setAiConsentAccepted] = useState(false);
  const [stockQuery, setStockQuery] = useState('');
  const [stockResults, setStockResults] = useState([]);
  const [showStockResults, setShowStockResults] = useState(false);
  const [feeRate, setFeeRate] = useState(DEFAULT_FEE_RATE);
  const [taxRate, setTaxRate] = useState(DEFAULT_TAX_RATE);
  const [feeFree, setFeeFree] = useState(false);
  const [authSession, setAuthSession] = useState(loadStoredAuth);
  const [oauthServerStatus, setOauthServerStatus] = useState(null);
  const [appReadiness, setAppReadiness] = useState(null);
  const [dataSummary, setDataSummary] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [journalSubView, setJournalSubView] = useState('review');
  const [reviewHistory, setReviewHistory] = useState([]);
  const [activeReviewHistory, setActiveReviewHistory] = useState(null);
  const [reviewHistoryLoading, setReviewHistoryLoading] = useState(false);
  const stockSearchSeq = useRef(0);
  const suppressStockSearchRef = useRef(false);
  const reviewHistoryAdShownRef = useRef(false);
  const entitlementSectionRef = useRef(null);
  const setMessage = (value) => setRawMessage(toKoreanUserMessage(value));

  useEffect(() => {
    const handleBackRequest = (event) => {
      if (message) {
        event.detail.handled = true;
        setRawMessage('');
        return;
      }
      if (reviewAccessDialog) {
        event.detail.handled = true;
        setReviewAccessDialog(null);
        return;
      }
      if (accountPanelOpen) {
        event.detail.handled = true;
        onCloseAccountPanel?.();
        return;
      }
      if (journalSubView !== 'history') return;
      event.detail.handled = true;
      if (activeReviewHistory) {
        setActiveReviewHistory(null);
        return;
      }
      setJournalSubView('review');
    };
    window.addEventListener(APP_BACK_REQUEST_EVENT, handleBackRequest);
    return () => window.removeEventListener(APP_BACK_REQUEST_EVENT, handleBackRequest);
  }, [accountPanelOpen, activeReviewHistory, journalSubView, message, onCloseAccountPanel, reviewAccessDialog]);
  const handledOAuthReturnUrlRef = useRef('');

  const activeAuthToken = authSession?.session_token || DEV_AUTH_TOKEN;
  const authHeaders = { Authorization: `Bearer ${activeAuthToken}` };
  const savedJournalMode = Boolean(authSession?.session_token && authSession?.user?.journal_storage_enabled);
  const transientJournalMode = oneTimeMode && !savedJournalMode;

  const reportJournalClientEvent = (event) => reportClientEvent({
    apiBase,
    sessionToken: authSession?.session_token || '',
    path: '/journal',
    ...event,
  });

  useEffect(() => {
    if (onEntitlementsChange) onEntitlementsChange(entitlements);
  }, [entitlements, onEntitlementsChange]);

  const oauthRedirectUri = (provider) => {
    if (provider === 'kakao' && KAKAO_REDIRECT_URI) return KAKAO_REDIRECT_URI;
    if (provider === 'naver' && NAVER_REDIRECT_URI) return NAVER_REDIRECT_URI;
    const url = new URL(window.location.href);
    url.search = '';
    url.hash = '';
    url.searchParams.set('view', 'journal');
    url.searchParams.set('oauth_provider', provider);
    return url.toString();
  };

  const providerLabel = (provider) => (provider === 'kakao' ? '카카오' : '네이버');

  const oauthPublicConfigured = (provider) => (
    provider === 'kakao' ? Boolean(KAKAO_REST_API_KEY) : Boolean(NAVER_CLIENT_ID)
  );

  const oauthServerReady = (provider) => {
    const serverReady = oauthServerStatus?.providers?.[provider]?.server_ready;
    return serverReady !== false;
  };

  const oauthConfigured = (provider) => oauthPublicConfigured(provider);

  const oauthDisabledReason = (provider) => {
    if (!oauthPublicConfigured(provider)) {
      return provider === 'kakao'
        ? 'VITE_KAKAO_REST_API_KEY 설정 후 활성화됩니다.'
        : 'VITE_NAVER_CLIENT_ID 설정 후 활성화됩니다.';
    }
    const missing = oauthServerStatus?.providers?.[provider]?.missing_server_settings || [];
    if (missing.length) {
      return `서버 .env에 ${missing.join(', ')} 설정이 필요합니다.`;
    }
    return `${providerLabel(provider)} 로그인으로 이동합니다.`;
  };

  const oauthReadinessText = () => {
    if (authSession) return '';
    const missing = ['kakao', 'naver']
      .flatMap(provider => {
        const messages = [];
        if (!oauthPublicConfigured(provider)) messages.push(`${providerLabel(provider)} 프론트 키`);
        const serverMissing = oauthServerStatus?.providers?.[provider]?.missing_server_settings || [];
        if (serverMissing.length) messages.push(`${providerLabel(provider)} 서버 설정(${serverMissing.join(', ')})`);
        return messages;
      });
    if (!missing.length) return '카카오/네이버 실제 로그인 준비가 완료되었습니다.';
    return `실제 로그인 전 설정 필요: ${missing.join(', ')}`;
  };

  const oauthSetupRows = () => ['kakao', 'naver'].map(provider => {
    const publicSetting = provider === 'kakao' ? 'VITE_KAKAO_REST_API_KEY' : 'VITE_NAVER_CLIENT_ID';
    const redirectSetting = provider === 'kakao' ? 'VITE_KAKAO_REDIRECT_URI' : 'VITE_NAVER_REDIRECT_URI';
    const server = oauthServerStatus?.providers?.[provider] || null;
    const serverMissing = server?.missing_server_settings || [];
    return {
      provider,
      label: providerLabel(provider),
      publicSetting,
      redirectSetting,
      publicReady: oauthPublicConfigured(provider),
      serverReady: server?.server_ready === true,
      serverMissing,
      redirectUri: oauthRedirectUri(provider),
    };
  });

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

  const loadReviewHistory = async () => {
    if (!authSession?.session_token || !authSession?.user?.journal_storage_enabled) {
      setReviewHistory([]);
      setActiveReviewHistory(null);
      return [];
    }
    setReviewHistoryLoading(true);
    try {
      const res = await axios.get(`${apiBase}/api/journal/review-history`, {
        headers: { Authorization: `Bearer ${authSession.session_token}` },
      });
      const rows = res.data || [];
      setReviewHistory(rows);
      if (activeReviewHistory && !rows.some(item => item.id === activeReviewHistory.id)) {
        setActiveReviewHistory(null);
      }
      return rows;
    } catch (err) {
      setMessage(err.response?.data?.detail || '복기 보관함을 불러오지 못했습니다.');
      setReviewHistory([]);
      return [];
    } finally {
      setReviewHistoryLoading(false);
    }
  };

  const openReviewHistoryDetail = async (id) => {
    if (!authSession?.session_token) return;
    setReviewHistoryLoading(true);
    try {
      const res = await axios.get(`${apiBase}/api/journal/review-history/${id}`, {
        headers: { Authorization: `Bearer ${authSession.session_token}` },
      });
      setActiveReviewHistory(res.data || null);
    } catch (err) {
      setMessage(err.response?.data?.detail || '저장된 복기를 불러오지 못했습니다.');
    } finally {
      setReviewHistoryLoading(false);
    }
  };

  const deleteReviewHistoryItem = async (id) => {
    if (!authSession?.session_token) return;
    const ok = window.confirm('선택한 복기 기록을 삭제할까요?');
    if (!ok) return;
    setReviewHistoryLoading(true);
    try {
      await axios.delete(`${apiBase}/api/journal/review-history/${id}`, {
        headers: { Authorization: `Bearer ${authSession.session_token}` },
      });
      setReviewHistory(prev => prev.filter(item => item.id !== id));
      if (activeReviewHistory?.id === id) setActiveReviewHistory(null);
      setMessage('복기 기록을 삭제했습니다.');
    } catch (err) {
      setMessage(err.response?.data?.detail || '복기 기록을 삭제하지 못했습니다.');
    } finally {
      setReviewHistoryLoading(false);
    }
  };

  const enterReviewHistory = async () => {
    if (
      authSession?.user?.journal_storage_enabled
      && entitlements?.plan !== 'pro'
      && !reviewHistoryAdShownRef.current
    ) {
      reviewHistoryAdShownRef.current = true;
      try {
        await showReviewHistoryInterstitial();
      } catch (err) {
        reportJournalClientEvent({
          eventType: 'review_history_interstitial_failed',
          level: 'warning',
          message: err?.message || 'Review history interstitial failed.',
          details: {
            native: getAdMobRuntimeStatus().native,
            plan: entitlements?.plan || 'free',
            userId: authSession?.user?.id,
          },
        });
        // Ad failures should not block access to saved user data.
      }
    }
    setJournalSubView('history');
    await loadReviewHistory();
  };

  const loadEntitlements = async (tokenOverride = '') => {
    const token = tokenOverride || activeAuthToken;
    if (!token) {
      setEntitlements(null);
      return;
    }
    try {
      const res = await axios.get(`${apiBase}/api/journal/entitlements`, {
        params: { entitlement_token: DEV_ENTITLEMENT_TOKEN },
        headers: { Authorization: `Bearer ${token}` },
      });
      setEntitlements(res.data || null);
    } catch {
      setEntitlements(null);
    }
  };

  const loadProductCatalog = async () => {
    try {
      const res = await axios.get(`${apiBase}/api/journal/products`);
      setProductCatalog(res.data || null);
      return res.data || null;
    } catch {
      setProductCatalog(null);
      return null;
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
    if (!DEV_TOOLS_ENABLED) {
      setMessage('배포 모드에서는 실제 로그인 연결이 필요합니다.');
      return;
    }
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

  const handleOAuthStart = (provider) => {
    if (!oauthConfigured(provider)) {
      setMessage(`${provider === 'kakao' ? '카카오' : '네이버'} 로그인 설정값이 아직 없습니다.`);
      return;
    }
    if (!oauthServerReady(provider)) {
      setMessage(oauthDisabledReason(provider));
      return;
    }
    const state = randomState();
    const redirectUri = oauthRedirectUri(provider);
    localStorage.setItem(OAUTH_STATE_KEY, JSON.stringify({
      provider,
      state,
      redirect_uri: redirectUri,
      created_at: Date.now(),
    }));
    const authUrl = new URL(provider === 'kakao'
      ? 'https://kauth.kakao.com/oauth/authorize'
      : 'https://nid.naver.com/oauth2.0/authorize');
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('client_id', provider === 'kakao' ? KAKAO_REST_API_KEY : NAVER_CLIENT_ID);
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('state', state);
    window.location.href = authUrl.toString();
  };

  const finishOAuthLogin = async ({ provider, code, state, redirectUri }) => {
    setAuthLoading(true);
    try {
      const res = await axios.post(`${apiBase}/api/auth/login/${provider}/code`, {
        code,
        state,
        redirect_uri: redirectUri,
      });
      const session = res.data || null;
      setAuthSession(session);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
      localStorage.removeItem(OAUTH_STATE_KEY);
      await loadEntitlements(session?.session_token || '');
      await loadDataSummary(session?.session_token || '');
      if (session?.user?.journal_storage_enabled && session?.session_token) {
        await loadPersistedJournal(session.session_token);
      }
      const cleanUrl = new URL(window.location.href);
      cleanUrl.search = '';
      cleanUrl.searchParams.set('view', 'journal');
      window.history.replaceState({}, '', cleanUrl.toString());
      setMessage(`${provider === 'kakao' ? '카카오' : '네이버'} 로그인했습니다.`);
    } catch (err) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      reportJournalClientEvent({
        eventType: 'oauth_code_login_failed',
        level: 'warning',
        message: err?.message || 'OAuth code login failed.',
        details: {
          provider,
          stage: 'code_exchange',
          status: err.response?.status || 0,
        },
      });
      setMessage(err.response?.data?.detail || '로그인을 완료하지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };


  const finishOAuthTicketLogin = async ({ provider, ticket, state }) => {
    const stored = loadStoredOAuthState();
    if (!stored?.provider || stored.provider !== provider || stored.state !== state) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('로그인 확인값이 맞지 않습니다. 다시 로그인해 주세요.');
      return;
    }
    if (Date.now() - Number(stored.created_at || 0) > 10 * 60 * 1000) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('로그인 시간이 만료되었습니다. 다시 로그인해 주세요.');
      return;
    }
    if (!ticket) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('앱 로그인 티켓이 없습니다. 다시 로그인해 주세요.');
      return;
    }

    setAuthLoading(true);
    try {
      const res = await axios.post(`${apiBase}/api/auth/login/oauth-ticket`, { ticket });
      const session = res.data || null;
      setAuthSession(session);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
      localStorage.removeItem(OAUTH_STATE_KEY);
      await loadEntitlements(session?.session_token || '');
      await loadDataSummary(session?.session_token || '');
      if (session?.user?.journal_storage_enabled && session?.session_token) {
        await loadPersistedJournal(session.session_token);
      }
      const cleanUrl = new URL(window.location.href);
      cleanUrl.search = '';
      cleanUrl.searchParams.set('view', 'journal');
      window.history.replaceState({}, '', cleanUrl.toString());
      setMessage(`${provider === 'kakao' ? '카카오' : '네이버'} 로그인했습니다.`);
    } catch (err) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      reportJournalClientEvent({
        eventType: 'oauth_app_ticket_login_failed',
        level: 'warning',
        message: err?.message || 'OAuth app ticket login failed.',
        details: {
          provider,
          stage: 'ticket_exchange',
          status: err.response?.status || 0,
        },
      });
      setMessage(err.response?.data?.detail || '로그인을 완료하지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleOAuthAppReturn = (rawUrl) => {
    const parsed = parseOAuthAppReturnUrl(rawUrl);
    if (!parsed) return false;
    if (handledOAuthReturnUrlRef.current === rawUrl) return true;
    handledOAuthReturnUrlRef.current = rawUrl;
    if (parsed.error) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('로그인이 취소되었거나 실패했습니다. 다시 시도해 주세요.');
      return true;
    }
    finishOAuthTicketLogin(parsed);
    return true;
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
      setReviewHistory([]);
      setActiveReviewHistory(null);
      setJournalSubView('review');
      if (onEntitlementsChange) onEntitlementsChange({ plan: DEV_ACCESS_PLAN === 'pro' ? 'pro' : 'free' });
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
        setReviewHistory([]);
        setActiveReviewHistory(null);
        setJournalSubView('review');
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

  const handleExportAccountData = async () => {
    if (!authSession?.session_token) {
      setMessage('내 데이터 내보내기는 로그인 후 사용할 수 있습니다.');
      return;
    }
    setAuthLoading(true);
    try {
      const res = await axios.get(`${apiBase}/api/me/export-data`, {
        headers: { Authorization: `Bearer ${authSession.session_token}` },
      });
      const dateText = new Date().toISOString().slice(0, 10);
      const filename = `alphamate-my-data-${dateText}.json`;
      const jsonText = JSON.stringify(res.data || {}, null, 2);
      const file = typeof File === 'function'
        ? new File([jsonText], filename, { type: 'application/json;charset=utf-8' })
        : null;
      const canShareFile = file && navigator.share
        && (!navigator.canShare || navigator.canShare({ files: [file] }));

      if (canShareFile) {
        await navigator.share({ title: 'AlphaMate 내 데이터', files: [file] });
        setMessage('JSON 파일을 저장하거나 공유할 앱을 선택했습니다.');
      } else {
        const blob = new Blob([jsonText], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
        setMessage('JSON 형식의 내 데이터 파일을 만들었습니다.');
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        setMessage('내 데이터 내보내기를 취소했습니다.');
        return;
      }
      setMessage(err.response?.data?.detail || '내 데이터를 내보내지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleDeleteAccountData = async () => {
    if (!authSession?.session_token) {
      setMessage('계정 데이터 삭제는 로그인 후 사용할 수 있습니다.');
      return;
    }
    const ok = window.confirm('현재 로그인 계정의 매매 기록, 복기권/구독 상태, 광고 보상 기록, 로그인 연결 정보를 서버에서 삭제할까요? 이 작업은 되돌릴 수 없습니다.');
    if (!ok) return;
    setAuthLoading(true);
    try {
      const res = await axios.delete(`${apiBase}/api/me/account-data`, {
        headers: { Authorization: `Bearer ${authSession.session_token}` },
      });
      localStorage.removeItem(AUTH_STORAGE_KEY);
      setAuthSession(null);
      setTrades([]);
      setReview(null);
      setAiReview(null);
      setChartReview({ charts: [] });
      setActiveChartTicker('');
      setReviewHistory([]);
      setActiveReviewHistory(null);
      setJournalSubView('review');
      setDataSummary(null);
      if (onEntitlementsChange) onEntitlementsChange({ plan: DEV_ACCESS_PLAN === 'pro' ? 'pro' : 'free' });
      await loadEntitlements(DEV_AUTH_TOKEN);
      setMessage(`계정 데이터 삭제가 완료됐습니다. 저장 기록 ${res.data?.deleted_trades || 0}건도 함께 삭제했습니다.`);
    } catch (err) {
      setMessage(err.response?.data?.detail || '계정 데이터를 삭제하지 못했습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const loadJournal = async (nextTrades = trades) => {
    if (transientJournalMode) {
      if (!nextTrades.length) {
        setTrades([]);
        setReview(null);
        return;
      }
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

  const loadAiReview = async (nextTrades = trades, reviewType = aiReviewType, options = {}) => {
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
      const idempotencyKey = buildAiReviewIdempotencyKey({
        trades: nextTrades,
        reviewType,
        targetTradeId: options.targetTradeId || '',
      });
      const res = await axios.post(
        `${apiBase}/api/journal/ai-review-once`,
        {
          trades: nextTrades,
          review_type: reviewType,
          ad_reward_token: options.adRewardToken ?? (DEV_TOOLS_ENABLED && reviewType === 'basic' && DEV_ACCESS_PLAN !== 'pro' ? DEV_AD_REWARD_TOKEN : ''),
          entitlement_token: DEV_ENTITLEMENT_TOKEN,
          privacy_consent: aiConsentAccepted,
        },
        { headers: { ...authHeaders, 'X-Idempotency-Key': idempotencyKey } },
      );
      setAiReview(res.data || null);
      if (res.data?.status === 'error') {
        setMessage('AI 서버 응답을 완료하지 못했습니다. 사용한 복기 이용권은 다시 돌려드렸습니다.');
      }
      if (res.data?.access?.wallet) setEntitlements(res.data.access.wallet);
      if (res.data?.review_history_id) {
        await loadReviewHistory();
      }
      if (authSession?.session_token) {
        await loadDataSummary(authSession.session_token);
      }
    } catch (err) {
      if (err.response?.status === 402 && reviewType === 'advanced') {
        setMessage('');
        setReviewAccessDialog('advanced');
        await loadEntitlements();
        return;
      }
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

  const startAdvancedReview = () => {
    setAiReviewType('advanced');
    const advanced = entitlements?.advanced;
    const availableTickets = advanced
      ? (advanced.pro_monthly_remaining || 0)
        + (advanced.weekly_reward_remaining || 0)
        + (advanced.purchased_remaining || 0)
      : null;
    if (availableTickets === 0) {
      setMessage('');
      setReviewAccessDialog('advanced');
      return;
    }
    loadAiReview(trades, 'advanced');
  };

  const showReviewPasses = () => {
    setReviewAccessDialog(null);
    window.requestAnimationFrame(() => {
      entitlementSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const claimAdvancedAdProgress = async (adRewardToken = '') => {
    const res = await axios.post(
      `${apiBase}/api/journal/ad-reward-claim`,
      {
        ad_reward_token: adRewardToken,
        entitlement_token: DEV_ENTITLEMENT_TOKEN,
      },
      { headers: authHeaders },
    );
    if (res.data?.ad_reward?.claimed || res.data?.ad_reward?.blocked_reason) {
      setEntitlements(res.data);
      return res.data;
    }
    return null;
  };

  const handleRewardedAdAdvancedTicket = async () => {
    if (!authSession?.user?.id) {
      setMessage('광고 보상은 로그인 후 받을 수 있습니다. 먼저 카카오 또는 네이버 로그인을 완료해주세요.');
      return;
    }
    if (entitlements?.plan === 'pro') {
      setMessage('Pro 이용자는 월 제공되는 심화 복기 이용권을 광고 없이 사용할 수 있습니다.');
      return;
    }
    if ((entitlements?.advanced?.weekly_reward_remaining || 0) > 0) {
      setMessage('이미 광고 보상 심화 복기 이용권 1장을 보유하고 있습니다.');
      return;
    }

    setAdLoading(true);
    try {
      const delayedReward = await claimAdvancedAdProgress();
      if (delayedReward) {
        if (delayedReward.ad_reward.blocked_reason === 'ticket_already_held') {
          setMessage('이미 광고 보상 심화 복기 이용권 1장을 보유하고 있습니다.');
          return;
        }
        if (delayedReward.ad_reward.blocked_reason === 'pro_no_ads') {
          setMessage('Pro 이용자는 월 제공되는 심화 복기 이용권을 광고 없이 사용할 수 있습니다.');
          return;
        }
        const granted = delayedReward.ad_reward.advanced_ticket_granted;
        setMessage(granted ? '광고 보상 심화 복기 이용권 1장이 지급되었습니다.' : '이전 광고 시청이 반영되었습니다.');
        return;
      }

      if (!mobileAdStatus.native) {
        if (!DEV_TOOLS_ENABLED) {
          setMessage('보상형 광고는 Android 앱에서 이용할 수 있습니다.');
          return;
        }
        const devReward = await claimAdvancedAdProgress(DEV_AD_REWARD_TOKEN);
        setMessage(devReward?.ad_reward?.advanced_ticket_granted
          ? '광고 보상 심화 복기 이용권 1장이 지급되었습니다.'
          : '테스트 광고 시청이 주간 횟수에 반영되었습니다.');
        return;
      }

      await showRewardedReviewAd({
        userId: authSession.user.id,
        purpose: 'advanced_ticket_progress',
      });
      if (mobileAdStatus.usingTestAdUnit) {
        setMessage('테스트 광고 재생을 확인했습니다. 테스트 광고는 실제 심화 복기 이용권을 지급하지 않습니다. 실제 AdMob 보상형 광고와 서버 보상 확인을 연결한 운영 앱에서 이용권이 지급됩니다.');
        return;
      }
      let claimed = null;
      for (let attempt = 0; attempt < 3 && !claimed; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 1600));
        claimed = await claimAdvancedAdProgress();
      }
      if (!claimed) {
        setMessage('광고 시청은 완료됐고 서버에서 보상을 확인 중입니다. 잠시 후 버튼을 다시 누르면 새 광고 없이 이전 보상부터 확인합니다.');
        return;
      }
      setMessage(claimed.ad_reward.advanced_ticket_granted
        ? '광고 보상 심화 복기 이용권 1장이 지급되었습니다.'
        : '광고 시청이 주간 횟수에 반영되었습니다.');
    } catch (err) {
      reportJournalClientEvent({
        eventType: 'rewarded_ad_advanced_ticket_failed',
        level: 'warning',
        message: err?.message || 'Rewarded ad advanced ticket failed.',
        details: {
          native: mobileAdStatus.native,
          platform: mobileAdStatus.platform,
          userId: authSession?.user?.id,
        },
      });
      setMessage(err?.response?.data?.detail || err?.message || '광고 보상을 확인하지 못했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setAdLoading(false);
      await loadEntitlements();
    }
  };

  const handleRewardedAdBasicReview = async () => {
    if (!trades.length) {
      setMessage('AI 분석을 하려면 먼저 매매 기록을 입력하세요.');
      return;
    }
    if (!aiConsentAccepted) {
      setMessage('AI 분석 전 개인정보 및 매매 기록 전송 동의가 필요합니다.');
      return;
    }

    setAiReviewType('basic');

    if (!mobileAdStatus.native) {
      if (DEV_TOOLS_ENABLED) {
        await loadAiReview(trades, 'basic');
      } else {
        setMessage('광고 시청은 Android 앱에서 사용할 수 있습니다. 웹에서는 무료 제공량 또는 구매 이용권으로 복기를 실행하세요.');
      }
      return;
    }

    if (!authSession?.user?.id) {
      setMessage('광고 보상은 로그인된 사용자에게만 지급됩니다. 먼저 카카오/네이버 로그인을 완료하세요.');
      return;
    }

    setAdLoading(true);
    try {
      await showRewardedReviewAd({ userId: authSession.user.id });
      setMessage('광고 시청을 확인했습니다. 서버 보상 확인 후 일반 복기를 실행합니다.');
      await new Promise(resolve => setTimeout(resolve, 1800));
      await loadAiReview(trades, 'basic', { adRewardToken: '' });
      await loadEntitlements();
    } catch (err) {
      reportJournalClientEvent({
        eventType: 'rewarded_ad_basic_review_failed',
        level: 'warning',
        message: err?.message || 'Rewarded ad basic review failed.',
        details: {
          native: mobileAdStatus.native,
          platform: mobileAdStatus.platform,
          userId: authSession?.user?.id,
        },
      });
      setMessage(err?.message || '광고 시청 또는 보상 확인을 완료하지 못했습니다.');
    } finally {
      setAdLoading(false);
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
    axios.get(`${apiBase}/api/auth/oauth-config`)
      .then(res => setOauthServerStatus(res.data || null))
      .catch(() => setOauthServerStatus(null));
    axios.get(`${apiBase}/api/app/readiness`)
      .then(res => {
        const data = res.data || null;
        setAppReadiness(data);
        if (data?.sections?.login?.providers) {
          setOauthServerStatus({ providers: data.sections.login.providers });
        }
      })
      .catch(() => setAppReadiness(null));
  }, [apiBase]);

  useEffect(() => {
    initializeAdMob()
      .then(status => setMobileAdStatus(status))
      .catch(() => setMobileAdStatus(getAdMobRuntimeStatus()));
  }, []);

  useEffect(() => {
    if (!productCatalog) return;
    initializeBilling(productCatalog)
      .then(status => setBillingStatus(status))
      .catch(() => setBillingStatus(getBillingRuntimeStatus()));
  }, [productCatalog]);

  useEffect(() => {
    loadJournal()
      .then(() => Promise.all([loadChartReview(), loadEntitlements(), loadDataSummary(), loadProductCatalog()]))
      .catch(() => setMessage('매매 기록을 불러오지 못했습니다.'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let listener = null;
    let active = true;
    CapacitorApp.addListener('appUrlOpen', ({ url }) => {
      handleOAuthAppReturn(url);
    }).then(handle => {
      listener = handle;
    }).catch(() => {});
    CapacitorApp.getLaunchUrl()
      .then(result => {
        if (active && result?.url) handleOAuthAppReturn(result.url);
      })
      .catch(() => {});
    return () => {
      active = false;
      if (listener?.remove) listener.remove();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (DEV_TOOLS_ENABLED || authSession?.session_token) return;
    const appReturn = parseOAuthAppReturnUrl(window.location.href);
    if (appReturn) {
      handleOAuthAppReturn(window.location.href);
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    if (!code || !state) return;

    const stored = loadStoredOAuthState();
    if (!stored?.provider || stored.state !== state) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('로그인 확인값이 맞지 않습니다. 다시 로그인해주세요.');
      return;
    }
    if (Date.now() - Number(stored.created_at || 0) > 10 * 60 * 1000) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      setMessage('로그인 시간이 만료되었습니다. 다시 로그인해주세요.');
      return;
    }
    finishOAuthLogin({
      provider: stored.provider,
      code,
      state,
      redirectUri: stored.redirect_uri || oauthRedirectUri(stored.provider),
    });
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
    if (!DEV_TOOLS_ENABLED) {
      setMessage('배포 모드에서는 Google Play 결제 검증이 필요합니다.');
      return;
    }
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

  const purchaseProduct = async (productId) => {
    if (!productCatalog) {
      setMessage('상품 정보를 아직 불러오지 못했습니다. 잠시 뒤 다시 시도하세요.');
      return;
    }
    if (!billingStatus.native) {
      if (DEV_TOOLS_ENABLED) {
        await devPurchaseProduct(productId);
      } else {
        setMessage('Google Play 결제는 Android 앱에서 사용할 수 있습니다.');
      }
      return;
    }
    if (!authSession?.session_token || !authSession?.user?.id) {
      setMessage('이용권 구매는 로그인 후 사용할 수 있습니다.');
      return;
    }

    setPurchaseLoadingId(productId);
    try {
      const purchase = await purchaseGooglePlayProduct({
        productCatalog,
        localProductId: productId,
        userId: authSession.user.id,
      });
      const res = await axios.post(
        `${apiBase}/api/journal/google-play-purchase`,
        {
          product_id: productId,
          purchase_token: purchase.purchaseToken,
          package_name: GOOGLE_PLAY_PACKAGE_NAME,
        },
        { headers: { Authorization: `Bearer ${authSession.session_token}` } },
      );
      setEntitlements(res.data || null);
      await loadDataSummary(authSession.session_token);
      if (shouldFinishGooglePlayTransaction(res.data)) {
        await purchase.transaction?.finish?.();
      }
      if (res.data?.purchase?.status === 'consume_pending') {
        setMessage('이용권은 반영됐습니다. Google Play 확정 처리는 다음 구매 확인 때 다시 시도됩니다.');
      } else {
        setMessage('Google Play 구매가 서버에서 검증되어 이용권에 반영됐습니다.');
      }
    } catch (err) {
      reportJournalClientEvent({
        eventType: 'google_play_purchase_failed',
        level: 'error',
        message: err.response?.data?.detail || err?.message || 'Google Play purchase failed.',
        details: {
          productId,
          native: billingStatus.native,
          platform: billingStatus.platform,
          serverStatus: err.response?.status,
        },
      });
      setMessage(err.response?.data?.detail || err?.message || 'Google Play 구매를 완료하지 못했습니다.');
    } finally {
      setPurchaseLoadingId('');
    }
  };

  const recoverPurchases = async () => {
    if (!productCatalog) {
      setMessage('상품 정보를 아직 불러오지 못했습니다. 잠시 뒤 다시 시도하세요.');
      return;
    }
    if (!billingStatus.native) {
      setMessage('구매 복구는 Android 앱에서 사용할 수 있습니다.');
      return;
    }
    if (!authSession?.session_token || !authSession?.user?.id) {
      setMessage('구매 복구는 로그인 후 사용할 수 있습니다.');
      return;
    }

    setPurchaseRecoveryLoading(true);
    try {
      const candidates = await recoverGooglePlayPurchases({
        productCatalog,
        userId: authSession.user.id,
      });
      if (!candidates.length) {
        setMessage('복구할 Google Play 구매 내역이 없습니다.');
        return;
      }

      let appliedCount = 0;
      for (const candidate of candidates) {
        const res = await axios.post(
          `${apiBase}/api/journal/google-play-purchase`,
          {
            product_id: candidate.localProductId,
            purchase_token: candidate.purchaseToken,
            package_name: GOOGLE_PLAY_PACKAGE_NAME,
          },
          { headers: { Authorization: `Bearer ${authSession.session_token}` } },
        );
        if (res.data) {
          appliedCount += 1;
          setEntitlements(res.data);
        }
      }
      await loadDataSummary(authSession.session_token);
      setMessage(`Google Play 구매 ${appliedCount}건을 다시 확인했습니다.`);
    } catch (err) {
      reportJournalClientEvent({
        eventType: 'google_play_purchase_recovery_failed',
        level: 'error',
        message: err.response?.data?.detail || err?.message || 'Google Play purchase recovery failed.',
        details: {
          native: billingStatus.native,
          platform: billingStatus.platform,
          serverStatus: err.response?.status,
        },
      });
      setMessage(err.response?.data?.detail || err?.message || 'Google Play 구매 복구를 완료하지 못했습니다.');
    } finally {
      setPurchaseRecoveryLoading(false);
    }
  };

  const submitManual = async () => {
    if (!validTradeDateTime(form.trade_date) || !form.name || !form.price || !form.quantity) {
      setMessage('날짜와 시간을 정확히 입력하고 종목명, 가격, 수량을 확인해주세요.');
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
  const adPolicy = productCatalog?.settings?.ad_policy || entitlements?.settings?.ad_policy || {};
  const readinessSections = appReadiness?.sections || {};
  const dataStorageReadiness = readinessSections.data_storage || {};
  const privacyPolicyReadiness = readinessSections.privacy_policy || {};
  const privacyPolicyUrl = `${String(apiBase || '').replace(/\/$/, '')}/privacy`;
  const googlePlayReadiness = readinessSections.google_play || productCatalog?.google_play || {};
  const admobStatus = readinessSections.admob || productCatalog?.admob || {};
  const aiReadiness = readinessSections.ai || {};
  const adsPerAdvancedTicket = adPolicy.ads_per_advanced_ticket || entitlements?.advanced?.weekly_ad_views_needed || 5;
  const weeklyAdViews = entitlements?.advanced?.weekly_ad_views || 0;
  const adPolicyText = `광고 ${adsPerAdvancedTicket}회 시청 시 주간 심화 복기 이용권 1장`;
  const adReadinessText = admobStatus.ready ? 'AdMob 보상형 광고 준비됨' : 'AdMob 광고 단위 설정 필요';
  const mobileAdStatusText = mobileAdStatus.native
    ? mobileAdStatus.productionMisconfigured
      ? '배포 모드 운영 AdMob 보상형 광고 단위 설정 필요'
      : `모바일 SDK 준비됨${mobileAdStatus.usingTestAdUnit ? ' · 테스트 광고 단위' : ''}`
    : '웹 화면에서는 네이티브 광고 미사용';
  const billingStatusText = billingStatus.native ? 'Google Play Billing SDK 준비됨' : '웹 화면에서는 Google Play 결제 미사용';
  const activeIdentity = authSession?.user?.identities?.[0];
  const activeProviderLabel = activeIdentity ? DEV_LOGIN_PROFILES[activeIdentity.provider]?.label || activeIdentity.provider : '';
  const consentRecordedAt = dataSummary?.privacy_consented_at || authSession?.user?.privacy_consented_at || '';
  const consentStatusText = consentRecordedAt ? '동의 완료' : '동의 필요';
  const consentDetailText = consentRecordedAt ? `동의일 ${consentRecordedAt.slice(0, 10)}` : 'AI 복기 실행 시 동의할 수 있습니다.';
  const missingText = (items = []) => items.length ? `누락: ${items.join(', ')}` : '설정 완료';
  const readinessItems = [
    {
      label: 'AI 복기',
      ready: aiReadiness.ready === true,
      detail: missingText(aiReadiness.missing_server_settings || []),
    },
    {
      label: 'Google Play 결제',
      ready: googlePlayReadiness.ready === true && billingStatus.native,
      detail: billingStatus.native
        ? missingText(googlePlayReadiness.missing_server_settings || [])
        : 'Android 앱에서 실제 결제 확인',
    },
    {
      label: '데이터 저장소',
      ready: dataStorageReadiness.ready === true,
      detail: missingText(dataStorageReadiness.missing_server_settings || []),
    },
    {
      label: '개인정보처리방침',
      ready: privacyPolicyReadiness.ready === true,
      detail: privacyPolicyReadiness.url || missingText(privacyPolicyReadiness.missing_server_settings || []),
    },
    {
      label: 'AdMob 보상 광고',
      ready: admobStatus.ready === true && mobileAdStatus.available,
      detail: mobileAdStatus.native
        ? missingText(admobStatus.missing_server_settings || [])
        : 'Android 앱에서 실제 광고 확인',
    },
    ...oauthSetupRows().map(provider => ({
      label: `${provider.label} 로그인`,
      ready: provider.publicReady && provider.serverReady,
      detail: [
        provider.publicReady ? '' : `${provider.publicSetting} 필요`,
        provider.serverMissing.length ? provider.serverMissing.join(', ') : '',
      ].filter(Boolean).join(' · ') || '설정 완료',
    })),
  ];

  const renderReviewHistoryArchive = () => {
    const savedReview = activeReviewHistory?.ai_review || null;
    const savedChartSnapshot = activeReviewHistory?.chart_snapshot || {};
    const savedChart = (savedChartSnapshot.charts || [])[0];
    const savedCards = savedReview?.chart_reviews || savedChartSnapshot.chart_reviews || [];

    return (
      <section className="journal-panel review-history-panel">
        <div className="journal-panel-title">
          <h3>복기 보관함</h3>
          <span className="journal-chart-mode">{reviewHistory.length}건</span>
        </div>
        {!authSession?.user?.journal_storage_enabled ? (
          <p className="journal-privacy-note">
            복기 보관함은 로그인 후 매매 이력 저장을 켠 경우에만 사용할 수 있습니다.
          </p>
        ) : (
          <div className="review-history-layout">
            <div className="review-history-list">
              <button className="journal-secondary" disabled={reviewHistoryLoading} onClick={loadReviewHistory}>
                {reviewHistoryLoading ? '불러오는 중' : '새로고침'}
              </button>
              {!reviewHistoryLoading && !reviewHistory.length && (
                <p className="journal-privacy-note">아직 저장된 AI 복기가 없습니다.</p>
              )}
              {reviewHistory.map(item => (
                <button
                  key={item.id}
                  className={activeReviewHistory?.id === item.id ? 'active' : ''}
                  onClick={() => openReviewHistoryDetail(item.id)}
                >
                  <strong>{item.name || item.ticker || '종목 미입력'}</strong>
                  <span>{item.review_type === 'advanced' ? '심화 복기' : '일반 복기'} · {dateTimeText(item.trade_date || item.created_at)}</span>
                </button>
              ))}
            </div>
            <div className="review-history-detail">
              {activeReviewHistory ? (
                <>
                  <div className="journal-panel-title">
                    <div>
                      <h4>{activeReviewHistory.name || activeReviewHistory.ticker || '저장된 복기'}</h4>
                      <span className="journal-chart-mode">
                        {activeReviewHistory.review_type === 'advanced' ? '심화 복기' : '일반 복기'}
                      </span>
                    </div>
                    <button
                      className="journal-danger journal-danger-outline"
                      disabled={reviewHistoryLoading}
                      onClick={() => deleteReviewHistoryItem(activeReviewHistory.id)}
                    >
                      삭제
                    </button>
                  </div>
                  <JournalTradeChart chartData={savedChart} />
                  <p className="journal-ai-summary">{savedReview?.summary || '저장된 복기 내용이 없습니다.'}</p>
                  <div className="journal-chart-review-list">
                    {savedCards.map((item, idx) => (
                      <div className="journal-ai-card" key={`${item.title || idx}-${idx}`}>
                        <strong>{item.title}</strong>
                        <p>{item.detail}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="journal-privacy-note">왼쪽에서 저장된 복기를 선택하세요.</p>
              )}
            </div>
          </div>
        )}
      </section>
    );
  };

  return (
    <div className="journal-page">
      <div className="journal-header">
        <div>
          <h2>매매복기</h2>
          <p>매수와 매도 기록을 남기고 실현손익, 승률, 반복 패턴을 점검합니다.</p>
        </div>
        <button
          type="button"
          className="journal-account-launch"
          onClick={onOpenAccountPanel}
          aria-label="계정 및 데이터 관리"
          title="계정 및 데이터 관리"
        >
          <UserRound size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="journal-summary">
        <div><span>기록</span><strong>{summary.trade_count || 0}건</strong></div>
        <div><span>실현손익</span><strong className={(summary.realized_pnl || 0) >= 0 ? 'positive' : 'negative'}>{money(summary.realized_pnl)}원</strong></div>
        <div><span>수익률</span><strong>{summary.realized_return_pct || 0}%</strong></div>
        <div><span>승률</span><strong>{summary.win_rate_pct || 0}%</strong></div>
      </div>

      {message && (
        <div className="journal-notice-backdrop" role="presentation" onClick={() => setRawMessage('')}>
          <section
            className="journal-notice-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="journal-notice-title"
            onClick={event => event.stopPropagation()}
          >
            <div className="journal-notice-icon" aria-hidden="true"><CircleAlert size={22} /></div>
            <h3 id="journal-notice-title">안내</h3>
            <p>{message}</p>
            <button type="button" onClick={() => setRawMessage('')}>확인</button>
          </section>
        </div>
      )}

      {reviewAccessDialog === 'advanced' && (
        <div className="journal-access-backdrop" role="presentation" onClick={() => setReviewAccessDialog(null)}>
          <section
            className="journal-access-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="advanced-review-access-title"
            onClick={event => event.stopPropagation()}
          >
            <div className="journal-access-icon" aria-hidden="true"><Ticket size={22} /></div>
            <h3 id="advanced-review-access-title">심화 복기 이용권이 필요합니다</h3>
            <p>심화 복기는 Pro 월 제공량, 광고 보상 심화 복기 이용권 또는 구매한 심화 복기 이용권 1장을 사용합니다.</p>
            <div className="journal-access-actions">
              <button type="button" onClick={() => setReviewAccessDialog(null)}>닫기</button>
              <button type="button" className="primary" onClick={showReviewPasses}>이용권 확인</button>
            </div>
          </section>
        </div>
      )}

      <div className="journal-subnav">
        <button className={journalSubView === 'review' ? 'active' : ''} onClick={() => setJournalSubView('review')}>
          매매복기
        </button>
        <button className={journalSubView === 'history' ? 'active' : ''} onClick={enterReviewHistory}>
          복기 보관함
        </button>
      </div>

      {accountPanelOpen && (
      <div className="journal-account-backdrop" role="presentation" onClick={onCloseAccountPanel}>
      <section
        className="journal-panel journal-account-panel journal-account-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="계정 및 데이터 관리"
        onClick={event => event.stopPropagation()}
      >
        <div className="journal-panel-title">
          <h3>계정/데이터 관리</h3>
          <button type="button" className="journal-account-close" onClick={onCloseAccountPanel} aria-label="닫기" title="닫기">
            <X size={19} aria-hidden="true" />
          </button>
        </div>
        <div className="journal-auth-box">
          <div>
            <strong>{authSession ? `${authSession.user?.display_name || activeProviderLabel} 계정` : '로그인이 필요합니다'}</strong>
            <span>{authSession ? `${activeProviderLabel}로 연결됨` : DEV_TOOLS_ENABLED ? '기본 개발 계정으로 표시됩니다.' : '복기 보관함과 이용권 관리를 위해 로그인하세요.'}</span>
          </div>
          <div className="journal-auth-actions">
            {DEV_TOOLS_ENABLED && (
              <>
                <button className={providerButtonClass('kakao')} disabled={authLoading} onClick={() => handleDevLogin('kakao')}>
                  <ProviderIcon provider="kakao" />
                  <span>카카오</span>
                </button>
                <button className={providerButtonClass('naver')} disabled={authLoading} onClick={() => handleDevLogin('naver')}>
                  <ProviderIcon provider="naver" />
                  <span>네이버</span>
                </button>
              </>
            )}
            {!DEV_TOOLS_ENABLED && !authSession && (
              <>
                <button
                  className={providerButtonClass('kakao')}
                  disabled={authLoading || !oauthConfigured('kakao')}
                  title={oauthConfigured('kakao') ? '카카오 로그인으로 이동합니다.' : 'VITE_KAKAO_REST_API_KEY 설정 후 활성화됩니다.'}
                  onClick={() => handleOAuthStart('kakao')}
                >
                  <ProviderIcon provider="kakao" />
                  <span>카카오 로그인</span>
                </button>
                <button
                  className={providerButtonClass('naver')}
                  disabled={authLoading || !oauthConfigured('naver')}
                  title={oauthConfigured('naver') ? '네이버 로그인으로 이동합니다.' : 'VITE_NAVER_CLIENT_ID 설정 후 활성화됩니다.'}
                  onClick={() => handleOAuthStart('naver')}
                >
                  <ProviderIcon provider="naver" />
                  <span>네이버 로그인</span>
                </button>
              </>
            )}
            {authSession && (
              <button className="journal-secondary" disabled={authLoading} onClick={handleLogout}>
                로그아웃
              </button>
            )}
          </div>
        </div>
        {!authSession && DEV_TOOLS_ENABLED && (
          <div className="journal-oauth-setup">
            <div className="journal-oauth-setup-head">
              <strong>실제 로그인 준비</strong>
              <span>{oauthReadinessText()}</span>
            </div>
            <div className="journal-oauth-provider-grid">
              {oauthSetupRows().map(row => (
                <div className="journal-oauth-provider" key={row.provider}>
                  <div className="journal-oauth-provider-title">
                    <strong>{row.label}</strong>
                    <span className={row.publicReady && row.serverReady ? 'ready' : 'not-ready'}>
                      {row.publicReady && row.serverReady ? '준비 완료' : '설정 필요'}
                    </span>
                  </div>
                  <ul>
                    <li className={row.publicReady ? 'ready' : 'not-ready'}>
                      프론트 키: {row.publicReady ? '설정됨' : row.publicSetting}
                    </li>
                    <li className={row.serverReady ? 'ready' : 'not-ready'}>
                      서버 설정: {row.serverReady ? '설정됨' : (row.serverMissing.length ? row.serverMissing.join(', ') : '확인 중')}
                    </li>
                    <li>
                      Redirect URI: <code>{row.redirectUri}</code>
                    </li>
                  </ul>
                  <p>{row.redirectSetting} 값을 provider 콘솔의 Redirect URI와 같게 맞추세요.</p>
                </div>
              ))}
            </div>
            {DEV_TOOLS_ENABLED && (
              <p className="journal-privacy-note">
                현재는 개발 모드라 위쪽 카카오/네이버 버튼은 개발용 계정 전환입니다. 실제 로그인 테스트는 `VITE_ALPHAMATE_ENV=production` 또는 `VITE_ENABLE_DEV_TOOLS=false`로 실행한 뒤 확인합니다.
              </p>
            )}
          </div>
        )}
        {authSession && (
          <div className="journal-data-grid">
            <div>
              <span>저장된 매매 기록</span>
              <strong>{dataSummary?.saved_trade_count ?? 0}건</strong>
            </div>
            <div>
              <span>AI 분석 기록</span>
              <strong>{dataSummary?.server_keeps_ai_review_history ? '서버 저장' : '서버 저장 안 함'}</strong>
            </div>
            <div>
              <span>AI 복기 동의</span>
              <strong>{consentStatusText}</strong>
              <em>{consentDetailText}</em>
            </div>
          </div>
        )}
        <details className="journal-privacy-disclosure">
          <summary>개인정보/AI 이용 안내</summary>
          <div>
            <p>AI 복기는 입력한 매매 기록, 메모, 차트 요약을 서버와 AI 제공업체로 전송해 분석합니다.</p>
            <p>매매 이력 저장을 켠 계정은 AI 복기 결과와 당시 차트 스냅샷이 복기 보관함에 저장될 수 있습니다.</p>
            <p>내 데이터 내보내기로 저장 내용을 확인할 수 있고, 계정 데이터 삭제로 현재 계정의 저장 데이터를 지울 수 있습니다.</p>
            <a href={privacyPolicyUrl} target="_blank" rel="noreferrer">
              개인정보처리방침 열기
            </a>
          </div>
        </details>
        {authSession && (
          <>
            <label className="journal-auth-toggle">
              <input
                type="checkbox"
                checked={Boolean(authSession.user?.journal_storage_enabled)}
                disabled={authLoading}
                onChange={e => handleJournalStorageToggle(e.target.checked)}
              />
              <span>매매 이력 저장</span>
              <em>{authSession.user?.journal_storage_enabled ? '켜짐' : '꺼짐'}</em>
            </label>
            {savedJournalMode && (
              <button className="journal-danger" disabled={authLoading || !trades.length} onClick={handleClearSavedTrades}>
                저장 기록 전체 삭제
              </button>
            )}
            <button className="journal-secondary journal-inline-action" disabled={authLoading} onClick={handleExportAccountData}>
              내 데이터 내보내기
            </button>
            <button className="journal-danger journal-danger-outline" disabled={authLoading} onClick={handleDeleteAccountData}>
              계정 데이터 삭제
            </button>
            <p className="journal-privacy-note">
              저장 기능을 켠 로그인 계정의 매매 기록만 서버에 보관됩니다. 내 데이터 내보내기는 저장 기록과 이용권 현황을 파일로 내려받고, 계정 데이터 삭제는 현재 로그인 계정의 저장 기록, 복기권/구독 상태, 광고 보상 기록, 로그인 연결 정보를 함께 정리합니다.
            </p>
          </>
        )}
      </section>
      </div>
      )}

      {journalSubView === 'history' ? (
        renderReviewHistoryArchive()
      ) : (
        <>
      <section className="journal-panel">
        <h3>매매 기록 입력</h3>
        <div className="journal-form">
          <div className="journal-field journal-datetime-field">
            <span>매매일시</span>
            <div className="journal-datetime-inputs">
              <input
                type="date"
                aria-label="매매 날짜"
                value={tradeDatePart(form.trade_date)}
                onChange={event => updateForm('trade_date', combineTradeDateTime(form.trade_date, { date: event.target.value }))}
              />
              <div className="journal-time-entry">
                <input
                  type={directTimeEntry ? 'text' : 'time'}
                  inputMode={directTimeEntry ? 'numeric' : undefined}
                  aria-label={directTimeEntry ? '매매 시간 직접 입력' : '매매 시간 선택'}
                  placeholder={directTimeEntry ? 'HH:MM' : undefined}
                  maxLength={directTimeEntry ? 5 : undefined}
                  value={tradeTimePart(form.trade_date)}
                  onChange={event => {
                    const time = directTimeEntry ? normalizeDirectTime(event.target.value) : event.target.value;
                    updateForm('trade_date', combineTradeDateTime(form.trade_date, {
                      date: tradeDatePart(form.trade_date) || localDateText(),
                      time,
                    }));
                  }}
                />
                <button
                  type="button"
                  className={directTimeEntry ? 'journal-time-mode active' : 'journal-time-mode'}
                  onClick={() => setDirectTimeEntry(value => !value)}
                  aria-label={directTimeEntry ? '시간 선택기로 전환' : '시간 직접 입력으로 전환'}
                  title={directTimeEntry ? '시간 선택기로 전환' : '시간 직접 입력으로 전환'}
                >
                  {directTimeEntry ? <Clock3 size={16} aria-hidden="true" /> : <Keyboard size={16} aria-hidden="true" />}
                </button>
              </div>
            </div>
          </div>
          <label className="journal-field">
            <span>종목명</span>
            <div className="journal-stock-search">
              <input
                placeholder="이름, 초성, 코드 검색"
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
          </label>
          <label className="journal-field"><span>종목코드</span><input placeholder="검색 시 자동 입력" value={form.ticker} onChange={e => updateForm('ticker', e.target.value)} /></label>
          <label className="journal-field"><span>구분</span><select value={form.side} onChange={e => updateForm('side', e.target.value)}><option value="buy">매수</option><option value="sell">매도</option></select></label>
          <label className="journal-field"><span>가격</span><input type="number" placeholder="체결가" value={form.price} onChange={e => updateForm('price', e.target.value)} /></label>
          <label className="journal-field"><span>수량</span><input type="number" placeholder="체결 수량" value={form.quantity} onChange={e => updateForm('quantity', e.target.value)} /></label>
          <div className="journal-field"><span>수수료 무료</span><label className="journal-check"><input type="checkbox" checked={feeFree} onChange={e => setFeeFree(e.target.checked)} /><span>무료 적용</span></label></div>
          <label className="journal-field"><span>수수료율</span><input type="number" step="0.001" value={feeRate} disabled={feeFree} onChange={e => setFeeRate(e.target.value)} /></label>
          <label className="journal-field"><span>세금률</span><input type="number" step="0.01" value={taxRate} onChange={e => setTaxRate(e.target.value)} /></label>
          <label className="journal-field"><span>수수료</span><input type="number" value={form.fee} readOnly /></label>
          <label className="journal-field"><span>세금</span><input type="number" value={form.tax} readOnly /></label>
          <label className="journal-field journal-field-memo"><span>매매 메모</span><textarea placeholder="선택 입력: 이유, 감정, 실수" value={form.memo} onChange={e => updateForm('memo', e.target.value)} /></label>
        </div>
        <button className="journal-primary" disabled={loading} onClick={submitManual}>저장</button>
      </section>

      <section className="journal-panel" ref={entitlementSectionRef}>
        <div className="journal-panel-title">
          <h3>이용권</h3>
          <span className="journal-chart-mode">{entitlements?.plan === 'pro' ? 'Pro' : '무료'}</span>
        </div>
        <div className="journal-entitlement-grid">
          <div><span>무료 일반 복기</span><strong>{(entitlements?.basic?.signup_remaining || 0) + (entitlements?.basic?.free_daily_max_remaining || 0)}</strong></div>
          <div><span>Pro 일반 복기</span><strong>{entitlements?.basic?.pro_monthly_remaining || 0}</strong></div>
          <div><span>구매 일반 이용권</span><strong>{entitlements?.basic?.purchased_remaining || 0}</strong></div>
          <div><span>Pro 심화 복기</span><strong>{entitlements?.advanced?.pro_monthly_remaining || 0}</strong></div>
          <div><span>광고 보상 심화 복기 이용권</span><strong>{entitlements?.advanced?.weekly_reward_remaining || 0}</strong></div>
          <div><span>구매 심화 복기 이용권</span><strong>{entitlements?.advanced?.purchased_remaining || 0}</strong></div>
        </div>
        <div className="journal-ad-policy">
          <div>
            <span>광고 보상 정책</span>
            <strong>{adPolicyText}</strong>
            <em>현재 주간 광고 시청 {weeklyAdViews}/{adsPerAdvancedTicket}회</em>
            <button
              type="button"
              className="journal-ad-reward-button"
              disabled={adLoading || entitlements?.plan === 'pro' || (entitlements?.advanced?.weekly_reward_remaining || 0) > 0}
              onClick={handleRewardedAdAdvancedTicket}
            >
              {adLoading
                ? '광고 보상 확인 중'
                : entitlements?.plan === 'pro'
                  ? 'Pro는 광고 없이 이용'
                  : (entitlements?.advanced?.weekly_reward_remaining || 0) > 0
                    ? '심화 복기 이용권 보유 중'
                    : '광고 보고 심화 복기 이용권 받기'}
            </button>
          </div>
          {DEV_TOOLS_ENABLED && (
            <>
              <div>
                <span>AdMob 상태</span>
                <strong className={admobStatus.ready ? 'ready' : 'not-ready'}>{adReadinessText}</strong>
                <em>{mobileAdStatusText}</em>
                <em>연속 광고 강제: {adPolicy.force_rewarded_ad_chain ? '켜짐' : '꺼짐'}</em>
              </div>
              <div>
                <span>결제 상태</span>
                <strong className={billingStatus.native ? 'ready' : 'not-ready'}>{billingStatusText}</strong>
                <em>패키지 {GOOGLE_PLAY_PACKAGE_NAME}</em>
              </div>
            </>
          )}
        </div>
        {DEV_TOOLS_ENABLED && (
          <div className="journal-readiness-box">
            <div className="journal-readiness-head">
              <strong>배포 준비 상태</strong>
              <span>{appReadiness?.overall_ready ? '서버 설정 준비됨' : '설정 확인 필요'}</span>
            </div>
            <div className="journal-readiness-grid">
              {readinessItems.map(item => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <strong className={item.ready ? 'ready' : 'not-ready'}>{item.ready ? '준비됨' : '설정 필요'}</strong>
                  <em>{item.detail}</em>
                </div>
              ))}
            </div>
          </div>
        )}
        {DEV_TOOLS_ENABLED || billingStatus.native ? (
          <div className="journal-product-list">
            {REVIEW_PRODUCTS.map(([id, label, price]) => (
              <button
                key={id}
                className="journal-secondary"
                disabled={Boolean(purchaseLoadingId)}
                onClick={() => purchaseProduct(id)}
              >
                {purchaseLoadingId === id ? '구매 확인중' : `${label} · ${price}`}
              </button>
            ))}
            {billingStatus.native && (
              <button
                className="journal-secondary"
                disabled={Boolean(purchaseLoadingId) || purchaseRecoveryLoading}
                onClick={recoverPurchases}
              >
                {purchaseRecoveryLoading ? '구매 복구중' : 'Google Play 구매 복구'}
              </button>
            )}
          </div>
        ) : (
          <p className="journal-privacy-note">
            배포 모드에서는 Google Play 결제 검증이 연결된 뒤 이용권 구매가 표시됩니다.
          </p>
        )}
      </section>

      <section className="journal-panel">
        <div className="journal-panel-title">
          <h3>매매 차트</h3>
          <span className="journal-chart-mode">
            {chartIntervalLabel[activeTradeChart?.interval] || (activeTradeChart?.timeframe === 'intraday' ? '분봉' : activeTradeChart?.timeframe === 'weekly' ? '주봉' : '일봉')}
            {activeTradeChart?.period_label ? ` · ${activeTradeChart.period_label}` : ''}
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
        <div className="journal-panel-title journal-review-title">
          <h3>AI 복기</h3>
          <div className="journal-review-actions">
            <button
              className="journal-secondary"
              disabled={aiLoading || adLoading || !trades.length || !aiConsentAccepted}
              onClick={() => { setAiReviewType('basic'); loadAiReview(trades, 'basic'); }}
            >
              {aiLoading && aiReviewType === 'basic' ? '분석중' : '일반 복기'}
            </button>
            <button
              className="journal-secondary"
              disabled={aiLoading || adLoading || !trades.length || !aiConsentAccepted}
              onClick={handleRewardedAdBasicReview}
              title={mobileAdStatus.native ? '보상형 광고를 본 뒤 일반 복기를 실행합니다.' : '웹에서는 개발 모드 확인 또는 모바일 앱 빌드가 필요합니다.'}
            >
              {adLoading ? '광고 확인중' : '광고 보고 일반 복기'}
            </button>
            <button
              className="journal-secondary"
              disabled={aiLoading || adLoading || !trades.length || !aiConsentAccepted}
              onClick={startAdvancedReview}
            >
              {aiLoading && aiReviewType === 'advanced' ? '분석중' : '심화 복기'}
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
        <div className="journal-symbol-results">
          {(review?.by_symbol || []).map(row => (
            <div className="journal-symbol-result" key={row.ticker || row.name}>
              <div className="journal-symbol-result-title"><strong>{row.name}</strong>{row.ticker && <span>{row.ticker}</span>}<em>{row.trade_count || 0}건</em></div>
              <div className="journal-symbol-result-grid">
                <div className="wide"><span>매매일시</span><strong>{tradePeriodText(row)}</strong></div>
                <div><span>매수액</span><strong>{money(row.buy_amount)}원</strong></div>
                <div><span>매도액</span><strong>{money(row.sell_amount)}원</strong></div>
                <div><span>순수익</span><strong className={(row.realized_pnl || 0) >= 0 ? 'positive' : 'negative'}>{money(row.realized_pnl)}원</strong></div>
                <div><span>수수료</span><strong>{money(row.total_fee)}원</strong></div>
                <div><span>세금</span><strong>{money(row.total_tax)}원</strong></div>
                <div><span>수익률</span><strong className={(row.realized_return_pct || 0) >= 0 ? 'positive' : 'negative'}>{row.realized_return_pct || 0}%</strong></div>
                <div><span>미청산</span><strong>{row.open_quantity}주</strong></div>
              </div>
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
              <span className={trade.side === 'buy' ? 'positive' : 'negative'}>{sideLabels[trade.side]}</span>
              <span>{money(trade.price)} x {trade.quantity}</span>
              <button onClick={() => removeTrade(trade.id)}>삭제</button>
            </div>
          ))}
        </div>
      </section>
        </>
      )}
    </div>
  );
}
