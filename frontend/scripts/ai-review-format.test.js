import test from 'node:test';
import assert from 'node:assert/strict';

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
  assert.equal(blocks[2].items[0], '5이평선 위에서 매도');
  assert.equal(blocks[2].items[1], '20이평선도 상승 중');
  assert.equal(blocks[5].ordered, true);
});

test('uses Korean moving-average labels in review copy', () => {
  assert.equal(
    normalizeAiReviewTerms('MA5 7,014원 > MA20 6,573원, MA 10 확인'),
    '5이평선 7,014원 > 20이평선 6,573원, 10이평선 확인',
  );
});
