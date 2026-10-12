import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import CanonicalReviewRenderer, { validateReviewDisplay } from '../src/components/CanonicalReviewRenderer.js';
import { renderEvidence } from './review-render-evidence.js';

import { validateV2, validateBundle, makeBundle, mutate, flatten, stable, replay, generation } from './review-display-v2-reference.js';

const v2 = JSON.parse(readFileSync(new URL('./fixtures/review-display-v2-vectors.json',import.meta.url),'utf8'));
const v2Schema = JSON.parse(readFileSync(new URL('./fixtures/review-display-v2.schema.json',import.meta.url),'utf8'));
const witnessFor = id => v2.witnesses.find(w => w.id === id);
function textPaths(value,path) {
  if (typeof value === 'string') return [path];
  if (Array.isArray(value)) return value.flatMap((child,i) => textPaths(child,[...path,i]));
  if (value && typeof value === 'object') return Object.entries(value).flatMap(([k,v]) => textPaths(v,[...path,k]));
  return [];
}


const vectors = JSON.parse(readFileSync(new URL('./fixtures/review-display-v1.json', import.meta.url), 'utf8'));
const valid = id => vectors.valid.find(vector => vector.id === id);
const unavailable = '복기 내용을 표시할 수 없습니다.';

test('v2 shared body vectors enforce exact roles ownership order and bounds', () => {
  for (const witness of v2.witnesses) {
    validateV2(witness.expected_v2, v2Schema);
    assert.throws(() => validateReviewDisplay(witness.expected_v2));
  }
  for (const vector of v2.invalid_documents) {
    assert.throws(() => validateV2(mutate(witnessFor(vector.base).expected_v2, vector.mutations), v2Schema), undefined, vector.id);
  }
  for (const text of ['x'.repeat(4097), String.fromCharCode(0xD800), 'x\r']) {
    const doc = structuredClone(v2.witnesses[0].expected_v2);
    doc.blocks[0].runs[0].text = text;
    doc.canonical_text = flatten(doc);
    assert.throws(() => validateV2(doc, v2Schema));
  }
  const doc = structuredClone(v2.witnesses[0].expected_v2);
  doc.blocks[0].runs[0].text = 'e\u0301 😀';
  doc.canonical_text = flatten(doc);
  assert.deepEqual(validateV2(doc, v2Schema), doc);
});

test('v2 atomic bundles reject either corrupt side without v1 downgrade', () => {
  for (const witness of v2.witnesses) {
    for (const kind of ['v1_only', 'paired_v1_v2']) validateBundle(makeBundle(witness,kind), witness, v2Schema, validateReviewDisplay);
  }
  for (const vector of v2.invalid_bundles) {
    const witness = witnessFor(vector.base);
    assert.throws(() => validateBundle(mutate(makeBundle(witness),vector.mutations), witness, v2Schema, validateReviewDisplay), undefined, vector.id);
  }
  for (const status of ['ready','missing_key','error','empty']) {
    const witness = v2.witnesses[0], bundle = makeBundle(witness,'v1_only');
    bundle.status = status;
    validateBundle(bundle,witness,v2Schema,validateReviewDisplay);
  }
});

test('v2 semantic witnesses cover text slots and backend objective without inference', () => {
  for (const witness of v2.witnesses) {
    const source = witness.source;
    const paths = [...textPaths(source.summary,['summary']), ...textPaths(source[source.review_type],[source.review_type])]
      .filter(p => p.at(-1) !== 'phase' && stable(p) !== stable(['summary','data_confidence','level']));
    assert.deepEqual(witness.bindings.filter(b => b.source_path[0] !== 'objective').map(b => stable(b.source_path)).sort(),
      paths.map(stable).sort());
    assert.deepEqual(witness.bindings.map(b => b.block_id),witness.expected_v2.blocks.map(b => b.id));
    for (const binding of witness.bindings) {
      const value = binding.source_path.reduce((v,k) => v[k],source);
      const block = witness.expected_v2.blocks.find(b => b.id === binding.block_id);
      const field = binding.source_path.at(-1);
      // Fixed synthetic objective expectations, not a production formatter.
      const expected = field === 'realized_pnl' ? '+29,967원' : field === 'realized_return_pct' ? '+1.33%' : value;
      if (field === 'realized_pnl') assert.equal(value,29967);
      if (field === 'realized_return_pct') assert.equal(value,1.33);
      assert.equal(block.runs.map(r => r.text).join(''),expected);
    }
    const quality = witness.expected_v2.sections.find(s => s.role === 'data_quality');
    assert.equal(quality.confidence.level,source.summary.data_confidence.level);
    assert.equal(quality.missing_information.length,source.summary.missing_information.length);
  }
});

test('v2 approval identity binds nontext state even when canonical text is unchanged', () => {
  const witness = v2.witnesses[0], doc = structuredClone(witness.expected_v2);
  doc.sections[1].confidence.level = 'low';
  validateV2(doc,v2Schema);
  assert.equal(doc.canonical_text,witness.expected_v2.canonical_text);
  assert.notEqual(stable(doc),stable(witness.expected_v2));
  const bundle = makeBundle(witness);
  bundle.representations.v2.document = doc;
  assert.throws(() => validateBundle(bundle,witness,v2Schema,validateReviewDisplay));
});

test('v2 replay separates capability from execution and limits expiry guarantees', () => {
  const witness = v2.witnesses[0], args = {witness,schema:v2Schema,validateV1:validateReviewDisplay};
  for (const row of v2.replay) {
    const trace = [];
    const result = replay({...args,capability:row.capability,record:makeBundle(witness,row.kind),trace});
    assert.equal(result.version,row.expected);
    assert.deepEqual([result.ai,result.charge,result.history_insert],[0,0,0]);
    assert.deepEqual(trace,['capability_gate','execution_identity','bundle_validation','representation_selection','projection']);
  }
  for (const capability of ['v3','','v1,dual',['v1','dual'],null]) {
    const trace = [];
    assert.throws(() => replay({...args,capability,record:null,trace}));
    assert.deepEqual(trace,['capability_gate']);
  }
  assert.throws(() => replay({...args,capability:'dual',record:makeBundle(witness),sameBody:false}),/idempotency conflict/);
  assert.deepEqual(replay({...args,capability:'dual',record:null}),{kind:'new_execution_requires_normal_gates'});
  for (const vector of v2.invalid_bundles) {
    const sourceWitness = witnessFor(vector.base), record = mutate(makeBundle(sourceWitness),vector.mutations);
    for (const capability of ['v1','dual']) {
      const trace = [];
      assert.throws(() => replay({...args,witness:sourceWitness,record,capability,trace}),undefined,vector.id);
      assert.ok(!trace.includes('projection'));
    }
  }
  for (const row of v2.generation) assert.equal(generation(row),row.expected);
});


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
