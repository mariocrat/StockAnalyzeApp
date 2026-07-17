const DEFAULT_USER_MESSAGE = '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';

const MESSAGE_RULES = [
  {
    pattern: /publisher data not found|admob|ad unit|reward(?:ed)? ad|advertisement/i,
    message: '광고를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.',
  },
  {
    pattern: /advanced review ticket|required.*advanced|advanced.*ticket/i,
    message: '심화 복기 이용권이 필요합니다. 이용권을 확인해 주세요.',
  },
  {
    pattern: /google play|billing|purchase|product.*not found/i,
    message: '구글 플레이 결제를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  },
  {
    pattern: /unauthori[sz]ed|forbidden|session|access token|auth(?:entication)?/i,
    message: '로그인 정보가 만료되었거나 유효하지 않습니다. 다시 로그인해 주세요.',
  },
  {
    pattern: /rate limit|too many requests|quota exceeded/i,
    message: '요청이 많아 잠시 기다려야 합니다. 잠시 후 다시 시도해 주세요.',
  },
  {
    pattern: /network|failed to fetch|timeout|timed out|bad gateway|service unavailable|\b50[234]\b/i,
    message: '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  },
  {
    pattern: /openai|model.*not found|ai review request/i,
    message: 'AI 복기 분석을 완료하지 못했습니다. 사용한 이용권은 자동으로 복구됩니다.',
  },
];

function cleanUserText(value) {
  return String(value || '')
    .replace(/<https?:\/\/[^>]+>/gi, '')
    .replace(/https?:\/\/\S+/gi, '')
    .replace(/\b(?:request|trace|session|error)[_-]?id\s*[:=]\s*[\w.-]+/gi, '')
    .replace(/\(?문의용 ID\s*:\s*[\w.-]+\)?/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function toKoreanUserMessage(value, fallback = DEFAULT_USER_MESSAGE) {
  const raw = String(value || '').trim();
  if (!raw) return '';

  const cleaned = cleanUserText(raw);
  const containsTechnicalLeak = /publisher data not found|support\.google\.com|stack trace|traceback|\.env/i.test(raw);
  if (/[가-힣]/.test(cleaned) && !containsTechnicalLeak && !/[<>]/.test(cleaned)) {
    return cleaned;
  }

  const matched = MESSAGE_RULES.find(rule => rule.pattern.test(raw));
  if (matched) return matched.message;

  return fallback;
}

export { DEFAULT_USER_MESSAGE };
