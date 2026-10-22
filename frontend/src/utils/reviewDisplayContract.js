// An explicit display compatibility declaration for AI execution/history only.
export const REVIEW_DISPLAY_CONTRACT_HEADER = 'X-Review-Display-Contract';
export const REVIEW_DISPLAY_CONTRACT = 'review-display.v1';
const UPDATE_REQUIRED_MESSAGE = 'AI 복기를 표시하려면 앱을 업데이트해 주세요.';

export function debugReviewClientHeaders(headers = {}, scheme = import.meta.env?.VITE_ANDROID_OAUTH_APP_SCHEME) {
  return scheme === 'com.mariocrat.stockanalyze.debug' ? { ...headers, 'X-StockBoda-Client': 'debug' } : headers;
}

export function reviewDisplayHeaders(headers = {}) {
  return { ...headers, [REVIEW_DISPLAY_CONTRACT_HEADER]: REVIEW_DISPLAY_CONTRACT };
}

export function reviewDisplayFailureMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (detail?.code === 'unsupported_review_display_client') return UPDATE_REQUIRED_MESSAGE;
  if (error?.response?.status === 401) return '로그인이 만료되었거나 필요합니다. 다시 로그인해 주세요.';
  if (error?.response?.status === 402) return '사용 가능한 복기권이 없습니다. 이용권을 확인해 주세요.';
  return fallback;
}
