// Test-only schema interpreter; never import from production.
export class ReferenceContractError extends Error {
  constructor(code) { super(code); this.code = code; }
}
export function requireContract(ok, code = 'contract violation') {
  if (!ok) throw new ReferenceContractError(code);
}
export function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${stable(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}
function exact(value, keys, path) {
  requireContract(value !== null && typeof value === 'object' && !Array.isArray(value), 'INVALID_TYPE');
  requireContract(Object.keys(value).every(k => keys.includes(k)), 'UNKNOWN_KEY');
  const missing = keys.filter(k => !(k in value));
  if (missing.length) {
    const code = path.startsWith('$.blocks[') && missing.includes('id') ? 'MISSING_BLOCK_ID'
      : path === '$.representations' && missing.includes('v1') ? 'V1_MISSING'
      : path === '$.representations' && missing.includes('v2') ? 'V2_MISSING' : 'MISSING_FIELD';
    requireContract(false,code);
  }
}
function scalarCode(path,issue) {
  const suffixes = {role:'WRONG_SECTION_ORDER',compiler_version:'COMPILER_VERSION_MISMATCH',
    schema_version:'INVALID_VERSION',surface:'INVALID_SURFACE',review_type:'INVALID_REVIEW_TYPE',
    status:'INVALID_BUNDLE_STATUS',level:'INVALID_CONFIDENCE',phase:'INVALID_PHASE',
    separator_after:'INVALID_SEPARATOR',id:'INVALID_BLOCK_ID'};
  const field = path.split('.').at(-1);
  if (suffixes[field]) return suffixes[field];
  if (field === 'type') return path.includes('.runs[') ? 'INVALID_RUN_TYPE' : 'INVALID_BLOCK_TYPE';
  if (field.endsWith('_identity')) return 'INVALID_IDENTITY';
  return issue === 'pattern' ? 'INVALID_REFERENCE' : 'INVALID_TYPE';
}
export function schemaCheck(value,rule,path='$') {
  requireContract(rule !== false,'INVALID_TYPE');
  if (rule.oneOf) {
    requireContract(value !== null && typeof value === 'object' && !Array.isArray(value),'INVALID_TYPE');
    const discriminator = rule.oneOf.some(r => 'kind' in r.properties) ? 'kind' : 'review_type';
    const match = rule.oneOf.find(r => value[discriminator] === r.properties[discriminator].const);
    requireContract(Boolean(match),discriminator === 'kind' ? 'INVALID_BUNDLE_KIND' : 'INVALID_REVIEW_TYPE');
    schemaCheck(value,match,path); return;
  }
  if ('const' in rule) requireContract(value === rule.const,scalarCode(path,'const'));
  if (rule.enum) requireContract(rule.enum.includes(value),scalarCode(path,'enum'));
  if (rule.type === 'object') {
    requireContract(value !== null && typeof value === 'object' && !Array.isArray(value),'INVALID_TYPE');
    if (rule.properties) {
      exact(value,rule.required,path);
      for (const [k,child] of Object.entries(rule.properties)) schemaCheck(value[k],child,path+'.'+k);
    }
  } else if (rule.type === 'array') {
    requireContract(Array.isArray(value),path.endsWith('.missing_information') ? 'INVALID_MISSING_INFORMATION' : 'INVALID_TYPE');
    requireContract(value.length >= rule.minItems && value.length <= rule.maxItems,path === '$.sections' ? 'WRONG_SECTION_ORDER' : 'LIMIT_EXCEEDED');
    value.forEach((child,i) => schemaCheck(child,rule.prefixItems ? rule.prefixItems[i] : rule.items,`${path}[${i}]`));
  } else if (rule.type === 'string') {
    requireContract(typeof value === 'string',rule['x-block-ref'] ? 'INVALID_REFERENCE' : 'INVALID_TYPE');
    requireContract([...value].length >= (rule.minLength||0) && [...value].length <= (rule.maxLength??Infinity),'LIMIT_EXCEEDED');
    if (rule.pattern) requireContract(new RegExp(rule.pattern,'u').exec(value)?.[0] === value,scalarCode(path,'pattern'));
  }
}
function references(value,rule) {
  if (rule['x-block-ref']) return [value];
  if (rule.type === 'array') return value.flatMap(v => references(v,rule.items));
  if (rule.type === 'object') return rule['x-field-order'].flatMap(k => references(value[k],rule.properties[k]));
  return [];
}
function checkText(text) {
  for (const ch of text) {
    const c=ch.codePointAt(0);
    requireContract(!(c<9 || (c>10 && c<32) || c===127 || (c>=0xD800 && c<=0xDFFF)),'INVALID_UNICODE');
  }
}
export const flatten = doc => doc.blocks.map(b => b.runs.map(r => r.text).join('')+b.separator_after).join('');
export function validateV2(doc,schema) {
  exact(doc,['schema_version','surface','review_type','blocks','sections','canonical_text'],'$');
  requireContract(doc.schema_version === 'review-display.v2','INVALID_VERSION');
  requireContract(doc.surface === 'body','INVALID_SURFACE');
  const shape=schema.oneOf.find(s => s.properties.review_type.const === doc.review_type);
  requireContract(Boolean(shape),'INVALID_REVIEW_TYPE');
  const rules=shape.properties.sections.prefixItems;
  requireContract(Array.isArray(doc.sections),'INVALID_TYPE');
  requireContract(doc.sections.length === rules.length,'WRONG_SECTION_ORDER');
  const roles = schema.oneOf.flatMap(s => s.properties.sections.prefixItems.map(r => r.properties.role.const));
  doc.sections.forEach((section,i) => {
    requireContract(section !== null && typeof section === 'object' && !Array.isArray(section),'INVALID_TYPE');
    requireContract(roles.includes(section.role),'UNKNOWN_ROLE');
    requireContract(section.role === rules[i].properties.role.const,'WRONG_SECTION_ORDER');
  });
  schemaCheck(doc,schema);
  const ids=doc.blocks.map(b => b.id), owned=doc.sections.flatMap(s => s.block_ids);
  requireContract(new Set(ids).size === ids.length,'DUPLICATE_BLOCK_ID');
  requireContract(doc.blocks.reduce((n,b) => n+b.runs.length,0)<=512,'LIMIT_EXCEEDED');
  for (const block of doc.blocks) {
    if (block.type==='divider') requireContract(block.runs.length===1 && block.runs[0].type==='text','INVALID_DIVIDER');
    block.runs.forEach(r => checkText(r.text));
  }
  requireContract(new Set(owned).size===owned.length,'DUPLICATE_OWNERSHIP');
  requireContract(owned.every(id => ids.includes(id)),'MISSING_BLOCK_REFERENCE');
  requireContract(ids.every(id => owned.includes(id)),'ORPHAN_BLOCK');
  doc.sections.forEach((section,i) => {
    const refs=references(section,rules[i]);
    requireContract(refs.every(id => ids.includes(id)),'MISSING_BLOCK_REFERENCE');
    requireContract(new Set(refs).size===refs.length,'DUPLICATE_BLOCK_REFERENCE');
    requireContract(refs.every(id => section.block_ids.includes(id)),'FOREIGN_SECTION_REFERENCE');
    requireContract(stable(refs)===stable(section.block_ids),'WRONG_REFERENCE_ORDER');
  });
  requireContract(stable(ids)===stable(owned),'WRONG_BLOCK_ORDER');
  checkText(doc.canonical_text);
  requireContract(flatten(doc)===doc.canonical_text,'CANONICAL_TEXT_MISMATCH');
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
export function validateBundle(bundle,witness,schema,validateV1) {
  schemaCheck(bundle,schema.$defs.bundle);
  const v1=bundle.representations.v1;
  try { validateV1(v1.document); } catch (error) {
    if (error.constructor !== Error) throw error;
    throw new ReferenceContractError('V1_DOCUMENT_INVALID');
  }
  requireContract(v1.summary===witness.expected_summary,'A1_SUMMARY_MISMATCH');
  requireContract(bundle.review_type===witness.source.review_type,'REVIEW_TYPE_MISMATCH');
  if (bundle.kind==='paired_v1_v2') {
    validateV2(bundle.representations.v2.document,schema);
    for (const rep of Object.values(bundle.representations)) {
      requireContract(rep.review_type===bundle.review_type,'REVIEW_TYPE_MISMATCH');
      requireContract(rep.source_identity===bundle.source_identity,'SOURCE_IDENTITY_MISMATCH');
      requireContract(rep.objective_identity===bundle.objective_identity,'OBJECTIVE_IDENTITY_MISMATCH');
    }
    requireContract(bundle.source_identity===witness.source_identity,'SOURCE_IDENTITY_MISMATCH');
    requireContract(bundle.objective_identity===witness.objective_identity,'OBJECTIVE_IDENTITY_MISMATCH');
  }
  for (const [version,rep] of Object.entries(bundle.representations))
    requireContract(stable(rep.document)===stable(witness[`expected_${version}`]),'COMPILER_OUTPUT_MISMATCH');
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
