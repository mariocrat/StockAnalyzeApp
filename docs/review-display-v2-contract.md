# review-display.v2 body and approval contract — Slice 1

## Status and authority

Executable specification only, 2026-10-12. No runtime v2 support, new API header,
storage format, compiler, renderer or flag is activated by this slice.
The exact closed schema is
[review-display-v2.schema.json](../frontend/scripts/fixtures/review-display-v2.schema.json);
shared examples and negative mutations are
[review-display-v2-vectors.json](../frontend/scripts/fixtures/review-display-v2-vectors.json).
The Python/JavaScript reference helpers interpret the same schema. Their scope is
decoded JSON plus invariants below, not a general JSON Schema engine or a security seal.
A passing display contract does not replace source admission, safety, consent,
ownership or entitlement approval. Existing v1 admission remains unchanged.

## Exact body document

All keys below are required; unknown keys at every nesting level reject.
JSON object member order is immaterial. Array order is significant.
No title, notice, chart, HTML, style, URL or external reference fields are allowed.

- Document: schema_version="review-display.v2", surface="body",
  review_type="basic"|"advanced", blocks, sections, canonical_text.
- Block: id, type, runs, separator_after. IDs match
  ^[a-z][a-z0-9_-]{0,31}$, 1–32 ASCII characters, unique within this document.
- type: heading|paragraph|list_item|divider (existing v1 vocabulary).
- Run: type=text|strong, text. No nested runs or references.
- blocks: 1–64; runs/block: 1–64; total runs: at most 512.
- Run text: 1–4096 Unicode codepoints; canonical_text: 1–16384.
- separator_after: 0–16 codepoints, ASCII space/tab/LF only.
- Text preserves exact Unicode and whitespace; no normalization/trim/repair.
  Reject U+0000–0008, U+000B–001F (including CR), U+007F and unpaired surrogates.
  A Unicode scalar outside BMP counts as one codepoint in both languages.
- Divider has exactly one text run. Markers and visible body labels, if emitted,
  are literal compiler-owned canonical content, never synthesized by a renderer.

These preserve v1 display resource ceilings. Semantic collection ceilings below
come from trade_review_schema/review_history_content_contract. The complete source
still passes its own stricter per-field limits before compilation; display bounds
do not relax source limits.

## Roles, fields and canonical traversal

Each section has exactly role, block_ids and the fields listed below.
All named text fields are single local block-ID references unless stated otherwise.
quality = {label, explanation}; card = {title, detail}.
Arrays retain source order. Missing/optional collections use [], not null/omitted keys.
The schema's x-field-order defines recursive traversal, and x-block-ref identifies
references; these annotations are normative. role, block_ids and enums themselves
contribute no reference to traversal.

Basic role order:
summary → data_quality → good_points → main_improvement → next_trade_checks → lesson.

Advanced role order:
summary → data_quality → entry_review → risk_review → exit_review →
detailed_analysis → next_trade_playbook → lesson → reflection_questions.

| Role | Fields in traversal order |
| --- | --- |
| summary | objective={realized_pnl, realized_return_pct}; decision_quality=quality; main_issue; next_action |
| data_quality | confidence={level, label, reasons[0..5]}; missing_information[0..4] |
| good_points | items[1..2] of card |
| main_improvement | title; detail |
| next_trade_checks | items[1..3] of {phase, text}; phase=before_entry|while_holding|before_exit |
| lesson basic | title; concept; applied_to_this_trade |
| lesson advanced | title; concept; applied_to_this_trade; next_trade_application |
| entry_review | assessment=quality; evidence[1..4]; uncertainty[0..4]; invalidation |
| risk_review | planned_rule; actual_response; assessment=quality |
| exit_review | profit_taking_assessment; trend_exit_assessment; explanation |
| detailed_analysis | items[0..5] of card |
| next_trade_playbook | before_entry[1..3]; while_holding[1..3]; before_exit[1..3] |
| reflection_questions | items[0..2] |

Confidence level is high|medium|low. Labels/reasons are canonical refs, never
parsed to infer level. missing_information is independent: low+[] is valid;
medium+missing is valid. High may collapse, medium warns, low strongly warns,
empty missing may hide, nonempty missing is separate presentation policy.
No color/priority/size fields. Validate hidden/collapsed content before rendering.

Summary references the backend's admitted objective values, not model estimates.
Other objective fields remain in the existing approved envelope, outside this
body projection. Formatting is compiler-owned; fixture +29,967원/+1.33% are exact
synthetic examples, not a general numeric formatter implementation.

### Ownership/order invariants

For EACH section, recursively traversing its fields in the table/schema order
must yield exactly block_ids (0–64 IDs, no extras). Concatenating every section's
block_ids in fixed role order must equal document.blocks.map(id), exactly.
Every block therefore has one owner and one semantic field reference.
Orphan, repeated ownership/reference, foreign-section reference, reversed order,
role mismatch and missing role all reject. Empty sections with empty owned blocks
are legitimate only where every required collection is empty (e.g. questions).
References are strings to blocks, never section IDs or recursive objects; blocks
have no outgoing references. A graph cycle is structurally impossible.
Validate explicit roles AND order: array index is not an unvalidated role inference.

## Canonical identity

Flatten every run's text plus each separator in document.blocks order:
the result MUST equal canonical_text. v2 text need not equal v1 text.
Body headings/list markers/labels belong in canonical runs if shown as body.
Shell labels and collapse controls are not body text. Expansion must expose the
entire approved canonical sequence; no hidden unvalidated tail.

Whole-document approval protects schema/surface/review type, IDs, block types,
runs/separators, section roles, ownership/references, enums and canonical_text.
Equal text is NOT equal approved identity. Reordering JSON keys alone is immaterial.
Changing confidence without changing text may be structurally valid but cannot
reuse the old approval. The test helper's sorted JSON equality is a comparison
oracle, not production cryptography, a new seal format or an authorization token.

## Atomic approval bundle (Major 1)

Exact envelope is schema $defs.bundle, schema_version=review-approval-bundle.v1.
It is a future internal contract, not a new public API response in this slice.

v1_only:
{schema_version, kind, review_type, status, representations:{v1:{document,summary}}}.
kind=v1_only; status=ready|missing_key|error|empty.
An old record becomes this logical variant ONLY after existing whole-record
admission. No DB migration or inferred upgrade. Absence of v2 is legitimate.
A terminal response with no approved body has no bundle; this schema does not
invent an error body.

paired_v1_v2:
{schema_version,kind,review_type,status,source_identity,objective_identity,
 representations:{v1,v2}}.
kind=paired_v1_v2; status=ready only.
Each representation has compiler_version, source_identity, objective_identity,
review_type, document; v1 additionally has summary.
Compiler versions are exactly review-body.v1.0 and review-body.v2.0.
The v1.0 alias pins HEAD 39c4534f90307b2339168eb939f7ddfbcfc6f195's
compile_structured_review plus unchanged A1 compatibility serialization.
v2.0 names the future compiler target in this schema/corpus, not an existing
runtime function. A changed compilation rule requires a new explicit version;
silently reinterpreting an existing version on read is forbidden.
Identity labels are bounded opaque strings (1–128, [a-zA-Z0-9._/-]+);
matching these labels alone does not authenticate or admit content.

One trusted admitted analysis + objective feeds both pinned compilers. Admission
requires independent v1/A1 and v2 validation, identical source/objective/type,
complete semantic coverage under each compiler's rules, and EXACT agreement with
each compiler output. v1 retains current A1 summary-to-body equality, including
strong markup boundaries. v2 references all required semantic text slots and
keeps confidence/phase enums; no omission, relocation or substituted objective.

Only AFTER both succeed may an immutable approval for the WHOLE bundle be created.
One atomic persistence/cache publication includes discriminator, both representations,
versions and common provenance/approval association. Never store one side first.
Snapshot integrity must bind both entire documents AND their provenance to the
trusted source approval; caller-supplied source hash is insufficient.

Paired missing/corrupt either side, unknown compiler, mismatched provenance/type,
invalid A1, or structurally valid but wrong compiler output => WHOLE bundle reject.
This applies even to a v1 client requesting the good side. Never downgrade a bad
paired record to v1_only, ignore the bad side, regenerate from raw semantic data on
read, call AI to repair, or persist partial approval.
Legacy v1_only handling keeps existing admission; it does not require reconstructing
a historical source that was never stored.

Reference tests compare to a separate trusted fixture witness, not expected fields
supplied by the record. Witness outputs are immutable expected data, not a runtime
approval mechanism. Existing Python v1 compiler/A1 independently verifies v1
witnesses; fixed v2 outputs and semantic bindings specify the future compiler target.
Slice 2 must implement real factory-only approval and mutation-proof identities.
Later storage work must prove the association survives reads without recompilation.

## Execution identity / display negotiation (Major 2)

Keep current authenticated user scope + idempotency key and existing execution
body fingerprint rules (including current token exclusions). Display capability
is NOT added to that fingerprint. Same key/different body retains conflict.
A display selection change is not another analysis.

Two distinct capability checks prevent an ordering ambiguity:
1. Early request capability SYNTAX/ELIGIBILITY gate: unsupported, duplicate,
   malformed values reject before AI/charge/history insert, including cache misses.
   Slice 1 defines only logical v1 and dual capabilities; it does not add/change a
   wire header. Existing exact-single-header fail-closed behavior remains.
2. Resolve execution identity and an existing approved record (with ownership).
3. Validate WHOLE bundle and its approval, including the unrequested representation.
4. Negotiate representation against validated bundle and eligible client capability.
5. Project already-approved representation; return without new AI/charge/insert.

The early gate does not inspect or choose a representation. A corrupted bundle
never bypasses validation because an old client only understands v1.
A projection is data selection, not a new partial stored approval.

| Case | Client / record | Result |
| --- | --- | --- |
| A | v1 / v1_only | v1 |
| B | dual / v1_only | v1, never upgrade |
| C | v1 / paired | validate both, project v1 |
| D | dual / paired | validate both, project v2 |
| E | any / paired missing v2 | reject entire bundle |
| F | any / paired corrupt v1 | reject entire bundle |
| G | unsupported/malformed/duplicate capability | early reject, effects 0 |
| H | same execution, changed display capability, approved record available | projection only; AI/charge/insert 0 |
| I | same key, different body | existing conflict; no new execution |

## Cache/history boundary

Current cache is process-memory, default TTL 300s (configured bounded TTL), not a
durable idempotency ledger. Existing cache hit may replay an approved bundle.
After expiry/restart, no approved cache record means no promise of free replay.

Owner-authorized history GET may display an admitted stored record with this same
projection contract. It is NOT a POST execution-identity match: current history
does not persist the request fingerprint/idempotency-key mapping needed to promise
cross-restart POST deduplication. Do not search history by trade/source similarity
to skip charging or create such a guarantee in this migration.

No safely associated record => ordinary new-request consent/entitlement/idempotency
rules apply, not free reconstruction. Reference counters prove only model behavior;
actual route/cache/charge/storage evidence is required in later slices.

## Generation / rollout / rollback floor

Slice 1: NO runtime v2, no bundle wrapper added.
Future bridge: reads/validates both bundle kinds, serves v1/dual projections,
generation OFF (new results remain v1_only).
Activation: only normal structured ready gets paired generation.
missing_key/error/empty and separate fallback body remain v1_only, even with ON.

| Combination | Required result |
| --- | --- |
| old v1 app + bridge | v1; paired records still fully validated |
| dual app + bridge / generation OFF | v1 for new v1_only results |
| dual app + bridge / generation ON | v2 for eligible paired ready; otherwise v1 |
| old v1_only history + old app | v1 |
| old v1_only history + dual app | v1, no upgrade |
| paired history + old app | v1 after atomic validation |
| paired history + dual app | v2 after atomic validation |
| frontend rollback to v1 app | bridge projects v1; no data downgrade |
| backend rollback to bridge | safe with generation OFF; continues reading paired |
| rollback to pre-bridge after paired persistence | NOT SUPPORTED SAFE ROLLBACK |

Bridge is the rollback floor once paired data exists. Rolling generation OFF
does not delete/convert paired history or authorize pre-bridge rollback.
Rollout tests in Slice 1 are a state specification, not deployment verification.

## Shared vectors and implementation slices

Three sanitized source witnesses: basic-high/missing[], basic-medium/missing,
advanced-low/missing[]. Each includes fixed v1/A1 + v2 output and source-slot
bindings. Both languages use the same file. Negative cases are base+mutations;
wrong content/order/state can keep an identical source ID and still reject.
Old v1 suites and production v1 validator continue rejecting v2.

1. This contract/reference/vector suite; no production behavior.
2. Pure v2 compiler/admission and atomic approval, no runtime connection.
3. History/cache persistence and sealed-read invariants.
4. Bridge gate/projection/execution replay, generation OFF.
5. Dual frontend admission/renderer and collapsed/full-text UI regressions.
6. Rollout/rollback evidence; separately approved ready-only activation.
