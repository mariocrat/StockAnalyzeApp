const SECRET_FIELD_IDS = new Set([
  'accesstoken', 'adrewardtoken', 'alphamateadmintoken',
  'alphamatedevadrewardtoken', 'alphamatedevauthtoken',
  'alphamatedevproentitlementtoken', 'alphamateopenaiapikey',
  'alphamatereviewaccesspasswordhash', 'apikey', 'apisecret', 'appsecret',
  'authtoken', 'authorization', 'authorizationcode', 'authorizationheader',
  'bearertoken', 'clientsecret', 'code', 'configuredtoken', 'cookie',
  'cookieheader', 'credential', 'credentials', 'devadtoken', 'devauthtoken',
  'devprotoken', 'entitlementtoken', 'googleplaypurchasetokenencryptionkey',
  'googleplayrtdnsharedtoken', 'googleplayserviceaccountjson', 'idtoken',
  'kakaoclientsecret', 'naverclientsecret', 'oauthclientsecret', 'oauthcode',
  'oauthstate', 'oauthticket', 'openaiapikey', 'password', 'passwordhash',
  'privatekey', 'purchasetoken', 'refreshtoken', 'secret', 'sessiontoken',
  'sharedtoken', 'setcookie', 'signature', 'state', 'ticket', 'token',
  'verificationtoken', 'xalphamatertdntoken', 'xapikey', 'xauthtoken',
]);
const AUTH_STORAGE_KEY = 'alphamate.devAuth.v1';
const HEX_DIGITS = new Set('0123456789abcdefABCDEF');
const KEY_PUNCTUATION = new Set('_.-');
const QUOTES = new Set(['"', "'"]);
const TRUNCATED_MARKER = '[truncated]';

function isAsciiAlphanumeric(character) {
  if (!character) return false;
  const code = character.charCodeAt(0);
  return (code >= 48 && code <= 57)
    || (code >= 65 && code <= 90)
    || (code >= 97 && code <= 122);
}

function keyUnitEnd(text, position) {
  if (position >= text.length) return position;
  const character = text[position];
  if (isAsciiAlphanumeric(character) || KEY_PUNCTUATION.has(character)) return position + 1;
  if (
    character === '%'
    && position + 2 < text.length
    && HEX_DIGITS.has(text[position + 1])
    && HEX_DIGITS.has(text[position + 2])
  ) return position + 3;
  return position;
}

function hasKeyBoundary(text, position) {
  if (position === 0) return true;
  const previous = text[position - 1];
  return !(isAsciiAlphanumeric(previous) || previous === '_' || previous === '%');
}

function assignmentCandidate(text, start) {
  if (!hasKeyBoundary(text, start)) return { candidate: null, advanceTo: start + 1 };

  let position = start;
  if (text[position] === '\\' && QUOTES.has(text[position + 1])) position += 2;
  else if (QUOTES.has(text[position])) position += 1;

  const keyStart = position;
  while (position < text.length) {
    const unitEnd = keyUnitEnd(text, position);
    if (unitEnd === position) break;
    position = unitEnd;
  }
  if (position === keyStart) return { candidate: null, advanceTo: start + 1 };

  const keyEnd = position;
  if (text[position] === '\\' && QUOTES.has(text[position + 1])) position += 2;
  else if (QUOTES.has(text[position])) position += 1;
  while (position < text.length && /\s/.test(text[position])) position += 1;
  if (position >= text.length || !['=', ':'].includes(text[position])) {
    return { candidate: null, advanceTo: Math.max(position, keyEnd, start + 1) };
  }

  position += 1;
  while (position < text.length && /\s/.test(text[position])) position += 1;
  return {
    candidate: { key: text.slice(keyStart, keyEnd), valueStart: position },
    advanceTo: position,
  };
}

function normalizedCredentialKey(key) {
  const text = String(key || '').trim();
  let decoded = text;
  try {
    decoded = decodeURIComponent(text);
  } catch {
    // Malformed percent encoding is not decoded or written back to the source value.
  }
  return decoded.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function isSecretKey(key) {
  const normalized = normalizedCredentialKey(key);
  return SECRET_FIELD_IDS.has(normalized)
    || ['authorization', 'password', 'purchasetoken'].some(prefix => normalized.startsWith(prefix));
}

function lineEnd(text, start) {
  let position = start;
  while (position < text.length && text[position] !== '\r' && text[position] !== '\n') position += 1;
  return position;
}

function quotedValueEnd(text, start, quote) {
  for (let position = start + 1; position < text.length; position += 1) {
    if (text[position] !== quote) continue;
    let backslashes = 0;
    for (let previous = position - 1; previous >= start && text[previous] === '\\'; previous -= 1) {
      backslashes += 1;
    }
    if (backslashes % 2 === 0) return position + 1;
  }
  return text.length;
}

function credentialValueEnd(text, start, normalizedKey) {
  if (start >= text.length) return start;
  if (text.startsWith('\\"', start) || text.startsWith("\\'", start)) {
    return text.length;
  }
  if (text[start] === '"' || text[start] === "'") {
    return quotedValueEnd(text, start, text[start]);
  }
  if (['authorization', 'authorizationheader', 'cookie', 'cookieheader', 'setcookie'].includes(normalizedKey)) {
    return lineEnd(text, start);
  }

  let position = start;
  if (text.slice(position, position + 6).toLowerCase() === 'bearer') {
    position += 6;
    while (position < text.length && /\s/.test(text[position])) position += 1;
  }
  while (position < text.length && !/\s/.test(text[position])) position += 1;
  return position;
}

function boundedResult(text, limit, truncated) {
  if (limit === undefined) return text;
  if (!truncated && text.length <= limit) return text;
  if (limit <= TRUNCATED_MARKER.length) return TRUNCATED_MARKER.slice(0, limit);
  return `${text.slice(0, limit - TRUNCATED_MARKER.length)}${TRUNCATED_MARKER}`;
}

function sanitizeText(value, limit) {
  const rawText = String(value || '');
  const boundedLimit = limit === undefined ? undefined : Math.max(0, Math.trunc(limit));
  const truncated = boundedLimit !== undefined && rawText.length > boundedLimit;
  const text = boundedLimit === undefined ? rawText : rawText.slice(0, boundedLimit);
  const safeParts = [];
  let copiedUntil = 0;
  let position = 0;

  while (position < text.length) {
    const { candidate, advanceTo } = assignmentCandidate(text, position);
    if (!candidate) {
      position = advanceTo;
      continue;
    }

    if (!isSecretKey(candidate.key)) {
      position = advanceTo;
      continue;
    }

    const { valueStart } = candidate;
    const valueEnd = credentialValueEnd(text, valueStart, normalizedCredentialKey(candidate.key));
    safeParts.push(text.slice(copiedUntil, valueStart), '[redacted]');
    copiedUntil = valueEnd;
    position = Math.max(valueEnd, valueStart + 1);
  }

  if (!safeParts.length) return boundedResult(text, boundedLimit, truncated);
  safeParts.push(text.slice(copiedUntil));
  return boundedResult(safeParts.join(''), boundedLimit, truncated);
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
  if (typeof value === 'string') return sanitizeText(value, 1000);
  if (['number', 'boolean'].includes(typeof value) || value == null) return value;
  return sanitizeText(value, 1000);
}

function cleanText(value, fallback, limit) {
  const text = String(value || '').trim();
  return (text || fallback).slice(0, limit);
}

function cleanLogText(value, fallback, limit) {
  const text = sanitizeText(value || '', limit).trim();
  return text || fallback;
}

function errorName(error) {
  return cleanLogText(error?.name || error?.constructor?.name || 'Error', 'Error', 80);
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
    event_type: cleanLogText(eventType, 'client_event', 120),
    level: cleanLogText(level, 'warning', 20),
    message: cleanLogText(message, '', 500),
    path: cleanLogText(path, '/client', 200),
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
    await post(`${apiBase}/api/client-events`, {
      method: 'POST',
      headers,
      body: JSON.stringify(buildClientEventPayload({
        eventType,
        level,
        message,
        path,
        details,
      })),
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
