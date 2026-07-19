function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function hashText(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export function createAiReviewRequestNonce(nowMs = Date.now()) {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (randomUuid) return randomUuid;
  return `${Number(nowMs || 0)}-${Math.random().toString(36).slice(2)}`;
}

export function buildAiReviewIdempotencyKey({
  trades,
  reviewType,
  targetTradeId = '',
  requestNonce = createAiReviewRequestNonce(),
}) {
  const payload = stableStringify({
    reviewType: reviewType || 'basic',
    targetTradeId: targetTradeId || '',
    trades: trades || [],
    requestNonce,
  });
  return `ai-review-${hashText(payload)}-${hashText(String(requestNonce))}`;
}
