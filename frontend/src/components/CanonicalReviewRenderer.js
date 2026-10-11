import React from 'react';

// The Node H4 runner imports this same production component without a JSX loader.
const VERSION = 'review-display.v1';
const SURFACES = new Set([
  'body', 'chart_card', 'chart_header', 'chart_tab', 'marker_label',
  'marker_tooltip', 'history_title', 'trade_name', 'notice',
]);
const BLOCK_TYPES = new Set(['heading', 'paragraph', 'list_item', 'divider']);
const RUN_TYPES = new Set(['text', 'strong']);
const UNAVAILABLE = '복기 내용을 표시할 수 없습니다.';

function exactKeys(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

function checkedText(value, limit, allowEmpty = false) {
  if (typeof value !== 'string' || (!allowEmpty && !value)) throw new Error('invalid text');
  let count = 0;
  for (const char of value) {
    const code = char.codePointAt(0);
    if (++count > limit || code < 9 || (code > 10 && code < 32) || code === 127
        || (code >= 0xD800 && code <= 0xDFFF)) throw new Error('invalid text');
  }
  return value;
}

export function validateReviewDisplay(document, expectedSurface = 'body') {
  if (!exactKeys(document, ['schema_version', 'surface', 'blocks', 'canonical_text'])
      || document.schema_version !== VERSION || !SURFACES.has(expectedSurface)
      || document.surface !== expectedSurface
      || !Array.isArray(document.blocks) || document.blocks.length < 1 || document.blocks.length > 64) {
    throw new Error('invalid review display document');
  }
  const pieces = [];
  let totalRuns = 0;
  let visibleCodepoints = 0;
  for (const block of document.blocks) {
    if (!exactKeys(block, ['type', 'runs', 'separator_after']) || !BLOCK_TYPES.has(block.type)
        || !Array.isArray(block.runs) || block.runs.length < 1 || block.runs.length > 64) {
      throw new Error('invalid review display block');
    }
    totalRuns += block.runs.length;
    if (totalRuns > 512) throw new Error('too many review display runs');
    if (block.type === 'divider' && (block.runs.length !== 1 || block.runs[0]?.type !== 'text')) {
      throw new Error('invalid review display divider');
    }
    for (const run of block.runs) {
      if (!exactKeys(run, ['type', 'text']) || !RUN_TYPES.has(run.type)) {
        throw new Error('invalid review display run');
      }
      const text = checkedText(run.text, 4096);
      visibleCodepoints += [...text].length;
      if (visibleCodepoints > 16384) throw new Error('canonical text too long');
      pieces.push(text);
    }
    const separator = checkedText(block.separator_after, 16, true);
    if ([...separator].some(char => !' \t\n'.includes(char))) throw new Error('invalid separator');
    visibleCodepoints += [...separator].length;
    if (visibleCodepoints > 16384) throw new Error('canonical text too long');
    pieces.push(separator);
  }
  const canonical = checkedText(document.canonical_text, 16384);
  if (pieces.join('') !== canonical) throw new Error('canonical text mismatch');
  return canonical;
}

export default function CanonicalReviewRenderer({ document, expectedSurface = 'body' }) {
  try {
    validateReviewDisplay(document, expectedSurface);
  } catch {
    return React.createElement('span', { role: 'status' }, UNAVAILABLE);
  }
  const children = [];
  document.blocks.forEach((block, blockIndex) => {
    const runs = block.runs.map((run, runIndex) => run.type === 'strong'
      ? React.createElement('strong', { key: runIndex }, run.text)
      : React.createElement(React.Fragment, { key: runIndex }, run.text));
    children.push(React.createElement('span', {
      key: `block-${blockIndex}`,
      'data-review-block': block.type,
      ...(block.type === 'heading' ? { role: 'heading', 'aria-level': 3 } : {}),
      ...(block.type === 'divider' ? { role: 'separator' } : {}),
    }, runs));
    children.push(React.createElement(React.Fragment, { key: `separator-${blockIndex}` }, block.separator_after));
  });
  return React.createElement('span', { className: 'canonical-review-display', style: { whiteSpace: 'pre-wrap' } }, children);
}
