// An explicit display compatibility declaration for AI execution/history only.
export const REVIEW_DISPLAY_CONTRACT_HEADER = 'X-Review-Display-Contract';
export const REVIEW_DISPLAY_CONTRACT = 'review-display.v1';
const UPDATE_REQUIRED_MESSAGE = 'AI 복기를 표시하려면 앱을 업데이트해 주세요.';

export function reviewDisplayHeaders(headers = {}) {
  return { ...headers, [REVIEW_DISPLAY_CONTRACT_HEADER]: REVIEW_DISPLAY_CONTRACT };
}

export function reviewDisplayFailureMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (detail?.code === 'unsupported_review_display_client') return UPDATE_REQUIRED_MESSAGE;
  return fallback;
}
