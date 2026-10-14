// Body-only transport admission. Backend approval/ownership remain authoritative.
// This closed grammar mirrors the pinned v2 contract, without importing fixtures.
export const REVIEW_DISPLAY_V2 = 'review-display.v2';
export const BASIC_ROLES = Object.freeze(['summary', 'data_quality', 'good_points',
  'main_improvement', 'next_trade_checks', 'lesson']);
export const ADVANCED_ROLES = Object.freeze(['summary', 'data_quality', 'entry_review',
  'risk_review', 'exit_review', 'detailed_analysis', 'next_trade_playbook', 'lesson', 'reflection_questions']);
const ROLES = new Set([...BASIC_ROLES, ...ADVANCED_ROLES]);
const REF = Symbol('block reference');
const array = (item, min, max, code = 'INVALID_TYPE') => ({ array: item, min, max, code });
const enumeration = (values, code) => ({ values, code });
const quality = { label: REF, explanation: REF };
const card = { title: REF, detail: REF };
const lesson = { title: REF, concept: REF, applied_to_this_trade: REF };
const fields = {
  summary: { objective: { realized_pnl: REF, realized_return_pct: REF },
    decision_quality: quality, main_issue: REF, next_action: REF },
  data_quality: { confidence: { level: enumeration(['high', 'medium', 'low'], 'INVALID_CONFIDENCE'),
    label: REF, reasons: array(REF, 0, 5) }, missing_information: array(REF, 0, 4, 'INVALID_MISSING_INFORMATION') },
  good_points: { items: array(card, 1, 2) },
  main_improvement: card,
  next_trade_checks: { items: array({ phase: enumeration(['before_entry', 'while_holding', 'before_exit'],
    'INVALID_PHASE'), text: REF }, 1, 3) },
  entry_review: { assessment: quality, evidence: array(REF, 1, 4), uncertainty: array(REF, 0, 4), invalidation: REF },
  risk_review: { planned_rule: REF, actual_response: REF, assessment: quality },
  exit_review: { profit_taking_assessment: REF, trend_exit_assessment: REF, explanation: REF },
  detailed_analysis: { items: array(card, 0, 5) },
  next_trade_playbook: { before_entry: array(REF, 1, 3), while_holding: array(REF, 1, 3), before_exit: array(REF, 1, 3) },
  reflection_questions: { items: array(REF, 0, 2) },
};

export class ReviewDisplayV2Error extends Error {
  constructor(code) { super(code); this.code = code; }
}

function requireContract(condition, code) {
  if (!condition) throw new ReviewDisplayV2Error(code);
}

function exact(value, keys) {
  requireContract(value !== null && typeof value === 'object' && !Array.isArray(value), 'INVALID_TYPE');
  requireContract(Object.keys(value).every(key => keys.includes(key)), 'UNKNOWN_KEY');
  requireContract(keys.every(key => Object.hasOwn(value, key)), 'MISSING_FIELD');
}

function identifier(value, code) {
  // JS $ also accepts a final newline: require the entire match explicitly.
  requireContract(typeof value === 'string' && /^[a-z][a-z0-9_-]{0,31}$/.exec(value)?.[0] === value, code);
  return value;
}

function checkedText(value, maximum, empty = false) {
  requireContract(typeof value === 'string', 'INVALID_TYPE');
  requireContract(empty || value.length > 0, 'LIMIT_EXCEEDED');
  let count = 0;
  for (const char of value) {
    requireContract(++count <= maximum, 'LIMIT_EXCEEDED');
    const code = char.codePointAt(0);
    requireContract(!(code < 9 || (code > 10 && code < 32) || code === 127
      || (code >= 0xD800 && code <= 0xDFFF)), 'INVALID_UNICODE');
  }
  return count;
}

function fieldRefs(value, shape) {
  if (shape === REF) return [identifier(value, 'INVALID_REFERENCE')];
  if (Object.hasOwn(shape, 'values')) {
    requireContract(typeof value === 'string' && shape.values.includes(value), shape.code);
    return [];
  }
  if (Object.hasOwn(shape, 'array')) {
    requireContract(Array.isArray(value), shape.code);
    requireContract(value.length >= shape.min && value.length <= shape.max, 'LIMIT_EXCEEDED');
    return value.flatMap(child => fieldRefs(child, shape.array));
  }
  exact(value, Object.keys(shape));
  return Object.keys(shape).flatMap(key => fieldRefs(value[key], shape[key]));
}

const equalOrder = (left, right) => left.length === right.length && left.every((id, index) => id === right[index]);

export function validateReviewDisplayV2(document) {
  exact(document, ['schema_version', 'surface', 'review_type', 'blocks', 'sections', 'canonical_text']);
  requireContract(document.schema_version === REVIEW_DISPLAY_V2, 'INVALID_VERSION');
  requireContract(document.surface === 'body', 'INVALID_SURFACE');
  requireContract(['basic', 'advanced'].includes(document.review_type), 'INVALID_REVIEW_TYPE');
  requireContract(Array.isArray(document.blocks), 'INVALID_TYPE');
  requireContract(document.blocks.length >= 1 && document.blocks.length <= 64, 'LIMIT_EXCEEDED');
  const ids = [], pieces = [];
  let totalRuns = 0, totalChars = 0;
  for (const block of document.blocks) {
    requireContract(block !== null && typeof block === 'object' && !Array.isArray(block), 'INVALID_TYPE');
    requireContract(Object.hasOwn(block, 'id'), 'MISSING_BLOCK_ID');
    exact(block, ['id', 'type', 'runs', 'separator_after']);
    const id = identifier(block.id, 'INVALID_BLOCK_ID');
    requireContract(!ids.includes(id), 'DUPLICATE_BLOCK_ID');
    ids.push(id);
    requireContract(['heading', 'paragraph', 'list_item', 'divider'].includes(block.type), 'INVALID_BLOCK_TYPE');
    requireContract(Array.isArray(block.runs), 'INVALID_TYPE');
    requireContract(block.runs.length >= 1 && block.runs.length <= 64, 'LIMIT_EXCEEDED');
    totalRuns += block.runs.length;
    requireContract(totalRuns <= 512, 'LIMIT_EXCEEDED');
    if (block.type === 'divider') {
      requireContract(block.runs.length === 1 && block.runs[0]?.type === 'text', 'INVALID_DIVIDER');
    }
    for (const run of block.runs) {
      exact(run, ['type', 'text']);
      requireContract(['text', 'strong'].includes(run.type), 'INVALID_RUN_TYPE');
      totalChars += checkedText(run.text, 4096);
      requireContract(totalChars <= 16384, 'LIMIT_EXCEEDED');
      pieces.push(run.text);
    }
    requireContract(typeof block.separator_after === 'string'
      && [...block.separator_after].every(char => ' \t\n'.includes(char)), 'INVALID_SEPARATOR');
    totalChars += checkedText(block.separator_after, 16, true);
    requireContract(totalChars <= 16384, 'LIMIT_EXCEEDED');
    pieces.push(block.separator_after);
  }
  const order = document.review_type === 'basic' ? BASIC_ROLES : ADVANCED_ROLES;
  requireContract(Array.isArray(document.sections), 'INVALID_TYPE');
  requireContract(document.sections.length === order.length, 'WRONG_SECTION_ORDER');
  const owned = [], traversals = [];
  document.sections.forEach((section, index) => {
    requireContract(section !== null && typeof section === 'object' && !Array.isArray(section), 'INVALID_TYPE');
    requireContract(Object.hasOwn(section, 'role'), 'MISSING_FIELD');
    requireContract(ROLES.has(section.role), 'UNKNOWN_ROLE');
    requireContract(section.role === order[index], 'WRONG_SECTION_ORDER');
    const shape = section.role === 'lesson'
      ? { ...lesson, ...(document.review_type === 'advanced' ? { next_trade_application: REF } : {}) }
      : fields[section.role];
    exact(section, ['role', 'block_ids', ...Object.keys(shape)]);
    requireContract(Array.isArray(section.block_ids), 'INVALID_TYPE');
    requireContract(section.block_ids.length <= 64, 'LIMIT_EXCEEDED');
    section.block_ids.forEach(id => identifier(id, 'INVALID_REFERENCE'));
    owned.push(...section.block_ids);
    traversals.push(fieldRefs(Object.fromEntries(Object.keys(shape).map(key => [key, section[key]])), shape));
  });
  requireContract(new Set(owned).size === owned.length, 'DUPLICATE_OWNERSHIP');
  requireContract(owned.every(id => ids.includes(id)), 'MISSING_BLOCK_REFERENCE');
  requireContract(ids.every(id => owned.includes(id)), 'ORPHAN_BLOCK');
  document.sections.forEach((section, index) => {
    const refs = traversals[index];
    requireContract(refs.every(id => ids.includes(id)), 'MISSING_BLOCK_REFERENCE');
    requireContract(new Set(refs).size === refs.length, 'DUPLICATE_BLOCK_REFERENCE');
    requireContract(refs.every(id => section.block_ids.includes(id)), 'FOREIGN_SECTION_REFERENCE');
    requireContract(equalOrder(refs, section.block_ids), 'WRONG_REFERENCE_ORDER');
  });
  requireContract(equalOrder(ids, owned), 'WRONG_BLOCK_ORDER');
  checkedText(document.canonical_text, 16384);
  // Comparison only: never replace canonical_text or compile a repaired body.
  requireContract(pieces.join('') === document.canonical_text, 'CANONICAL_TEXT_MISMATCH');
  return document.canonical_text;
}
