const REQUEST_ID_HEADER = 'x-request-id';
const REQUEST_ID_PATTERN = /^[A-Za-z0-9_.-]{8,80}$/;
const RETRY_AFTER_HEADER = 'retry-after';
const MAX_RETRY_AFTER_SECONDS = 3600;

function cleanRequestId(value) {
  const text = String(value || '').trim();
  return REQUEST_ID_PATTERN.test(text) ? text : '';
}

function headerValue(headers, name) {
  if (!headers) return '';
  if (typeof headers.get === 'function') return headers.get(name) || headers.get(name.toUpperCase()) || '';
  const match = Object.entries(headers).find(([key]) => String(key).toLowerCase() === name);
  return match?.[1] || '';
}

export function requestIdFromAxiosError(error) {
  return cleanRequestId(headerValue(error?.response?.headers, REQUEST_ID_HEADER));
}

export function retryAfterSecondsFromAxiosError(error) {
  const text = String(headerValue(error?.response?.headers, RETRY_AFTER_HEADER) || '').trim();
  if (!/^\d+$/.test(text)) return null;
  const seconds = Number(text);
  if (!Number.isSafeInteger(seconds) || seconds < 0 || seconds > MAX_RETRY_AFTER_SECONDS) return null;
  return seconds;
}

export function appendRequestIdToMessage(message, requestId) {
  const safeRequestId = cleanRequestId(requestId);
  const text = String(message || '').trim();
  if (!safeRequestId || text.includes('문의용 ID:')) return text;
  return `${text || '요청을 처리하지 못했습니다.'} (문의용 ID: ${safeRequestId})`;
}

export function appendRetryAfterToMessage(message, retryAfterSeconds) {
  const text = String(message || '').trim() || '요청을 처리하지 못했습니다.';
  if (!Number.isSafeInteger(retryAfterSeconds) || retryAfterSeconds < 0 || text.includes('뒤 다시 시도')) {
    return text;
  }
  return `${text} ${retryAfterSeconds}초 뒤 다시 시도하세요.`;
}

export function installAxiosRequestIdMessages(axiosInstance) {
  axiosInstance?.interceptors?.response?.use(
    response => response,
    error => {
      const requestId = requestIdFromAxiosError(error);
      const retryAfterSeconds = retryAfterSecondsFromAxiosError(error);
      if (requestId && error?.response?.data && typeof error.response.data === 'object') {
        error.response.data.detail = appendRequestIdToMessage(
          appendRetryAfterToMessage(error.response.data.detail, retryAfterSeconds),
          requestId,
        );
      } else if (error?.response?.data && typeof error.response.data === 'object') {
        error.response.data.detail = appendRetryAfterToMessage(error.response.data.detail, retryAfterSeconds);
      } else if (error) {
        error.message = appendRequestIdToMessage(
          appendRetryAfterToMessage(error.message, retryAfterSeconds),
          requestId,
        );
      }
      return Promise.reject(error);
    },
  );
}
