import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import CanonicalReviewRenderer, { validateReviewDisplay } from '../src/components/CanonicalReviewRenderer.js';
import { renderEvidence } from './review-render-evidence.js';

const vectors = JSON.parse(readFileSync(new URL('./fixtures/review-display-v1.json', import.meta.url), 'utf8'));
const valid = id => vectors.valid.find(vector => vector.id === id);
const unavailable = '복기 내용을 표시할 수 없습니다.';

// Read the HTML produced by the real React server renderer. This extracts DOM
// text and strong nodes; it never compiles or substitutes the component.
function rendered(document, expectedSurface) {
  return renderEvidence(renderToStaticMarkup(React.createElement(CanonicalReviewRenderer, { document, expectedSurface })));
}

test('real React renderer matches every shared valid canonical text exactly', () => {
  assert.equal(vectors.schema_version, 'review-display.v1');
  for (const vector of vectors.valid) {
    assert.equal(validateReviewDisplay(vector.document), vector.expected_canonical_text, vector.id);
    assert.equal(rendered(vector.document).text, vector.expected_canonical_text, vector.id);
  }
});

test('mid-word bold counterexample renders only 수 in strong', () => {
  const result = rendered(valid('mid_word_bold_counterexample').document);
  assert.equal(result.text, '현재는 매수 추천합니다.');
  assert.deepEqual(result.strong, ['수']);
  assert.match(result.html, /현재는 매<strong>수<\/strong> 추천합니다\./);
});

test('normal bold renders exact 체결 기록 strong and following text', () => {
  const result = rendered(valid('normal_bold').document);
  assert.equal(result.text, '체결 기록을 확인합니다.');
  assert.deepEqual(result.strong, ['체결 기록']);
  assert.deepEqual(result.strongRanges, [{ start: 0, end: 5, text: '체결 기록' }]);
  assert.match(result.html, /<strong>체결 기록<\/strong>을 확인합니다\./);
});

test('multiple strong spans keep their text and original order', () => {
  const result = rendered(valid('multiple_strong_spans').document);
  assert.equal(result.text, '진입 후 청산 확인');
  assert.deepEqual(result.strong, ['진입', '청산']);
});

test('block order and explicit list marker divider and separators survive React', () => {
  const vector = valid('block_order_and_explicit_separators');
  const result = rendered(vector.document);
  assert.deepEqual(result.blocks, ['heading', 'list_item', 'divider', 'paragraph']);
  assert.deepEqual(result.strong, ['체결 기록']);
  assert.equal(result.text, '제목\n1. 체결 기록\n───\n결론: 확인했습니다.\n');
  assert.equal(result.text, vector.expected_canonical_text);
});

test('whitespace newline and Unicode sequence remain exact', () => {
  const result = rendered(valid('whitespace_and_newline').document);
  assert.equal(result.text, '앞  \n굵게\t끝');
  assert.deepEqual(result.strong, ['굵게']);
  const document = structuredClone(valid('plain_text').document);
  document.blocks[0].runs[0].text = 'e\u0301 😀';
  document.canonical_text = 'e\u0301 😀';
  assert.equal(rendered(document).text, 'e\u0301 😀');
});

test('React escapes HTML-like text while preserving logical text', () => {
  const vector = valid('html_like_text_is_escaped');
  const result = rendered(vector.document);
  assert.equal(result.text, vector.expected_canonical_text);
  assert.deepEqual(result.strong, ['안전']);
  assert.match(result.html, /&lt;script&gt;&amp;/);
  assert.doesNotMatch(result.html, /<script>/);
});

test('unknown versions types fields and canonical mismatch fail closed', () => {
  for (const vector of vectors.invalid) {
    assert.throws(() => validateReviewDisplay(vector.document), undefined, vector.id);
    const result = rendered(vector.document);
    assert.equal(result.text, unavailable, vector.id);
    assert.deepEqual(result.strong, [], vector.id);
    assert.ok(!result.html.includes(vector.document.canonical_text), vector.id);
  }
});

test('nested structure and bounds fail closed in the actual component', () => {
  const base = valid('plain_text').document;
  const documents = [];
  const extra = structuredClone(base);
  extra.blocks[0].runs[0].style = 'bold';
  documents.push(extra);
  const manyBlocks = structuredClone(base);
  manyBlocks.blocks = Array(65).fill(base.blocks[0]);
  documents.push(manyBlocks);
  const longRun = structuredClone(base);
  longRun.blocks[0].runs[0].text = 'x'.repeat(4097);
  documents.push(longRun);
  const longDocument = structuredClone(base);
  longDocument.blocks = Array.from({ length: 5 }, () => ({
    type: 'paragraph', runs: [{ type: 'text', text: 'x'.repeat(4096) }], separator_after: '',
  }));
  longDocument.canonical_text = 'x'.repeat(4096 * 5);
  documents.push(longDocument);
  const nested = structuredClone(base);
  nested.blocks[0].runs[0].text = { nested: 'x' };
  documents.push(nested);
  for (const document of documents) assert.equal(rendered(document).text, unavailable);
});

test('the same renderer and validator require the explicit approved surface for chart documents', () => {
  for (const surface of ['body', 'chart_card', 'chart_header', 'chart_tab', 'marker_label',
    'marker_tooltip', 'history_title', 'trade_name', 'notice']) {
    const document = { ...structuredClone(valid('plain_text').document), surface };
    assert.equal(validateReviewDisplay(document, surface), document.canonical_text);
    if (surface !== 'body') {
      assert.throws(() => validateReviewDisplay(document));
      assert.equal(rendered(document).text, unavailable);
    }
    const result = rendered(document, surface);
    assert.equal(result.text, document.canonical_text);
    assert.deepEqual(result.strong, []);
    assert.equal(rendered(document, 'unknown').text, unavailable);
    assert.throws(() => validateReviewDisplay(document, 'unknown'));
  }
});
