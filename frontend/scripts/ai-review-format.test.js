import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { normalizeAiReviewTerms, parseAiReviewDocument, parseAiReviewSummary } from '../src/utils/aiReviewFormat.js';

test('splits a dense general review into readable sections and checklist items', () => {
  const parsed = parseAiReviewSummary(
    '총평: 짧게 수익을 확정한 매매입니다. 잘한 점: 평균단가보다 높은 가격에 매도했습니다. '
    + '아쉬운 점: 일부 물량을 더 관찰할 여지가 있었습니다. 다음 체크리스트 3개: '
    + '1) 매수 전 손절가 정하기 2) 분할매수 기준 확인하기 3) 매도 후 5개 봉 기록하기',
  );

  assert.equal(parsed.structured, true);
  assert.equal(parsed.verdict, '짧게 수익을 확정한 매매입니다.');
  assert.match(parsed.strength, /평균단가/);
  assert.match(parsed.weakness, /일부 물량/);
  assert.deepEqual(parsed.checklist, [
    '매수 전 손절가 정하기',
    '분할매수 기준 확인하기',
    '매도 후 5개 봉 기록하기',
  ]);
});

test('keeps legacy unstructured review text as a safe fallback', () => {
  const parsed = parseAiReviewSummary('기존 복기 내용입니다.');

  assert.equal(parsed.structured, false);
  assert.equal(parsed.text, '기존 복기 내용입니다.');
});

test('turns an advanced markdown review into readable blocks', () => {
  const blocks = parseAiReviewDocument(
    '## 1. 반복 패턴\n\n**전량 매도**가 빨랐습니다.\n\n- MA5 위에서 매도\n- MA20도 상승 중\n\n---\n\n### 다음 규칙\n\n1. 손절가를 먼저 정합니다.',
  );

  assert.deepEqual(blocks.map(block => block.type), [
    'heading',
    'paragraph',
    'list',
    'divider',
    'heading',
    'list',
  ]);
  assert.equal(blocks[2].items[0], 'MA5 위에서 매도');
  assert.equal(blocks[2].items[1], 'MA20도 상승 중');
  assert.equal(blocks[5].ordered, true);
});

test('uses compact MA labels in review copy', () => {
  assert.equal(
    normalizeAiReviewTerms('MA5 7,014원 > MA20 6,573원, MA 10 확인'),
    'MA5 7,014원 > MA20 6,573원, MA10 확인',
  );
});


test('canonical basic single newline sections keep all legacy checklist boundaries', () => {
  const summary = '총평: 체결 기록을 확인합니다.\n잘한 점: 체결 비교\n아쉬운 점: 기준 확인\n다음 체크리스트: 1) 진입 이유 2) 보유 근거 3) 매도 이유';
  const parsed = parseAiReviewSummary(summary);
  assert.deepEqual([parsed.verdict, parsed.strength, parsed.weakness], ['체결 기록을 확인합니다.', '체결 비교', '기준 확인']);
  assert.deepEqual(parsed.checklist, ['진입 이유', '보유 근거', '매도 이유']);
});

test('canonical advanced blank line sections remain separate in the unchanged parser', () => {
  const sections = ['이번 매매 판단: 체결 기록을 확인합니다.', '진입 가설 검토: 근거 확인', '위험 관리 검토: 사전 기준', '매수·매도 대응: 당시 대응', '상세 분석: 체결 흐름', '다음 매매 체크: 진입 전 / 보유 중 / 매도 전', '이번에 배울 점: 판단과 결과', '다음 복기 질문: 당시 근거는 무엇인가?'];
  assert.deepEqual(parseAiReviewDocument(sections.join('\n\n')), sections.map(text => ({ type: 'paragraph', text })));
});

test('canonical advanced fallback contract renders four unchanged sections', () => {
  // Shared fixed contract: Python builders assert their sealed body and exact
  // compatibility summary equal these bytes before this actual parser check.
  const fixture = JSON.parse(readFileSync(new URL('./fixtures/review-compatibility-v1.json', import.meta.url), 'utf8'));
  assert.equal(fixture.contract, 'phase2c-advanced-fallback-double-newline');
  for (const vector of fixture.cases) {
    assert.deepEqual(vector.legacy_summary.split('\n'), vector.sections);
    assert.deepEqual(vector.summary.split('\n\n'), vector.sections);
    const blocks = parseAiReviewDocument(vector.summary);
    assert.equal(blocks.length, 4, vector.id);
    assert.deepEqual(blocks, vector.sections.map(text => ({ type: 'paragraph', text })), vector.id);
  }
});
