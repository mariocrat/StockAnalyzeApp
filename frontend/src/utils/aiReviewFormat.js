const SECTION_LABELS = {
  verdict: /^(?:총평)$/,
  strength: /^(?:잘한\s*점)$/,
  weakness: /^(?:아쉬운\s*점)$/,
  checklist: /^(?:다음\s*체크리스트(?:\s*3개)?)$/,
};

function sectionKey(label) {
  const normalized = String(label || '').replace(/\s+/g, ' ').trim();
  return Object.entries(SECTION_LABELS).find(([, pattern]) => pattern.test(normalized))?.[0] || '';
}

function numberedItems(text) {
  const source = String(text || '').trim();
  if (!source) return [];

  const matches = [...source.matchAll(/(?:^|\s)(\d+)[.)]\s*/g)];
  if (!matches.length) return [source];

  return matches.map((match, index) => {
    const start = Number(match.index || 0) + match[0].length;
    const end = index + 1 < matches.length ? Number(matches[index + 1].index || source.length) : source.length;
    return source.slice(start, end).trim();
  }).filter(Boolean);
}

export function parseAiReviewSummary(value) {
  const text = String(value || '').replace(/\r\n?/g, '\n').trim();
  const empty = { structured: false, text: '', verdict: '', strength: '', weakness: '', checklist: [] };
  if (!text) return empty;

  const labelPattern = /(총평|잘한\s*점|아쉬운\s*점|다음\s*체크리스트(?:\s*3개)?)\s*[:：]\s*/g;
  const matches = [...text.matchAll(labelPattern)];
  if (!matches.length) return { ...empty, text };

  const sections = {};
  matches.forEach((match, index) => {
    const key = sectionKey(match[1]);
    if (!key) return;
    const start = Number(match.index || 0) + match[0].length;
    const end = index + 1 < matches.length ? Number(matches[index + 1].index || text.length) : text.length;
    sections[key] = text.slice(start, end).trim();
  });

  const structured = Boolean(sections.verdict || sections.strength || sections.weakness || sections.checklist);
  return {
    structured,
    text,
    verdict: sections.verdict || '',
    strength: sections.strength || '',
    weakness: sections.weakness || '',
    checklist: numberedItems(sections.checklist),
  };
}
