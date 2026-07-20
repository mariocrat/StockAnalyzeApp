import test from 'node:test';
import assert from 'node:assert/strict';

import { parseAiReviewSummary } from '../src/utils/aiReviewFormat.js';

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
