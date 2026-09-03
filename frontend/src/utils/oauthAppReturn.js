export function parseOAuthAppReturnUrl(rawUrl, expectedScheme = '') {
  if (!rawUrl) return null;

  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    return null;
  }

  const normalizedExpectedScheme = String(expectedScheme || '').trim().replace(/:$/, '').toLowerCase();
  if (normalizedExpectedScheme && url.protocol.toLowerCase() !== `${normalizedExpectedScheme}:`) return null;
  if (url.hostname !== 'oauth') return null;
  const provider = url.pathname.replace(/^\/+/, '').toLowerCase();
  if (!['kakao', 'naver'].includes(provider)) return null;

  return {
    provider,
    ticket: url.searchParams.get('ticket') || '',
    state: url.searchParams.get('state') || '',
    error: url.searchParams.get('error') || '',
  };
}
