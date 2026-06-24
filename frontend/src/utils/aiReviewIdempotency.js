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

export function buildAiReviewIdempotencyKey({ trades, reviewType, targetTradeId = '', nowMs = Date.now() }) {
  const minuteBucket = Math.floor(Number(nowMs || 0) / 60_000);
  const payload = stableStringify({
    reviewType: reviewType || 'basic',
    targetTradeId: targetTradeId || '',
    trades: trades || [],
    minuteBucket,
  });
  return `ai-review-${minuteBucket}-${hashText(payload)}`;
}
