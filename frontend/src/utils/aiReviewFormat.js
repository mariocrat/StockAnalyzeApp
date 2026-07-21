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

export function normalizeAiReviewTerms(value) {
  return String(value || '')
    .replace(/\bMA\s*(5|10|20|60|120)\b/gi, 'MA$1');
}

export function parseAiReviewDocument(value) {
  const text = normalizeAiReviewTerms(value).replace(/\r\n?/g, '\n').trim();
  if (!text) return [];

  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push({ type: 'paragraph', text: paragraph.join(' ').trim() });
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    blocks.push(list);
    list = null;
  };

  text.split('\n').forEach(rawLine => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2].trim() });
      return;
    }

    if (/^-{3,}$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ type: 'divider' });
      return;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      flushParagraph();
      const orderedList = Boolean(ordered);
      if (!list || list.ordered !== orderedList) {
        flushList();
        list = { type: 'list', ordered: orderedList, items: [] };
      }
      list.items.push((unordered?.[1] || ordered?.[1] || '').trim());
      return;
    }

    flushList();
    paragraph.push(line);
  });

  flushParagraph();
  flushList();
  return blocks;
}
