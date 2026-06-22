const SECRET_KEY_PARTS = [
  'authorization',
  'code',
  'password',
  'private',
  'purchasetoken',
  'purchase_token',
  'secret',
  'signature',
  'token',
];
const AUTH_STORAGE_KEY = 'alphamate.devAuth.v1';

function isSecretKey(key) {
  const normalized = String(key || '').toLowerCase().replace(/[^a-z0-9_]/g, '');
  return SECRET_KEY_PARTS.some(part => normalized.includes(part));
}

function redactDetails(value) {
  if (Array.isArray(value)) return value.slice(0, 50).map(redactDetails);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        isSecretKey(key) ? '[redacted]' : redactDetails(item),
      ]),
    );
  }
  if (['string', 'number', 'boolean'].includes(typeof value) || value == null) return value;
  return String(value);
}

function cleanText(value, fallback, limit) {
  const text = String(value || '').trim();
  return (text || fallback).slice(0, limit);
}

function errorName(error) {
  return cleanText(error?.name || error?.constructor?.name || 'Error', 'Error', 80);
}

function rejectionMessage(reason) {
  if (reason instanceof Error) return reason.message;
  return typeof reason === 'string' ? reason : 'Unhandled promise rejection';
}

export function buildClientEventPayload({
  eventType = 'client_event',
  level = 'warning',
  message = '',
  path = '',
  details = {},
} = {}) {
  return {
    event_type: cleanText(eventType, 'client_event', 120),
    level: cleanText(level, 'warning', 20),
    message: cleanText(message, '', 500),
    path: cleanText(path, '/client', 200),
    details: redactDetails(details || {}),
  };
}

export async function reportClientEvent({
  apiBase,
  sessionToken = '',
  eventType,
  level = 'warning',
  message = '',
  path = '',
  details = {},
  post = fetch,
} = {}) {
  if (!apiBase || typeof post !== 'function') return;

  const headers = { 'Content-Type': 'application/json' };
  if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`;

  try {
    await post(`${apiBase}/api/client-events`, JSON.stringify(buildClientEventPayload({
      eventType,
      level,
      message,
      path,
      details,
    })), {
      method: 'POST',
      headers,
    });
  } catch {
    // Client-side logging must never block the user's original action.
  }
}

export function getStoredAuthSessionToken(storage = typeof localStorage !== 'undefined' ? localStorage : undefined) {
  try {
    const raw = storage?.getItem?.(AUTH_STORAGE_KEY);
    if (!raw) return '';
    const session = JSON.parse(raw);
    return cleanText(session?.session_token, '', 500);
  } catch {
    return '';
  }
}

export function installGlobalClientEventReporting({
  apiBase,
  getSessionToken = () => '',
  targetWindow = typeof window !== 'undefined' ? window : undefined,
  post = fetch,
} = {}) {
  if (!targetWindow || !apiBase) return () => {};

  const reported = new Set();
  const currentPath = () => targetWindow.location?.pathname || '/client';
  const reportOnce = async (eventType, message, details) => {
    if (reported.has(eventType)) return;
    reported.add(eventType);
    await reportClientEvent({
      apiBase,
      sessionToken: getSessionToken(),
      eventType,
      level: 'error',
      message,
      path: currentPath(),
      details,
      post,
    });
  };

  const onError = (event = {}) => reportOnce(
    'client_unhandled_error',
    event.message || 'Unhandled client error',
    {
      filename: event.filename || '',
      lineno: event.lineno || 0,
      colno: event.colno || 0,
      error_name: errorName(event.error),
    },
  );
  const onUnhandledRejection = (event = {}) => reportOnce(
    'client_unhandled_rejection',
    rejectionMessage(event.reason),
    {
      reason_name: errorName(event.reason),
    },
  );

  targetWindow.addEventListener('error', onError);
  targetWindow.addEventListener('unhandledrejection', onUnhandledRejection);

  return () => {
    targetWindow.removeEventListener?.('error', onError);
    targetWindow.removeEventListener?.('unhandledrejection', onUnhandledRejection);
  };
}
