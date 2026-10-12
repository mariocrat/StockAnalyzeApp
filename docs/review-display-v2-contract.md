# review-display.v2 body, approval and durable history contract

## Status and authority

The body/bundle specification below originated in Slice 1 (2026-10-12).
Slices 1 and 2 are independently approved and committed. Slice 2 supplies pure
production validators/compilers and process-local approval, still disconnected
from runtime routes/history/cache/frontend. The Slice 3 durable history contract
below clarifies the held architecture review; it is a design, not implemented
storage support. No header, renderer, storage rollout or generation is activated.
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

## Slice 3 durable history contract

### Threat model / Authority

The trusted application writer and its typed finalization/issuance path are the
trust assumption. Protect later payload corruption, partial/inconsistent storage,
storage version/kind, both representations, source/objective/provenance and the
actual history row context. The durable digest is a public checksum and consistency
binding, NOT authenticity, a signature or cryptographic authorization proof.

Out of scope: an actor able to rewrite DB content and digest coherently, server
code/admin compromise, malicious reinsertion of an old valid row, full DB rollback,
and complete replacement by another valid legacy row. A restart-safe digest does
not restore the process-local _ISSUED anchor or independently prove historical
compiler execution against a source that was never persisted. No HMAC/keyring/
rotation/secret, JCS or custom numeric protocol belongs to 3A. Future authenticated
DB tamper-resistance requires a separate security migration.

### Exact storage envelope / Dispatch

The new format occupies existing ai_review_json TEXT, with no DDL/backfill. The
outer object has EXACTLY these five required keys; unknown or missing keys reject:

```json
{
  "storage_schema_version": "review-history-paired.v1",
  "kind": "paired_v1_v2",
  "codec_version": "review-history-json.v1",
  "payload": "<the canonical payload JSON as a string>",
  "payload_digest": "<64 lowercase hexadecimal SHA-256 characters>"
}
```

All five values have exact built-in string type. The first three are exact enums;
payload is nonempty canonical JSON text, not an object, base64, compressed data or
a URL. Its UTF-8 bytes are the digest input. payload_digest matches [0-9a-f]{64}.
The outer encoding uses the same codec. There is no top-level summary/display
compatibility alias, algorithm selector, optional side or v1-only wrapper variant.
Old/new v1-only rows keep their existing unwrapped formats and admission.

Before any interpretation, dispatch by reserved root keys: presence of ANY of
storage_schema_version, kind, codec_version, payload or payload_digest selects
paired admission only, regardless of the value. Also reserve root-level bundle
markers schema_version=review-approval-bundle.v1, representations, source_identity
and objective_identity against accidental unwrapping. Unknown future storage
version/kind, wrong types, missing keys, partial removal, malformed JSON or duplicate
keys yield unavailable; never retry legacy. An unwrapped remainder must satisfy
the existing closed legacy/v1 shape (including summary); {} is not legacy success.
No markers AND a valid historical/canonical v1 shape uses the unchanged old path.
Deleting the entire wrapper and substituting a different valid legacy row is the
explicitly excluded whole-row replacement attack, not a guaranteed detectable case.

### Exact canonical payload / Row context

Payload is an object with EXACTLY row_context, snapshot_digests, objective,
bundle and chart_display_snapshot. No additional provenance/compiler/summary copies
are added: bundle owns its body representations and existing identities/versions;
objective owns the complete admitted objective; chart_display_snapshot owns the
AI review's approved display auxiliary data. SQL snapshot columns own their separate
content. Context is an assertion about the actual SQL row, never an alternate
display metadata source. review-display.v2 remains BODY ONLY: charts/chart_cards
are not v2 blocks, sections or additional body document keys.

row_context has EXACTLY:

| Key | Exact type / Constraint / Actual SQL source |
| --- | --- |
| id | int, 1..2^53-1; actual review_history.id, never a stand-in |
| user_id | nonempty str, <=120 codepoints; actual authenticated owner column |
| review_type | str basic or advanced; row and bundle must agree |
| ticker | str, empty or six ASCII digits; existing metadata identity |
| name | str, <=120 codepoints; existing nonempty metadata rule |
| trade_date | str, 1..35 codepoints; existing calendar/date-time rule |
| target_trade_id | null or exact int 1..2^53-1; equality to the actual nullable column |
| model | str, 1..100; existing [A-Za-z0-9._:/-]+ ready model rule |
| source | exact str openai; paired is ready/openai only |
| created_at | str, exactly 25 characters YYYY-MM-DDTHH:MM:SS+00:00, valid UTC calendar |

All metadata retains the current content/write Unicode and date constraints.
target_trade_id does NOT acquire a membership/equality requirement against the
recent window: the current producer permits an absent/outside-window target.
created_at is the stored value, not a recomputed current clock or timezone.

snapshot_digests has EXACTLY trade_snapshot, recent_trades_snapshot, chart_snapshot
and access_snapshot, each a 64-character lowercase hexadecimal SHA-256 string.
They bind the complete canonical values in the respective *_json SQL columns,
including nested canonical documents, candle/marker/metric data, fees/memos and
access balances/policy. No PDF, full original source or duplicate snapshot content
is introduced. Existing strict metadata/access and whole-record safety checks still
apply; a checksum does not make otherwise invalid snapshots admissible.

Choose canonical context object + exact SQL comparison (option B), with digests
ONLY for the four large existing snapshots. Duplicating those snapshots in payload
(option A) creates redundant content and avoidable resource cost; an opaque metadata
digest alone (option C) obscures the field contract and omits explicit row identity.
Compare actual types and canonical bytes, not Python loose equality/coercion.
SQL snapshots are strict-decoded with duplicate-key/nonfinite rejection; their
canonical content, not insignificant JSON key/spacing order, defines identity.
The SQL owner must be available internally: current _row_to_detail omits user_id,
so 3B must retain the owner for admission, then omit it from public projections.

The bound id is necessary even for two rows with otherwise identical contents.
Copying a complete valid wrapper to another row without changing it fails id
comparison. Changing only owner, target, metadata or any bound snapshot also fails.
Read never substitutes payload metadata for a mismatching SQL value.

objective is the current Slice 2 complete _dto_tree(ObjectiveSource) JSON shape:
each DTO has EXACTLY dto and fields; DTO names and all nested keys are pinned.
ObjectiveSource.fields={symbol,period,result}; ObjectiveSymbol.fields={ticker,name,
symbol_kind}; ObjectivePeriod.fields={first_trade_date,last_trade_date}; and
ObjectiveResult.fields={trade_count,closed_count,realized_pnl,realized_return_pct,
win_rate_pct,weighted_buy_price,weighted_sell_price,total_fee,total_tax,
buy_fill_count,sell_fill_count,open_quantity,symbol_count}.
Reuse current objective field/type/calendar/count/finite-value constraints;
symbol_kind is krx or name_only and obeys current symbol identity constraints.
Preserve hidden fields, numeric classes, nullable averages and exact values.
Its canonical bytes' SHA-256 must equal bundle.objective_identity. This is the
existing Slice 2 identity encoding, not a replacement numeric/DTO protocol.
Reads validate this tree without normalizing it or minting a live source DTO.

bundle is the existing exact review-approval-bundle.v1 paired_v1_v2/ready variant.
Both source_identity/objective_identity and each compiler/type association must
agree. For this writer, identity strings are actual 64-lowercase-hex SHA-256
identities from Slice 2 issuance (not witness aliases). Full source_identity is
retained only in the existing bundle (including its required per-representation
associations), not reconstructed from the truncated history
trade window. Its complete original source is not saved. Durable reads therefore
check retained associations under trusted-writer assumptions; they cannot independently
re-prove the original compiler/source relation if content AND digests are rewritten.

### Approved AI chart auxiliary / Distinct chart sources

SQL chart_snapshot_json (A) is the general journal/history chart snapshot.
ai_review.chart_display_snapshot (B) is the AI review's independently approved
charts and chart_cards. They can legitimately differ; neither is a substitute
for the other. Existing PreparedHistoryContentTest and ApprovedHistoryWriteTest
already assert different candle values between A and B. A's existing snapshot
digest does not preserve B, even if A happens to equal B in one example.

payload.chart_display_snapshot is required and has EXACTLY charts and chart_cards,
both exact list types. Reuse review_envelope_contract.validate_chart_display_snapshot
and the existing new-history content field constraints: <=8 charts, <=500 candles
and <=300 markers per chart, <=100 chart_cards, existing canonical surface documents,
finite numeric metrics, enums/types and resource checks. No unknown nested fields,
raw chart strings, v2-body chart insertion or schema relaxation. Preserve every
approved candle/marker/document/card/metric, array order and exact numeric types.

Issuance captures this exact value from the SAME original ApprovedReviewSnapshot's
charts/chart_cards projection and the frozen PreparedHistoryContent result's
chart_display_snapshot. Require canonical-byte/type identity with both and with
the validated ApprovedHistoryWrite's ai_review.chart_display_snapshot; current
prepare_history_content/_match_seal already enforces the first relationship.
Serialize an independent immutable copy into the full payload digest before write;
never recompute it from SQL A or use a caller-supplied replacement. Recheck this
association before and after serialization with the other original capture inputs.

Missing, null, malformed or changed B rejects the WHOLE paired admission, even if
both body representations are valid or only a body is requested. A correctly
approved {"charts":[],"chart_cards":[]} is valid and must round-trip unchanged;
it is never a repair default for missing/corrupt data. Independently empty approved
arrays also retain their original values. Mutation checks retain the stated digest
threat model: coherent content-plus-digest rewriting is not authentication-proof.

Immediate approved result and durable history reopen must have identical approved
display identity for body, charts AND chart_cards (whole documents/values, not text
alone). Use bundle.representations.v1 for the body's admitted compatibility projection,
payload.chart_display_snapshot for AI charts/cards, and SQL chart_snapshot_json only
where the general journal chart is requested. Return B as ai_review.chart_display_snapshot;
return A as the separate journal chart_snapshot. Never use A as B, merge them,
truncate cards, rebuild B from metadata or fall back to A on paired rejection.

### Canonical codec / Exact digest domains

review-history-json.v1 uses the current deterministic primitive:
json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
allow_nan=False).encode("utf-8"). UTF-8 has no BOM or terminal newline. Object keys
sort by Python Unicode codepoint order; arrays keep order. Never normalize Unicode,
trim strings, reorder arrays or coerce scalar classes. Only plain dict/list/string/
null/bool/int/finite-float values are allowed; reject subclasses, cycles, nonstring
keys, duplicate keys, unpaired surrogates, nonfinite values and unsupported types.
Payload field schemas retain stricter character/field limits. Key length <=64.

Use strict UTF-8/JSON decoding with duplicate-object-key and parse_constant rejection.
Canonical re-encoding must equal the saved payload bytes. No repair of noncanonical
payload JSON. Outer input is also required to match its canonical re-encoding.
Preserve 1 as int and 1.0 as float; retain -0.0 and its negative sign, distinct from
0.0/0. No JCS conversion or bespoke float encoding. Approved Python 3.12.14 produced
and round-tripped [null,true,1,1.0,-0.0,0.0] byte-for-byte in this document step.
Pin normal Python JSON finite-float formatting as part of this codec. Runtime
upgrades must pass codec goldens, including exponents/subnormal/extreme floats;
this single observed interpreter is not proof about all future runtimes. An
incompatible implementation requires a new codec plus an old-codec reader; it
cannot reinterpret existing bytes under the same version or rewrite rows on GET.

Let L(b)=len(b).to_bytes(8,"big") + b. Define:

```text
payload_digest = SHA256(
  b"StockBoda-review-history-paired-v1\x00"
  + L(UTF8(storage_schema_version)) + L(UTF8(kind))
  + L(UTF8(codec_version)) + L(UTF8(payload))
).hexdigest()

snapshot_digests[field] = SHA256(
  b"StockBoda-review-history-snapshot-v1\x00"
  + L(UTF8(codec_version)) + L(UTF8(field))
  + L(canonical_JSON_bytes(actual_SQL_snapshot_value))
).hexdigest()
```

The top digest thus binds storage version, kind, codec, full body bundle, complete
approved AI chart_display_snapshot, objective and context/snapshot associations.
The checksum is neither secret nor
authentication. Public serialization/checksum primitives may be pure helpers;
only the typed issuance boundary may wrap their output as approved durable content.

### Resource contract / Size evidence

- Canonical payload UTF-8: 1..1310720 bytes (1280 KiB / 1.25 MiB).
- Canonical outer JSON UTF-8: at most 2622464 bytes (2*1310720 + 1024).
- Decoded payload tree: depth <=16 (root depth 0), <=32768 visited value nodes;
  each container and scalar counts once, including array entries, excluding keys.
- Outer object: depth <=1 and exactly 6 value nodes; payload is one string here.
- Inner strings: <=16384 Unicode codepoints, with existing run 4096/ID 32/
  identity 64 and other stricter field limits. The carrier payload string is
  exempt from that inner-string limit; its UTF-8 byte budget applies instead.
- Existing SQL snapshots keep their current strict schemas, per-field limits,
  depth 32/node 100000 admission ceiling; no broadening for paired storage.

Support scope: durable paired storage supports ALL valid results that the current
trusted production approval path can normally issue, under the existing paired
eligibility contract. This means production request/builders -> admitted source ->
finalizer/seal -> prepared/write relationship, together with the pinned v2 compiler.
It does not mean arbitrary compiler-only DTOs or schema-only synthetic combinations
that the production producers cannot generate. The limits below are derived upper
bounds, not new truncation/eligibility rules. Other existing v1-only statuses retain
their current path. No approved chart or card is dropped to meet a storage limit.

Production trace (all references below are existing source, not new runtime code):

- backend/main.py caps the AI request at a configured maximum no greater than 200
  trades. build_basic_ai_review/build_advanced_ai_review in ai_review_v2.py analyze
  one selected episode and use episode[-20:] for chart production. Advanced groups
  partition that same window: no trade is duplicated across its chart inputs.
- _compact_chart_snapshot fully admits producer output, chooses its first chart,
  selects the marker window or last 100 candles and, if needed, samples to at most
  140 candles. Final envelope/prepared guards admit at most 8 available charts;
  combine these conservatively as <=1120 AI candles (not 8*500). Many actual
  episodes have only one chart; attainability of all maxima together is not assumed.
- journal_chart._markers_for_trades groups by candle time/side, with one price per
  input fill. _technical_reviews emits at most one observation per input trade.
  Across the <=20 chart-input fills there are <=20 markers, <=20 total tooltip price
  entries and <=20 cards. select_chart_candles retains existing markers/observations;
  it cannot multiply them. compile_review_envelope._card emits five null metric
  fields. Unavailable chart variants emit neither AI charts nor cards.
- The general journal chart producer has NO fixed DataFrame tail cap; its full
  returned candles are not AI B. A history write succeeds only if the separate
  metadata guard accepts <=8 SQL charts/<=500 candles/<=300 markers/<=100 reviews per
  chart, a target trade plus the last 10 recent trades, name 120, memo <=5000, and
  the existing whole-record depth 32/node 100000 guards. Those SQL values bind by
  four fixed 64-character digests; they are not copied into payload or substituted
  for B. The API input count and these guards remain unchanged.
- Finalizer/prepared/write validates structured text <=900 (card title <=160),
  confidence reasons <=5, missing <=4, entry evidence/uncertainty <=4, details <=5,
  playbook <=3 per phase, reflection questions <=2. V1 mapping emits 4 basic/8
  advanced paragraphs. Pinned v2 mapping emits at most 28 basic/59 advanced blocks
  (advanced 6+10+11+4+3+10+9+4+2), with b0..b58 IDs. Both body documents retain
  total runs <=512 and canonical text <=16384; A1 summary also <=16384. Inputs that
  fail those finalizer/prepared checks are not approved results, even if a raw
  semantic field schema by itself accepts them.
- Candle values pass through _to_float and finite admission: seven numeric fields
  are finite binary64 or null; time is a calendar date or safe integer. The shortest
  JSON finite-float spelling needs <=17 significant digits plus sign/dot/exponent;
  reserve 32 ASCII bytes/token. Grouped currency formatting of any admitted finite
  float has <=309 integral digits, <=102 commas and a sign: <=412 bytes. These are
  bounds on permitted numeric types, not impossible-value fixtures. Formatting
  overflow/nonfinite source or derived values cannot pass the current approval.

Conservative canonical payload byte bound (combining upstream maxima is deliberate):

| Component | Calculation | Bytes |
| --- | --- | ---: |
| Body bundle | 5*16384*4 text bytes + 2*512*32 run shells + (8+59)*64 block shells + 8192 fixed root/bundle/section/ref overhead | 372928 |
| AI candles | 8*140*320 bytes/candle | 358400 |
| AI cards | 20*[2*(160+900+2)*4 + 64*32 + 64 + 128 + 256] | 219840 |
| AI markers | 2*[20*(32+508+508+6) + 20*412 + 20*2 + 20*3] + 20*8 + 20*832 | 75640 |
| Chart shells/header/tab | 8*[2*(64+120*4) + 65*32 + 2*64 + 2*128 + 128] | 29440 |
| Auxiliary root/array syntax | Fixed closed object/collection allowance | 256 |
| Objective/context/bindings | Complete objective DTO tree + ten row scalars + four digests + syntax | 8192 |
| **Total upper bound** | Sum, with all arrays/strings preserved | **1064696** |

The text multiplier 4 covers UTF-8/JSON escapes of allowed scalar characters; valid
text excludes the controls whose six-byte escapes would exceed it. Body text is
two run/canonical sequences plus A1. Fixed syntax costs measured with the existing
codec are 28 bytes/run including a comma, 52/63 bytes for empty-text v1/v2 block
shells, and 67 bytes/candle shell. Budgets 32/64/320 are conservative: a candle needs
at most 67 + 7*32 + 18 = 309 bytes including time and syntax. Separators belong to
the text pool. The 8192 body overhead covers document/bundle headers and at most
118 b0..b58 field/ownership references plus the fixed nine-role section grammar.

Cards have one paragraph, <=64 runs, a <=160+900+2-codepoint title/detail line copied
into runs and canonical_text, a <=128-byte document shell and <=256-byte fixed
trade-id/metric wrapper. Markers have one literal label paragraph and at most four
literal tooltip paragraphs (one run each). Per-tooltip allowances are title 32,
average/quantity 508, optional profit/rate 508, escaped newlines 6 bytes; the price
list allowance is pooled across ONLY 20 fills. The marker's five run/block shells,
two document shells and wrapper cost <=832 bytes. Header is <=64 encoded text bytes,
tab <=120 codepoints; only the tab can expand into 64 inline runs. Context/objective
has bounded names/user (120), model (100), dates (35/25), fixed DTO labels/keys,
safe counters/IDs and finite computed values; 8192 exceeds their combined scalar/
syntax bounds without persisting any memo, market array or full source receipt.

Node accounting counts values, not schema visits, with root depth 0:

| Component | Calculation | Value nodes |
| --- | --- | ---: |
| AI auxiliary | 1120*9 candles + 8*219 chart/header/tab overhead + 20*48 markers + 20*209 cards + 3 root/arrays | 16975 |
| V1 body | 5 root fields/containers + 8*4 block overhead + 512*3 run nodes | 1573 |
| V2 body | 7 root fields/containers + 59*5 blocks + 512*3 runs + 256 section/ref/container allowance | 2094 |
| Remaining payload/bundle/context/objective/bindings | Fixed closed-shape allowance | 256 |
| **Total upper bound** | Sum | **20898** |

A one-paragraph document with 64 runs has 5+4+3*64=201 nodes; each marker uses a
12-node label plus a <=33-node literal tooltip and three wrapper nodes. Sections
have <=118 reference values plus bounded roles/enums/containers, below the 256-node
allowance. B's existing validator depth/node checks remain separate and unchanged.

Final payload limit 1310720 leaves 246024 bytes (23.1%) above the conservative byte
bound; 32768 is the next power-of-two node budget above 20898, leaving 11870 nodes.
The deepest stored path is payload.chart_display_snapshot.charts[].markers[].
tooltip.blocks[].runs[].text, depth 11; depth 16 keeps five levels of headroom.
Outer encoding can at most double payload quote/backslash bytes; fixed wrapper
version/kind/codec/digest syntax fits 1024 bytes, so 2*1310720+1024=2622464.
Bound raw outer bytes before parse, payload bytes before inner parse and lexical
nesting while scanning; validate decoded budgets before semantic callbacks.

The prior 4 MiB/8389632/131072 proposal and compiler/schema-only dense measurements
are superseded and are NOT production support evidence. This step verified source
constraints and arithmetic/fixed syntax in memory, without product imports or test
execution. 3A/3B must exercise max-valid production-shaped basic/advanced values
through the trusted approval/prepared/write chain and preserve all charts/cards.
No new source restriction may be introduced just to satisfy this resource budget.

Boundary tests must distinguish maximum approved data from a parser carrier limit:
max-valid production results are required to fit without truncation. At EXACT
1310720 payload bytes / 2622464 outer bytes / 32768 value nodes / depth 16, the
resource preflight passes (full admission may still reject invalid grammar). At
limit+1 the corresponding bounded layer rejects deterministically before projection.
Use test-owned scaffolding solely for these transport boundaries, never to enlarge
the support bound or claim it is trusted production output. Include multibyte UTF-8,
quote/backslash escaping, int/float/null/-0.0 and unchanged A != B/empty contracts.
Any producer/compiler/upstream-contract change must rederive this version's budget
or introduce a compatible new storage/codec version; silently narrowing supported
approved results or repairing auxiliaries to fit is forbidden. No runtime bounds,
tests or fixtures were implemented in this documentation step.

### Live issuance versus durable read authority

Planned pure types: LivePairedHistoryApproval, ApprovedDurableHistoryEnvelope and
DurableReadAdmission. Names are design targets, not existing production classes.
The live capture factory is finalizer-authority-only; no public raw-dict approval
or factory accepting a digest as authority. It must validate and retain:

1. Exact current ApprovedReviewSnapshot and validate_envelope on its original bytes.
2. Original PreparedHistoryContent and validate_prepared_history_content against
   exact metadata/result and that SAME snapshot object; no equal-byte replacement.
3. approve_history_write / ApprovedHistoryWrite plus validate_approved_history_write,
   retaining their exact serialized record, four snapshots and actual bind values.
4. Exact issued ApprovedReviewBundle validated by validate_bundle and its original
   _ISSUED receipt/source owner; complete objective identity and current source
   capture must still match. Never deserialize or manufacture this authority.
5. Same live finalizer capture association between source owner, original snapshot,
   prepared content and bundle. Existing prepared content does NOT itself hold the
   source DTO; equal body/objective bytes alone are not proof of original ownership.
   3A needs an explicit finalizer-only capture token/receipt retaining these original
   identities, with no runtime finalizer connection until a later authorized slice.
6. Bundle v1 document/summary equals the frozen prepared result and snapshot body/A1;
   type/status/source/objective agree; row metadata/access matches ApprovedHistoryWrite.
7. The full chart_display_snapshot exactly matches original snapshot charts/cards,
   frozen prepared result and approved-write review content, independently of SQL A.

Seal result/access and prepared relationship before issuing a durable envelope.
Storage context may only be derived from that validated write plus the actual
reserved SQL id. Raw row dicts can be read/checked, but cannot authorize issuance.
Final issuance must own bytes, recheck all original inputs after serialization,
validate independently decoded values and carry a process-local issuance receipt.
Mutated objects plus locally recalculated hashes are not live write authority.
The final writer accepts ApprovedDurableHistoryEnvelope only, never a dict with a
schema_version. Existing v1-only ApprovedHistoryWrite behavior stays unchanged.

DurableReadAdmission accepts persisted bytes and actual row context, validates
them and owns immutable admitted bytes. It grants history/display projection only,
not new write approval. Separate types/issuers; no constructor, conversion, pickle
or read-object path to LivePairedHistoryApproval/ApprovedDurableHistoryEnvelope.
Restoring a read object after restart does not restore _ISSUED or grant access,
consent, entitlement, generation or storage permission.

### Exact durable read order / Projection

The Slice 3B caller enforces authenticated ownership and storage opt-in first.
The pure 3A reader receives that owner's actual row/context; it does no auth/DB I/O.
Then perform, in order:

1. Bound raw outer bytes, strict outer parse and root marker dispatch.
2. Exact keys/types/version/kind/codec and canonical outer encoding.
3. Bound payload bytes; verify the versioned top digest against the saved bytes.
4. Strict inner decode (duplicates/nonfinite reject), depth/node/string/schema
   checks, exact canonical re-encoding identity.
5. Existing v1 document/A1 checks, full v2 checks and validate_bundle_structure;
   validate the REQUIRED chart_display_snapshot with the current AI chart contract.
6. Type/status/compiler/source/objective associations; validate complete objective
   tree and recompute its existing Slice 2 identity; both representations are checked.
7. Exact row_context versus actual SQL scalars, including id/user; strict-decode
   four SQL snapshots, apply existing metadata/access/whole-record safety admission,
   compare all four canonical snapshot digests. Never filter/repair before hashing.
8. Issue immutable DurableReadAdmission retaining body AND B. Only then project
   bundle v1 document/summary, payload AI charts/cards and admitted SQL A/metadata/
   restoration snapshots, each from its own authoritative source.

Read does not call either paired body compiler, normalize raw model semantics,
regenerate a representation, restore a live receipt or retry AI. Current canonical
trade/chart snapshot admission/display projection remains its own existing contract;
it is not v1/v2 body regeneration. Stored chart display documents are checked before
presentation, never trusted because the body digest passed. No paired side can be
inferred from those snapshots. AI B is retained as an independent approved auxiliary;
its absence cannot be repaired by the general journal chart. The paired format
does not persist redundant raw semantics or a second copy of SQL A.

List/detail/reopen/export all use the same complete admission before projection.
Slice 3 returns existing v1-compatible data/status canonical: body comes from the
bundle, AI charts/cards from payload B, general journal chart/restorable trades
from admitted SQL snapshots. It introduces no frontend/header
change. Export emits admitted v1 display data, not internal wrapper/raw JSON/digests.
If any stage fails, reject the whole bundle and return the existing fixed unavailable
history view, with no raw summary, restoration data or good-side fallback. Normal
v1-only uses the existing adapter; no read-time upgrade, rewrite or backfill.

### Corruption examples / Limits of recomputed checksums

| Change after valid issuance | Required result |
| --- | --- |
| Copy complete wrapper into another SQL row | ROW_CONTEXT_MISMATCH, including otherwise-identical row with different id |
| Change target_trade_id, user_id, review_type or any bound scalar | ROW_CONTEXT_MISMATCH |
| Change trade/recent/chart/access snapshot | SNAPSHOT_DIGEST_MISMATCH or earlier snapshot contract rejection |
| Mutate either paired document without a new digest | DIGEST_MISMATCH; no good-side selection |
| Missing/malformed/changed AI chart_display_snapshot B | Whole paired rejection (digest or AI auxiliary contract), no SQL A fallback |
| Correctly approved empty AI charts/cards | Preserve exact empty arrays; never infer replacement from SQL A |
| Missing/partial markers, unknown storage/kind/codec or malformed JSON | Closed contract rejection/unavailable; no legacy retry |
| Change source/objective/compiler association or drop a representation | Digest or full bundle/objective consistency rejection |
| Recalculate digest but leave conflicting SQL context/objective/A1/paired fields | The independent consistency check still rejects |
| Recalculate all digests and coherently change content/context to another valid contract value | Not guaranteed detectable; excluded coordinated rewrite, not authentication |

Error names above specify stable diagnostic categories for 3A tests; map existing
v1/v2 codes without exposing rejected values. Pin one code per negative vector
and document precedence; only expected contract faults become unavailable, never
silently swallow programming exceptions as successful admission. A buggy tool can
produce the same coordinated rewrite as an attacker: checksum detection is not
guaranteed then either. Log only controlled codes/versions/history/correlation IDs,
not full payloads, PDF, financial text, credentials/tokens or raw AI output.

### Slice 3B committed write / Publication failure

Bind the final SQL id without persisting a placeholder. After validating the live
prepared/write relationship, a paired writer uses BEGIN IMMEDIATE, reserves the next
AUTOINCREMENT-compatible id as max(current max(id), current sqlite_sequence value)+1
(treat either absent/NULL value as zero)
under that same write lock, checks the safe-id range, binds/validates the full envelope
to it and performs ONE complete INSERT with explicit id and all values. SQLite
updates its existing AUTOINCREMENT sequence. No new table/DDL, metadata-only row,
partial v1 INSERT or subsequent v2 UPDATE. Rollback on any pre-commit failure.
The existing v1 auto-ID writer remains unchanged. This allocation is a 3B design
target; no SQL or migration is written in 3A or this document step.

Commit success means the entire row is durably stored. Subsequent reread/response/
cache publication failure is NOT partial persistence. Deliver a typed committed
result containing actual inserted id/owner and immutable admitted result to the
caller immediately after successful commit. Prepare its immutable content before
commit; mark/report committed status only after success, without making a post-commit SELECT
a prerequisite for retaining that identity. 3B tests must fault-inject the existing
commit-then-get boundary, publication and known-row compensation; distinguish
pre-commit, committed and commit-outcome-unknown states. No automatic AI retry,
second INSERT or extra entitlement consumption on these publication failures.
Preserve existing owner-scoped compensation/refund contracts; do not claim the
separate access/history DBs plus process cache form a distributed atomic transaction
or provide crash-safe cross-restart POST deduplication. Unknown outcomes require
controlled failure/reconciliation, not blind regeneration.

### Cache / Rollout / Exact 3A boundary

3C uses issued ApprovedReviewBundle/process-local receipt plus immutable execution,
access/history association and existing snapshot. It does NOT impose the history
durable wrapper/codec on process cache. Preserve whole-cache checks, existing key/
body fingerprint, TTL and pending/conflict behavior. Corruption is fail-closed,
never cache miss/AI retry/charge/history insert. History GET and POST idempotency
remain separate; display capability is not execution identity.

3A is pure envelope/codec/digest/typed live issuance/durable read only, disconnected
from API/main/router/finalizer/history/cache/frontend/config. Planned tests cover
deterministic bytes/Unicode/int-float-null-negative-zero, nonfinite/duplicate JSON,
malformed markers/version/kind, digest/content/context changes, restart-equivalent
deserialize/read, raw-dict issuance rejection, read authority separation and all
resource bounds. No actual DB integration. New pure modules must import no runtime
stores/fixtures/test references and gain no environment/secret/activation dependency.

Mandatory added regressions: 3A serialization/admission must retain distinct SQL
snapshot A and approved auxiliary B (A != B), full chart_cards and approved empty B;
reject missing/malformed/mutated B and replacement by A against live capture.
3B synthetic basic/advanced save -> read -> history reopen must keep AI charts B,
general journal charts A and all chart_cards, with immediate/reopened body+charts+
cards identity. Cover list/detail/export shared admission, correct empty B, and
whole-paired rejection on auxiliary faults even with a valid body. No compiler,
SQL fallback or AI retry may repair a rejected auxiliary. These are required
future tests; none was implemented or run in this documentation-only correction.

3B adds synthetic/temp-DB paired history support; 3C adds process cache whole-bundle
support; both keep generation OFF. Slice 4 adds negotiation while OFF. Activation
is later, separately approved. No production paired rows before activation; test
records stay in isolated temp stores. Before any production paired persistence,
pre-Slice3 rollback may be assessed against unchanged old formats. After paired
persistence, a paired-capable bridge is the rollback floor; turning generation OFF
does not lower it. This documentation is not deployment or recovery evidence.
