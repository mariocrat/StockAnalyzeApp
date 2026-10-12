// Test-only executable specification. Never import from src or runtime code.
export function requireContract(ok, message = 'contract violation') {
  if (!ok) throw new Error(message);
}

export function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${stable(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

// Only the explicit JSON Schema vocabulary used by the shared spec is interpreted.
export function schemaCheck(value, rule) {
  requireContract(rule !== false);
  if (rule.oneOf) {
    let matches = 0;
    for (const candidate of rule.oneOf) {
      try { schemaCheck(value, candidate); matches++; } catch { /* other branch */ }
    }
    requireContract(matches === 1, 'oneOf');
    return;
  }
  if ('const' in rule) requireContract(value === rule.const, 'const');
  if (rule.enum) requireContract(rule.enum.includes(value), 'enum');
  if (rule.type === 'object') {
    requireContract(value !== null && typeof value === 'object' && !Array.isArray(value), 'object');
    if (rule.properties) {
      requireContract(stable(Object.keys(value).sort()) === stable([...rule.required].sort()), 'exact keys');
      for (const [key, child] of Object.entries(rule.properties)) schemaCheck(value[key], child);
    }
  } else if (rule.type === 'array') {
    requireContract(Array.isArray(value) && value.length >= rule.minItems && value.length <= rule.maxItems, 'array');
    value.forEach((child, i) => schemaCheck(child, rule.prefixItems ? rule.prefixItems[i] : rule.items));
  } else if (rule.type === 'string') {
    requireContract(typeof value === 'string', 'string');
    const length = [...value].length;
    requireContract(length >= (rule.minLength || 0) && length <= (rule.maxLength ?? Infinity), 'text bounds');
    if (rule.pattern) requireContract(new RegExp(rule.pattern, 'u').exec(value)?.[0] === value, 'pattern');
  }
}

function references(value, rule) {
  if (rule['x-block-ref']) return [value];
  if (rule.type === 'array') return value.flatMap(v => references(v, rule.items));
  if (rule.type === 'object') return rule['x-field-order'].flatMap(k => references(value[k], rule.properties[k]));
  return [];
}

function checkText(text) {
  for (const char of text) {
    const c = char.codePointAt(0);
    requireContract(!(c < 9 || (c > 10 && c < 32) || c === 127 || (c >= 0xD800 && c <= 0xDFFF)), 'character');
  }
}

export const flatten = doc => doc.blocks.map(b => b.runs.map(r => r.text).join('') + b.separator_after).join('');

export function validateV2(doc, schema) {
  schemaCheck(doc, schema);
  const shape = schema.oneOf.find(s => s.properties.review_type.const === doc.review_type);
  const all = [];
  for (let i = 0; i < doc.sections.length; i++) {
    const section = doc.sections[i];
    const refs = references(section, shape.properties.sections.prefixItems[i]);
    requireContract(stable(refs) === stable(section.block_ids), 'field ownership/order');
    all.push(...section.block_ids);
  }
  const ids = doc.blocks.map(b => b.id);
  requireContract(new Set(ids).size === ids.length && new Set(all).size === all.length, 'unique ownership');
  requireContract(stable(ids) === stable(all), 'document ownership/order');
  requireContract(doc.blocks.reduce((n, b) => n + b.runs.length, 0) <= 512, 'run total');
  for (const block of doc.blocks) {
    if (block.type === 'divider') requireContract(block.runs.length === 1 && block.runs[0].type === 'text', 'divider');
    block.runs.forEach(run => checkText(run.text));
    checkText(block.separator_after);
  }
  checkText(doc.canonical_text);
  requireContract(flatten(doc) === doc.canonical_text, 'canonical identity');
  return doc;
}

export function makeBundle(witness, kind = 'paired_v1_v2') {
  const bundle = {schema_version:'review-approval-bundle.v1', kind,
    review_type:witness.source.review_type, status:'ready',
    representations:{v1:{document:structuredClone(witness.expected_v1), summary:witness.expected_summary}}};
  if (kind === 'paired_v1_v2') {
    for (const key of ['source_identity','objective_identity']) bundle[key] = witness[key];
    for (const version of ['v1','v2']) bundle.representations[version] = {
      compiler_version:`review-body.${version}.0`, source_identity:witness.source_identity,
      objective_identity:witness.objective_identity, review_type:witness.source.review_type,
      document:structuredClone(witness[`expected_${version}`]),
      ...(version === 'v1' ? {summary:witness.expected_summary} : {}),
    };
  }
  return bundle;
}

// witness is a separate trusted test oracle, not a field accepted from a record.
// Exact compiler outputs are required in addition to opaque source identity.
export function validateBundle(bundle, witness, schema, validateV1) {
  schemaCheck(bundle, schema.$defs.bundle);
  const v1 = bundle.representations.v1;
  validateV1(v1.document);
  requireContract(v1.summary === witness.expected_summary && stable(v1.document) === stable(witness.expected_v1), 'v1 compiler/A1');
  requireContract(bundle.review_type === witness.source.review_type, 'review type');
  if (bundle.kind === 'paired_v1_v2') {
    validateV2(bundle.representations.v2.document, schema);
    for (const key of ['source_identity','objective_identity']) {
      requireContract(bundle[key] === witness[key], 'source/objective identity');
    }
    for (const [version, rep] of Object.entries(bundle.representations)) {
      requireContract(rep.source_identity === witness.source_identity && rep.objective_identity === witness.objective_identity
        && rep.review_type === bundle.review_type, 'representation provenance');
      requireContract(stable(rep.document) === stable(witness[`expected_${version}`]), 'compiler output/coverage');
    }
  }
  return bundle;
}

export function mutate(base, operations) {
  const result = structuredClone(base);
  for (const op of operations) {
    const target = op.path.reduce((v,k) => v[k], result);
    if (op.op === 'swap') [target[op.left],target[op.right]] = [target[op.right],target[op.left]];
    else if (op.op === 'remove') target.splice(op.index,1);
    else if (op.op === 'reflatten') target.canonical_text = flatten(target);
    else {
      const parent = op.path.slice(0,-1).reduce((v,k) => v[k],result), key = op.path.at(-1);
      if (op.op === 'delete') delete parent[key];
      else { requireContract(op.op === 'set'); parent[key] = structuredClone(op.value); }
    }
  }
  return result;
}

// In-memory state specification only; counters describe modeled effects, not HTTP evidence.
export function replay({capability, sameBody = true, record, witness, schema, validateV1, trace = []}) {
  trace.push('capability_gate');
  requireContract(['v1','dual'].includes(capability), 'unsupported capability');
  trace.push('execution_identity');
  requireContract(sameBody, 'idempotency conflict');
  if (!record) { trace.push('no_replay'); return {kind:'new_execution_requires_normal_gates'}; }
  trace.push('bundle_validation');
  validateBundle(record,witness,schema,validateV1);
  trace.push('representation_selection');
  const version = capability === 'dual' && record.kind === 'paired_v1_v2' ? 'v2' : 'v1';
  trace.push('projection');
  return {version, document:structuredClone(record.representations[version].document), ai:0, charge:0, history_insert:0};
}

export const generation = row => row.phase === 'activation' && row.status === 'ready' && row.body === 'structured'
  ? 'paired_v1_v2' : 'v1_only';
