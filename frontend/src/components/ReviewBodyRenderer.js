import React from 'react';
import CanonicalReviewRenderer, { validateReviewDisplay } from './CanonicalReviewRenderer.js';
import { REVIEW_DISPLAY_V2, validateReviewDisplayV2, ReviewDisplayV2Error } from '../utils/reviewDisplayV2.js';

export function validateReviewBody(document, expectedReviewType = null) {
  if (document?.schema_version === REVIEW_DISPLAY_V2) {
    const canonical = validateReviewDisplayV2(document);
    if (expectedReviewType !== null && document.review_type !== expectedReviewType) {
      throw new ReviewDisplayV2Error('REVIEW_TYPE_MISMATCH');
    }
    return canonical;
  }
  // Unknown/partial v2 never retries v1 or raw structured/summary content.
  return validateReviewDisplay(document);
}

const LABELS = {
  summary: '매매 결과와 판단', data_quality: '데이터 신뢰도', good_points: '잘한 점',
  main_improvement: '가장 아쉬운 점', next_trade_checks: '다음 매매 체크', lesson: '이번에 배울 매매 지식',
  entry_review: '진입 판단', risk_review: '위험 관리', exit_review: '매도 판단',
  detailed_analysis: '매수·매도 대응 상세', next_trade_playbook: '다음 매매 플레이북', reflection_questions: '다음 복기 질문',
};
const PHASES = { before_entry: '진입 전', while_holding: '보유 중', before_exit: '매도 전' };
const CONFIDENCE = { high: '높음', medium: '보통', low: '낮음' };

// All text-bearing IDs below are declared semantic fields. Their traversal has
// already been checked against block_ids and the complete canonical sequence.
function groups(section) {
  switch (section.role) {
    case 'summary': return [
      ['결과', [section.objective.realized_pnl, section.objective.realized_return_pct]],
      ['판단 품질', [section.decision_quality.label, section.decision_quality.explanation]],
      ['핵심 문제', [section.main_issue]], ['다음 매매 행동', [section.next_action]],
    ];
    case 'data_quality': return [
      ['신뢰도', [section.confidence.label, ...section.confidence.reasons]],
      ['정보 부족', section.missing_information],
    ];
    case 'good_points':
    case 'detailed_analysis': return section.items.map(item => [null, [item.title, item.detail]]);
    case 'main_improvement': return [[null, [section.title, section.detail]]];
    case 'next_trade_checks': return section.items.map(item => [PHASES[item.phase], [item.text]]);
    case 'entry_review': return [
      ['판단', [section.assessment.label, section.assessment.explanation]],
      ['진입 근거', section.evidence], ['불확실성', section.uncertainty], ['무효화 기준', [section.invalidation]],
    ];
    case 'risk_review': return [
      ['사전 손절 기준', [section.planned_rule]], ['실제 대응', [section.actual_response]],
      ['판단', [section.assessment.label, section.assessment.explanation]],
    ];
    case 'exit_review': return [
      ['수익 확정', [section.profit_taking_assessment]], ['추세 종료', [section.trend_exit_assessment]],
      ['근거', [section.explanation]],
    ];
    case 'next_trade_playbook': return Object.keys(PHASES).map(phase => [PHASES[phase], section[phase]]);
    case 'lesson': return [
      [null, [section.title]], ['개념', [section.concept]], ['이번 매매에 적용', [section.applied_to_this_trade]],
      ...(Object.hasOwn(section, 'next_trade_application') ? [['다음 매매에 적용', [section.next_trade_application]]] : []),
    ];
    case 'reflection_questions': return section.items.map(id => [null, [id]]);
    default: throw new ReviewDisplayV2Error('UNKNOWN_ROLE');
  }
}

function approvedBlock(block) {
  const runs = block.runs.map((run, index) => run.type === 'strong'
    ? React.createElement('strong', { key: index }, run.text)
    : React.createElement(React.Fragment, { key: index }, run.text));
  return React.createElement('span', { key: block.id, className: 'review-v2-canonical-part' },
    React.createElement('span', { 'data-review-block': block.type, 'data-review-block-id': block.id,
      ...(block.type === 'heading' ? { role: 'heading', 'aria-level': 4 } : {}),
      ...(block.type === 'divider' ? { role: 'separator' } : {}),
    }, runs), block.separator_after);
}

export default function ReviewBodyRenderer({ document, reviewType = null }) {
  try {
    validateReviewBody(document, reviewType);
  } catch {
    return React.createElement('span', { role: 'status' }, '복기 내용을 표시할 수 없습니다.');
  }
  if (document.schema_version !== REVIEW_DISPLAY_V2) {
    return React.createElement(CanonicalReviewRenderer, { document });
  }
  const blocks = new Map(document.blocks.map(block => [block.id, block]));
  const sections = document.sections.filter(section => section.block_ids.length).map(section => {
    const content = groups(section).filter(([, ids]) => ids.length).map(([label, ids], index) =>
      React.createElement('div', { key: index, className: 'review-v2-field' },
        label && React.createElement('span', { className: 'review-v2-shell-label', 'data-review-shell': true }, label),
        React.createElement('div', { className: 'review-v2-content' }, ids.map(id => approvedBlock(blocks.get(id))))));
    const heading = React.createElement('h5', { 'data-review-shell': true }, LABELS[section.role]);
    const confidence = section.role === 'data_quality' ? section.confidence.level : undefined;
    const badge = confidence && React.createElement('span', { className: 'review-v2-confidence',
      'data-review-shell': true }, CONFIDENCE[confidence]);
    if (section.role === 'detailed_analysis') {
      return React.createElement('details', { key: section.role, className: 'review-v2-section',
        'data-review-section': section.role },
      React.createElement('summary', { 'data-review-shell': true }, '상세 근거 보기'), heading, content);
    }
    return React.createElement('section', { key: section.role, className: 'review-v2-section',
      'data-review-section': section.role, 'data-confidence': confidence, 'aria-label': LABELS[section.role] },
    React.createElement('div', { className: 'review-v2-section-heading' }, heading, badge), content);
  });
  return React.createElement('div', { className: 'canonical-review-v2', 'data-review-version': REVIEW_DISPLAY_V2 }, sections);
}
