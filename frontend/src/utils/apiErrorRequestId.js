const REQUEST_ID_HEADER = 'x-request-id';
const REQUEST_ID_PATTERN = /^[A-Za-z0-9_.-]{8,80}$/;

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

export function appendRequestIdToMessage(message, requestId) {
  const safeRequestId = cleanRequestId(requestId);
  const text = String(message || '').trim();
  if (!safeRequestId || text.includes('문의용 ID:')) return text;
  return `${text || '요청을 처리하지 못했습니다.'} (문의용 ID: ${safeRequestId})`;
}

export function installAxiosRequestIdMessages(axiosInstance) {
  axiosInstance?.interceptors?.response?.use(
    response => response,
    error => {
      const requestId = requestIdFromAxiosError(error);
      if (requestId && error?.response?.data && typeof error.response.data === 'object') {
        error.response.data.detail = appendRequestIdToMessage(error.response.data.detail, requestId);
      } else if (requestId && error) {
        error.message = appendRequestIdToMessage(error.message, requestId);
      }
      return Promise.reject(error);
    },
  );
}
