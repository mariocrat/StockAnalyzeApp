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
