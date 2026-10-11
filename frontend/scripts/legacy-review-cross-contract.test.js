import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

import { normalizeAiReviewTerms, parseAiReviewDocument, parseAiReviewSummary } from '../src/utils/aiReviewFormat.js';
import CanonicalReviewRenderer from '../src/components/CanonicalReviewRenderer.js';
import { nodeEvidence, renderEvidence } from './review-render-evidence.js';

const vectorBytes = readFileSync(new URL('./fixtures/review-legacy-compatibility-v1.json', import.meta.url));
const vectors = JSON.parse(vectorBytes.toString('utf8'));
// Required actual backend output, generated in a fresh H4 Python child by the
// coordinator. There is deliberately no fallback to fixture expected values.
const handoff = JSON.parse(readFileSync(new URL('./fixtures/generated-review-legacy-admissions.json', import.meta.url), 'utf8'));
const admissions = new Map(handoff.admissions.map(record => [record.id, record]));

// Legacy compatibility stays a wire/parser contract. Production React consumes
// the approved document directly; no archived or cloned legacy renderer.
const source = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const sourceFile = ts.createSourceFile('TradingJournal.jsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
assert.deepEqual(sourceFile.parseDiagnostics, []);
const names = ['reviewDisplayText', 'ReviewInlineText', 'AiReviewSummary'];
function renderCanonical(document) {
  const result = renderEvidence(renderToStaticMarkup(React.createElement(CanonicalReviewRenderer, { document })));
  const paragraphs = result.dom.children[0].children.filter(node => node.block).map(node => {
    const evidence = nodeEvidence(node);
    return { text: evidence.text, strong: evidence.strongRanges };
  });
  assert.equal(result.text, document.canonical_text);
  return { ...result, paragraphs, visibleText: paragraphs.map(p => p.text).join('') };
}

function renderAdmitted(admission, render) {
  // Only actual backend success can cross into a frontend execution path.
  if (admission.status === 'rejected') {
    assert.equal(Object.hasOwn(admission, 'summary'), false);
    return null;
  }
  assert.equal(admission.status, 'success');
  return render(admission.summary);
}

function assertRendered(vector, result) {
  assert.equal(result.paragraphs.length, vector.expected_paragraphs.length, vector.id);
  assert.deepEqual(result.paragraphs, vector.expected_paragraphs, vector.id);
  assert.equal(result.visibleText, vector.expected_visible_text, vector.id);
  // Canonical block nodes and explicit separators both survive actual React.
  assert.equal(result.paragraphs.map(p => p.text).join('\n\n'), vector.document.canonical_text, vector.id);
}

test('actual Python admissions match all fixed success and rejection expectations', () => {
  assert.equal(vectors.contract, 'review-legacy-compatibility.v1');
  assert.equal(vectors.offset_unit, 'unicode_codepoint');
  assert.equal(handoff.contract, vectors.contract);
  assert.equal(handoff.vector_sha256, createHash('sha256').update(vectorBytes).digest('hex'));
  assert.equal(handoff.passed, true);
  assert.equal(handoff.unexpected, 0);
  assert.equal(handoff.restored, true);
  assert.equal(handoff.patches_restored, true);
  assert.deepEqual(handoff.counts, { success: 10, rejected: 65 });
  assert.equal(vectors.pass.length, 10);
  assert.equal(vectors.fail.length, 65);
  assert.equal(admissions.size, 75);
  assert.deepEqual(handoff.admissions.map(r => r.id), [...vectors.pass, ...vectors.fail].map(v => v.id));
  for (const vector of vectors.pass) {
    assert.deepEqual(admissions.get(vector.id), { id: vector.id, status: 'success', summary: vector.expected_summary });
    // Verify the independently fixed expectations also describe the input AST,
    // including separate adjacent strong runs. This only reads AST metadata;
    // it does not parse wire or implement a frontend renderer.
    const astParagraphs = vector.document.blocks.map(block => {
      let text = '';
      const strong = [];
      for (const run of block.runs) {
        const start = Array.from(text).length;
        text += run.text;
        if (run.type === 'strong') strong.push({ start, end: Array.from(text).length, text: run.text });
      }
      return { text, strong };
    });
    assert.deepEqual(astParagraphs, vector.expected_paragraphs, vector.id);
  }
  for (const vector of vectors.fail) {
    assert.deepEqual(admissions.get(vector.id), { id: vector.id, status: 'rejected', code: vector.expected_rejection });
  }
});

test('production journal has no legacy summary parser or inline renderer dependency', () => {
  assert.equal(ts.version, '4.2.4');
  for (const name of [...names, 'aiReviewFormat']) assert.ok(!source.includes(name));
  assert.equal(typeof CanonicalReviewRenderer, 'function');
});

test('admitted compatibility wires remain identity inputs to the unchanged legacy parser', () => {
  for (const vector of vectors.pass) renderAdmitted(admissions.get(vector.id), summary => {
    assert.equal(normalizeAiReviewTerms(summary), vector.expected_summary, vector.id);
    const parsedSummary = parseAiReviewSummary(summary);
    assert.equal(parsedSummary.structured, false, vector.id);
    assert.equal(parsedSummary.text, vector.expected_summary, vector.id);
    const blocks = parseAiReviewDocument(parsedSummary.text);
    assert.equal(blocks.length, vector.expected_paragraphs.length, vector.id);
    assert.deepEqual(blocks, vector.expected_summary.split('\n\n').map(text => ({ type: 'paragraph', text })), vector.id);
  });
});

test('every backend admitted body preserves block order text and exact strong in canonical React', () => {
  for (const vector of vectors.pass) {
    renderAdmitted(admissions.get(vector.id), summary => {
      assert.equal(summary, vector.expected_summary);
      assertRendered(vector, renderCanonical(vector.document));
    });
  }
});

test('normal strong survives compatibility admission and the canonical React renderer', () => {
  const vector = vectors.pass.find(v => v.id === 'normal_strong');
  renderAdmitted(admissions.get(vector.id), summary => {
    assert.equal(summary, '**체결 기록**을 확인합니다.');
    assert.notEqual(summary, vector.document.canonical_text);
    const full = renderCanonical(vector.document);
    assertRendered(vector, full);
    assert.deepEqual(full.paragraphs[0].strong, [{ start: 0, end: 5, text: '체결 기록' }]);
    assert.deepEqual(full.strongRanges, [{ start: 0, end: 5, text: '체결 기록' }]);
  });
});

test('multiple adjacent and mid word strong elements retain individual ranges', () => {
  for (const id of ['multiple_text_strong', 'adjacent_strong', 'mid_word_strong']) {
    const vector = vectors.pass.find(v => v.id === id);
    renderAdmitted(admissions.get(id), () => assertRendered(vector, renderCanonical(vector.document)));
  }
});

test('advanced fallback shapes preserve all four paragraph nodes and their order', () => {
  for (const vector of vectors.pass.filter(v => v.id.startsWith('advanced_fallback_'))) {
    renderAdmitted(admissions.get(vector.id), summary => {
      assert.equal(summary, vector.expected_summary);
      const rendered = renderCanonical(vector.document);
      assert.equal(rendered.paragraphs.length, 4);
      assertRendered(vector, rendered);
    });
  }
});

test('P1 counterexamples are actual backend rejections with zero frontend executions', () => {
  const expected = [
    ['p1_lone_star', '현재는 매**수** 추천합니다. *'],
    ['p1_link', '현재는 매**수** 추천합니다. [참고](url)'],
  ];
  let frontendCalls = 0;
  for (const [id, wire] of expected) {
    assert.equal(vectors.fail.find(v => v.id === id).forbidden_wire, wire);
    assert.equal(admissions.get(id).status, 'rejected');
    assert.equal(renderAdmitted(admissions.get(id), () => {
      frontendCalls += 1;
      return renderCanonical(vectors.fail.find(v => v.id === id).document);
    }), null);
  }
  assert.equal(frontendCalls, 0);
});

test('all forbidden patterns including split run bypasses are gated before any frontend call', () => {
  let frontendCalls = 0;
  for (const vector of vectors.fail) {
    assert.equal(admissions.get(vector.id).status, 'rejected', vector.id);
    assert.equal(renderAdmitted(admissions.get(vector.id), () => {
      frontendCalls += 1;
      return renderCanonical(vector.document);
    }), null, vector.id);
  }
  assert.equal(frontendCalls, 0);
});

test('MA and basic section tokens cannot bypass admission across paragraph boundaries', () => {
  const cases = vectors.fail.filter(v => v.id.startsWith('paragraph_boundary_'));
  assert.equal(cases.length, 5);
  for (const vector of cases) {
    assert.equal(admissions.get(vector.id).status, 'rejected');
    assert.equal(renderAdmitted(admissions.get(vector.id), () => assert.fail('frontend must not run')), null);
  }
});

test('Unicode codepoint offsets and ordinary punctuation survive actual React output', () => {
  for (const id of ['unicode_sequence', 'ordinary_punctuation', 'ordered_paragraph_strong']) {
    const vector = vectors.pass.find(v => v.id === id);
    renderAdmitted(admissions.get(id), () => assertRendered(vector, renderCanonical(vector.document)));
  }
});
