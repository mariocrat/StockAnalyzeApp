# Review display v2 migration

## Slice 3 — Current Status / Contract clarification

2026-10-12; integration/broker-import-ux-main at
3682af800771f8bc285765d0b288aa9086a823d5, initially clean (0/0/0/0).
Slice 1 independent approval/commit completed at
9b65a812f70f85b7ecc7fd7e6f0be202a866e482. Slice 2 independent approval
(Blocker/Major/Minor 0) and commit completed at the current HEAD. The initial
Slice 3 architecture review was held: storage scope/context and exact issuance,
codec and admission rules needed clarification before implementation.

2026-10-13 chart-auxiliary correction starts at the same HEAD with only this plan
and the contract modified (staged 0/untracked 0). Independent review resolved the
earlier Majors but found one new Major: SQL chart_snapshot_json and approved AI
chart_display_snapshot are different, and the compact payload did not retain the
latter. The auxiliary correction and the resource derivation below are documented;
independent acceptance remains pending. Executable boundary checks belong to 3A/3B.

This step changes only this plan and docs/review-display-v2-contract.md.
The normative durable storage contract is the latter document's
[Slice 3 durable history contract](../../review-display-v2-contract.md#slice-3-durable-history-contract).
No production/test/fixture/config/DB change, stage/commit/push/merge/rebase.

### Goal / Decisions

Protect subsequent corruption of trusted-writer payloads, partial/inconsistent
persistence, version/kind, both representations/provenance and actual row context.
Use trusted typed issuance -> deterministic JSON bytes -> versioned SHA-256
digest -> persisted wrapper -> full read consistency admission. This digest is
not authenticity or cryptographic authorization. A party able to rewrite both
DB and digest, server compromise, malicious reinsertion/full DB rollback and
whole replacement by a valid legacy row are outside this migration's threat model.
No HMAC/keyring/rotation, secret configuration, JCS or custom numeric protocol.
HMAC/signatures may be considered only in a separate future security migration.

Store an exact paired wrapper in ai_review_json, without DDL/backfill. Bind the
actual SQL row ID/owner/metadata and four existing snapshot columns; snapshots
remain authoritative in their SQL columns and are not duplicated in the payload.
Both BODY-only documents, the admitted objective and the exact approved AI
chart_display_snapshot (charts + chart_cards) are authoritative in the payload.
SQL journal chart A and approved AI auxiliary B may differ and never substitute
for each other. B is captured from the same original snapshot/prepared/write
relationship, participates in the payload digest and survives immediate result/
history reopen with identical body/charts/cards display identity. Missing or bad
B rejects the entire paired record; legitimately approved empty B is preserved.
Malformed/partial/unknown wrappers never retry legacy or select the good side.
Keep old v1 prepared/write/read behavior. Separate live write authority from
durable read admission; read objects cannot create new write approval.

### Current Status

- [x] Reconcile actual HEAD/clean state and Slice 1/2 approval/commit records.
- [x] Inspect current snapshot/prepared/approved-write/SQL/read/bundle contracts.
- [x] Specify exact wrapper, context, codec, digest domain, bounds and dispatch.
- [x] Specify 3B committed-write versus publication failure and 3C cache boundary.
- [x] Document the independent-review AI chart auxiliary Major and separate A/B
  preservation, capture, projection and whole-paired corruption contracts.
- [x] Derive/fix resource support and conservative limits for all valid results
  normally issued by the current trusted production approval path.
- [ ] Independent review of the clarified Slice 3 contract.
- [ ] Slice 3A implementation, separately authorized; runtime graph disconnected.

### Verification / Evidence

Read-only source inspection: review_history.py has a single 14-bind INSERT into
an AUTOINCREMENT row, commits, then calls get_review_history. _row_to_detail
currently omits user_id; future paired read must retain it internally for context
comparison, without exposing it in public projections. PreparedHistoryContent
requires the original snapshot object, not an equal-byte clone; ApprovedHistoryWrite
owns the actual immutable record/snapshot/bind values. ApprovedReviewBundle's
weak issuance receipt binds original complete bytes and source owner identity.

Stdlib-only in-memory measurements used the approved Python 3.12.14 with
-I -X utf8 -B; no product imports, files written, DB/network access or tests.
The current json.dumps options preserve [null,true,1,1.0,-0.0,0.0] exactly after
decode/re-encode, including Python types and negative-zero sign. Shared witnesses'
compact expected_v1 / expected_summary / expected_v2 byte lengths are respectively
1832/721/3249, 1908/759/3398 and 3988/1645/6503. They are body witnesses, not full
history rows or evidence that storage code already exists. The earlier 4 MiB/
8389632-byte/131072-node proposal based on dense schema-only shapes is superseded;
those measurements do not establish production-valid support. SQL A/trade/access
remain outside payload, whereas the existing approved B is included in full.

### Resource closure / Production-valid support (2026-10-13)

Support ALL valid results normally issued by the current trusted production
request/builders -> source/finalizer/seal -> prepared/write path, under existing
paired eligibility. Compiler-only DTOs or impossible producer combinations are
not support witnesses. This changes resource scope/limits only: approved B,
digest threat model, row binding, authority and 3A/3B/3C boundaries stay unchanged.

Read-only source trace: main's AI request configured cap <=200; basic/advanced
builders use episode[-20:] for chart inputs. _compact_chart_snapshot picks the
first admitted chart and at most 140 candles. Combine with the final 8-chart guard
as <=1120 AI candles, conservatively. The chart-input groups partition <=20 fills;
marker grouping and one observation per trade yield <=20 total markers, tooltip
price entries and cards, not 8*300 markers or 100 producer cards. General journal
producer has no fixed DataFrame tail cap, but prepared metadata admission permits
<=500 candles per SQL chart; SQL A is separate and only its digest enters payload.
Metadata keeps target+last 10 trades/name 120/memo <=5000/whole-record node 100000;
the full objective can still cover the whole <=200-trade episode.

Existing semantic/ready-write gates retain text 900/card title 160, reasons 5,
missing 4, details 5, evidence/uncertainty 4, playbook 3 per phase/questions 2.
V1 has 4/8 paragraphs; pinned v2 has <=28/59 blocks, both <=512 runs/16384
canonical codepoints; A1 <=16384. Finite production candles are binary64/null;
32-byte JSON numeric tokens and 412-byte grouped currency spellings conservatively
cover permitted numeric types, without using unapproved extreme-value fixtures.

The contract's resource tables calculate byte components 372928 body/bundle +
358400 candles + 219840 cards + 75640 markers + 29440 chart/header/tab + 256 auxiliary
syntax + 8192 objective/context/digests = 1064696 bytes. Value-node bound is
16975 auxiliary + 1573 v1 + 2094 v2 + 256 fixed context/bundle = 20898.
Read-only stdlib arithmetic and fixed JSON grammar sizing confirmed these sums;
no product imports, test execution, fixture changes, DB/network or file writes.
The fixed run/v1-block/v2-block/candle shells cost 28/52/63/67 bytes; the derivation
budgets include literal keys, scalar bytes, commas, escaped separators and UTF-8.

Final limits: payload 1310720 bytes (1.25 MiB), leaving 246024 bytes/23.1% headroom;
nodes 32768, the next power of two above 20898. Outer <=2*1310720+1024=2622464 bytes
includes worst-case quote/backslash escaping plus fixed wrapper overhead. Depth 16
stays: the deepest permitted stored path is depth 11. Existing upstream/schema
guards are unchanged. The full component calculations and node counting rules
are normative in the contract's Resource contract / Size evidence section.

Required 3A/3B checks: production-shaped max-valid basic/advanced must pass the
trusted approval/prepared/write chain and fit without omitted charts/cards. At
exact byte/node/depth carrier ceilings preflight passes; limit+1 fails that bounded
layer (full grammar may reject an exact-limit scaffold independently). Include
multibyte UTF-8/escaping and numeric type preservation. Boundary scaffolding is
not a production support witness. Executable boundary tests remain future work;
the static upper-bound derivation is complete, not deferred to a guessed limit.

Document verification: exact diff allowlist, local link targets, fixed schema/
domain/type/resource definitions and git diff --check. No suite/build/live check.
Protected original feature starts at 609163e9dc7ff8b6bbc5ee13c34e7f8020910c54
with 9 modified/10 untracked entries. Main starts at
f779e252b823bbd724c8be277c54d494d3b93f89 with its existing Play README change;
SHA-256 5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328.

### Remaining / Unverified

The AI auxiliary Major has been addressed in documents only; independent review
of this correction/resource derivation, executable production-valid maximum and
exact-limit/limit+1 checks, and codec
goldens across supported Python upgrades are pending. No durable storage code,
SQL/context adapter, paired history/cache integration, negotiation or activation
exists. Current post-commit reread failure is an existing publication failure
window, not partial persistence. 3B must preserve and return the committed ID/
immutable result and prevent automatic AI/INSERT/charge retries; crash-safe
cross-process POST deduplication is not promised.

### Next Step / Exact implementation split

Review this clarified contract, then implement separately authorized 3A only:
pure storage envelope/codec/SHA-256, typed live issuance and DurableReadAdmission,
with deterministic/Unicode/numeric/duplicate-key/mutation/context/restart-equivalent/
authority/resource tests and official H4 registrations. Reuse existing pure
snapshot/prepared/write/bundle contracts, but no runtime DB/history/cache store
imports or callers, API/router/frontend/config/secret/activation connection.
Include strict auxiliary capture/validation and pure A != B/empty preservation
regressions; review-display.v2 remains BODY ONLY and auxiliary is a separate payload field.

3B subsequently adds typed paired history write/read and list/detail/reopen/export
whole-row admission using synthetic/temp DBs, generation OFF. It must implement
the contract's single complete INSERT/row-ID allocation and committed result
delivery, with failure/compensation tests. Required basic/advanced A != B save/read/
reopen tests must retain AI B, SQL journal A and chart_cards, and prove immediate/
reopened body+charts+cards identity. Preserve approved empty B; missing/malformed/
mutated B fails the whole paired admission, never restores from A. 3C subsequently uses process-local
ApprovedReviewBundle/receipt plus immutable execution/access context for cache;
it does not impose the durable history codec on cache. History GET and POST
idempotency remain separate. Slice 4 adds negotiation, generation still OFF;
activation requires later explicit approval. Before any production paired row,
old-format rollback can be assessed; after one exists a paired-capable bridge
and its compatible read contract are the rollback floor. Temp test rows do not
establish a production rollback floor.

## Slice 2 — Current Status

Base: 9b65a812f70f85b7ecc7fd7e6f0be202a866e482,
integration/broker-import-ux-main, initially clean. User authorized pure production
v2 validator/compiler/approval modules, tests, expected-error vector additions,
inventory and this plan. No request/API/header/history/cache/frontend connection,
generation activation, stage/commit/push/merge/rebase or other worktree writes.

- [x] Inspect source DTO/projection, v1 coverage/A1, seal, prepared content and routes.
- [x] Implement production pure modules and stable error codes.
- [x] Verify reference parity and existing v1/history/client boundaries.
- [x] Independent Slice 2 review: approved; Blocker 0, Major 0, Minor 0.
- [x] Slice 2 commit: 3682af800771f8bc285765d0b288aa9086a823d5.

## Slice 2 — Goal and Architecture

Production pure code can now capture an admitted immutable review source,
compile current v1 plus v2, independently validate both, check semantic coverage
and exact compiler agreement, and atomically issue a paired content approval.
Existing source admission/finalizer safety/ownership/consent/entitlement still
have their existing responsibilities. This pure content object grants none of
those permissions and is not a durable history approval format.

### Files / Production pure modules

New modules only:

- backend/core/review_display_v2_contract.py: closed body shape and coded rejection.
- backend/core/review_display_v2_compiler.py: source capture, deterministic body mapping.
- backend/core/review_approval_bundle.py: v1-only/paired factory and immutable receipt.

Supporting changes: this plan, the shared vector's expected_errors mapping,
both test-only reference helpers, Python display-contract tests, Node canonical
test assertions, tests/test_inventory.json, isolation_inventory baseline counts,
and test_full_test_entrypoint aggregate expectations. No schema/role/golden rewrite.
Total: 9 tracked modified + 3 new production modules; staged 0.

### Validator / Error codes / Precedence

ReviewDisplayV2Error is a ValueError subtype with stable code and a controlled
path. Exception messages contain no rejected values. There is no catch-all that
turns programming exceptions into admission success/rejection. Tests prove
RuntimeError/TypeError programming failures propagate without issuing approval.

The shared corpus now has error_contract_version=review-display-errors.v1 and
expected_errors for all 41 existing negative vectors; IDs, mutations and goldens
are unchanged. Python production/reference and JS reference match every code.

Production body precedence:

1. Exact root keys, version/surface/type.
2. Ordered block shape, ID uniqueness, run/character/resource/separator checks.
3. Fixed role/order and exact nested section fields/reference syntax.
4. Global duplicate ownership; missing owned references; orphan blocks.
5. Per-section missing references; repeated field references; foreign references;
   traversal/ownership order; document block order.
6. Canonical text identity.

Bundle precedence: exact discriminator/keys/status and required representations;
pinned compiler/type/source/objective relationships; v1/A1 admission and summary;
v2 admission; trusted expected whole representation comparison. Paired reads
validate both sides, including the unrequested side. UNKNOWN_KEY on an attempted
kind downgrade is intentional; it cannot hide remaining paired fields.

Examples with multiple violated invariants: duplicate-ownership precedes the
resulting orphan; orphan-block precedes foreign field ownership; wrong-block-order
precedes its canonical mismatch. A structurally valid state/content/ref change
returns COMPILER_OUTPUT_MISMATCH against the original trusted output.
Reference precedence uses its shared schema preflight; the 41 corpus cases have
identical production/reference results. Mixed faults outside this corpus are not
claimed as a cross-language priority guarantee.

Additional source/approval codes include INVALID_SOURCE, UNSUPPORTED_V2_SOURCE,
SEMANTIC_COVERAGE_MISMATCH, SOURCE_MUTATION, INVALID_APPROVAL, APPROVAL_MUTATION.
Existing v1/A1 violations wrap as V1_DOCUMENT_INVALID; existing v1 code is unchanged.

### Compiler / Objective / Confidence / Determinism

Public compile_body accepts ValidatedReviewSource only and captures all DTO
values with exact DTO names/types/immutable tuple shape. Current admission is
rechecked and its type-preserving snapshot must equal the source; normalization
cannot silently repair tampering. Mutable/cyclic/forged/uninitialized sources
reject. Ready/openai/real objective/admitted semantic is required for v2.
Other states and the separate fallback paths do not become v2.

The mapper has explicit basic/advanced field calls and deterministic b0.. IDs;
no locale, random, time, request or input-dictionary order dependence. Model text
uses the existing inline-strong grammar; compiler-owned numeric text comes only
from ObjectiveSource. No frontend text reconstruction exists in this slice.
Sections contain refs plus declared machine enums, without duplicated body text.

Both types compile under high/medium/low quality. Backend review_data_quality
supplies level/label/reasons/missing independently. Optional detail/questions
can own zero blocks. Objective 0 remains 0, nullable average prices remain null
in full source/objective receipt bytes, and unavailable objective is never
converted to zero for v2. Formatting and semantic paths are checked explicitly.

Three fixed v2 goldens pass the mapping kernel; actual admitted DTO pipeline
tests use current backend-generated quality reasons instead of forcing synthetic
fixture reason text into a source DTO.

### Approval bundle / Cross-representation consistency

compile_approval_bundle uses current compile_review_body, v1 validate_document,
compile_structured_review coverage and A1 serializer unchanged. New v2 output
must equal the deterministic projected compiler result. Source/objective digests
bind their complete type-preserving data, not model text or canonical_text alone.
Both representation versions and their exact outputs bind to the approval.

ApprovedReviewBundle is factory-only, immutable, not subclassable/copyable/
pickle-restorable. It owns UTF-8 bytes and returns independent JSON copies.
Module-owned weak issuance receipts retain original complete bundle/source/
objective bytes, digest and original owner identity. Changing instance fields
plus recomputing a local digest still fails; this bookkeeping is neither the
request cache nor a persistence/restart protocol.

Only successful full validation/serialization/source recheck issues a receipt;
failure at v1, v2, coverage, consistency or serialization returns no partial
approval. validate_bundle compares to the existing issued receipt, does not
compile, reconstruct a side, downgrade or create approval. Source owner mutation
is rejected, including hidden objective fields. v1_only can wrap an existing
ApprovedReviewSnapshot without needing or inventing historical semantic input.
No stored legacy record is migrated or overwritten.

### Runtime isolation

Static import AST tests and repository reference scan find new modules referenced
only by each other and tests. Existing API routes, finalizer, history writer,
cache/fingerprint, headers, frontend and Android do not import/call them.
No flag was added. Production modules import existing pure compiler/source tools,
never fixtures/reference validators. All 402 initially tracked files were hashed:
only the 9 explicitly allowed support paths changed; 393 others (including all
existing backend and 41 frontend src files, config/Android) remain byte-identical.
Slice 1 contract spec/schema and golden outputs remain unchanged.

### Verification — Slice 2

Approved executable paths and exact final commands:

~~~powershell
$py = 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe'
$node = 'C:\Program Files\nodejs\node.exe'
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_contract
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_legacy_compatibility tests.test_review_source_contract tests.test_review_envelope_contract tests.test_review_source_admission tests.test_review_history_adapter tests.test_review_history_prepared_content tests.test_review_history_approved_write tests.test_review_display_client_gate tests.test_full_test_entrypoint tests.test_storage_fixture_runner
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:canonical-review-renderer --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:ai-format --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
git diff --check
~~~

- Final contract entrypoint: 33/33 PASS, including 14 new direct production tests.
  Initially passed before receipt hardening; rerun only this entrypoint after
  recomputed-digest/0-null and cyclic-source subcases were added, both PASS.
  No materially failed test approach occurred.
- Related Python: 219/219 PASS (legacy 14, source 32, envelope 26, source admission
  23, history adapter 44, prepared content 18, approved write 24, client gate 21,
  coordinator 15, storage fixture runner 2). Combined distinct direct coverage:
  252/252 in 11 modules; repeated contract runs are not counted again.
- Node: 15 canonical/reference + 11 legacy cross-contract + 7 format = 33/33.
- FAIL/ERROR/SKIP, inventory issues and guarded unexpected violations: 0.
  Restoration/patch restoration/cleanup true; coordinator negative synthetic
  outcomes satisfy their expected contracts. Private/live I/O was blocked.
- Python source inventory: 103 modules / 976 direct, baseline 35/904/22 + Stage 1
  15, separate child probes 18, missing/duplicate/expected skip 0.
- Node inventory: 23/248, missing/duplicate/extra 0, no missing source dependencies.
- Lint PASS and tracked git diff --check PASS. New modules have no trailing spaces
  or extra blank EOF. Full TestOnly, BuildChecks, frontend/Android builds and live
  API/OpenAI/device/private DB were not run. Frontend build omitted because all
  production frontend assets/config are byte-identical.

Protected feature remains HEAD 609163e9dc7ff8b6bbc5ee13c34e7f8020910c54 with
9 modified/10 untracked status entries. Main remains f779e252b823bbd724c8be277c54d494d3b93f89,
only its existing Play README modification; SHA-256 remains
5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328.
No command wrote to those worktrees. No stage/commit/push/merge/rebase.

## Slice 1 — Historical implementation record

## Goal

Freeze an executable, test-only contract for a semantic body and an atomic v1/v2
approval bundle. Resolve the independent review's three Majors: approval/corruption,
execution identity versus display selection, and section ownership/traversal.

## Scope / Current Status

2026-10-12; integration/broker-import-ux-main at
39c4534f90307b2339168eb939f7ddfbcfc6f195, initially clean (0/0/0/0).
Only docs, shared synthetic vectors, test-only reference helpers, contract tests
and exact H4 registrations/counts may change. No production imports or execution.

- [x] Inspect current source, v1 compiler/validator, seal, history/cache and frontend.
- [x] Freeze exact schema, bundle and replay matrices; implement reference tests.
- [x] Run official targeted H4, inventories, lint and preservation audit.
- [x] Independent Slice 1 review: approved; Blocker 0, Major 0, Minor 1.

## Non-goals

No production schema/validator/compiler/renderer, runtime flag/header, route,
history/cache writer, model/prompt/objective/policy change. No v2 activation, DB
migration, device/build, stage/commit/push/merge/rebase or other worktree writes.

## Current v1 constraint

All extra document/block/run keys are rejected. Body/compiler combines semantic
fields into four basic or eight advanced paragraphs; adjacent text runs merge.
Confidence level is not carried into display. The exact body, A1 compatibility
summary, chart projection and prepared history content are bound to the original
approval. See backend/core/review_display_contract.py, review_body_compiler.py,
review_envelope_contract.py, review_history_prepared_content.py and backend/main.py.

## Contract

The normative Slice 1 contract and matrices are in
[review-display-v2-contract.md](../../review-display-v2-contract.md).
The shared JSON Schema and corpus are test data under frontend/scripts/fixtures;
neither is imported by production. Role vocabulary, exact keys/limits,
ownership/order, canonical identity, confidence/missing, approval/corruption,
execution/negotiation/replay, cache/history boundary and rollout are defined there.

## Verification

Effects are restricted to H4-owned synthetic temporary data, blocked external
I/O, and local lint. All runs use the approved Python and Node below; no full
TestOnly, BuildChecks, install, build, API/model, device or private DB execution.

Initial failures (not product defects):

- Python reference interpreter indexed maxLength on enum-only string schemas;
  first run had 4 new methods in error (27 error/subtest reports), while existing
  v1 14 and the v1 compiler/A1 witness check passed. Fixed optional-schema bounds
  in both test-only interpreters. Second official run: 19/19 PASS.
- Node first stopped before entrypoint launch: InventoryError. A read-only call
  to the official source-inventory function exposed `non-source Node read rejected`.
  Registered ONLY the two new exact JSON paths, not a JSON wildcard or directory.
  Second official Node run: 15/15 PASS. The guard itself is unchanged.
- A patch context mismatch (entry closing comma) wrote nothing; narrower patch
  applied. A tool serialization issue with a literal lone surrogate wrote nothing;
  malformed-surrogate test input is now constructed in memory.
- `git diff --check` found one added final blank line; removed it, final check PASS.

Completed checks:

- Python display contract: 19/19 (14 unchanged v1 + 5 v2).
- Node canonical/display contract: 15/15 (10 unchanged v1 + 5 v2).
- Node legacy cross-contract 11/11 and ai-format 7/7.
- Node coordinator synthetic regressions: 9/9, including exact fixture permission
  and denial of unregistered JSON/backup/traversal paths.
- Node inventory: 23 entrypoints / 248 direct, missing/duplicate/extra 0,
  missing source dependencies []. Existing baseline was 243; an older coordinator
  literal 233 was corrected to the exact 248 total, not relaxed to a range.
- Python source inventory: 103 modules / 962 direct, baseline 35/890/22 plus
  Stage 1 15; 18 child probes, missing/duplicate/expected skip 0.
- `npm --prefix frontend run lint`: PASS.
- Existing Python targeted regression: 138/138 PASS (legacy 14, history adapter 44,
  prepared content 18, approved write 24, client gate 21, Python coordinator 15,
  storage fixture runner 2). Including display contract: 157/157 distinct direct
  tests in 8 modules. FAIL/ERROR/SKIP and inventory issues 0. All guarded reports
  unexpected 0; coordinator synthetic negative outcomes satisfy their expected
  contracts (not product failures). Restoration/patch restoration/cleanup true.
- Node selected entrypoints: 33/33 total, missing/duplicate/extra and unexpected
  guard violations 0; restoration/patch restoration/cleanup true. The separate
  Node coordinator 9 tests are not added to the inventory direct count.
- Production paths backend/, frontend/src/, package/lock/config have no content
  diff; production import scan found no v2 fixture/helper dependency. No build
  needed because only test/docs files changed; actual v2 UI/runtime is unverified.
- Pre-commit Git audit after Slice 1 verification: same branch/HEAD, staged 0,
  tracked modified 5, untracked 6, unmerged 0. `git diff --check` PASS. No Git
  writes occurred during Slice 1 implementation/verification; a separate commit
  approval is now being carried out.
- Protected feature: HEAD 609163e9dc7ff8b6bbc5ee13c34e7f8020910c54,
  9 modified / 10 untracked status entries preserved. Main remains
  f779e252b823bbd724c8be277c54d494d3b93f89 with only the existing protected README
  change; its SHA-256 remains
  5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328.
  No command wrote to either protected worktree.

The last regression process exited 0. A log-summary JSON parser initially failed
because stdout/stderr reports shared a line boundary; parsing the existing captured
output by complete JSON-object boundaries recovered all seven successful reports.
No tests were rerun for that reporting issue and no credit-limit stop was observed.

Commands (from this worktree; explicit approved executables):

```powershell
$py = 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe'
$node = 'C:\Program Files\nodejs\node.exe'
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_contract
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:canonical-review-renderer --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_legacy_compatibility tests.test_review_history_adapter tests.test_review_history_prepared_content tests.test_review_history_approved_write tests.test_review_display_client_gate tests.test_full_test_entrypoint tests.test_storage_fixture_runner
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:ai-format --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-regressions --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& $py -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
git diff --check
```

## v2 body scope / Exact document contract

Body only; exact six top-level keys, block/run limits and codepoint rules in the
shared schema/spec. No title/notice/chart changes. v1 validators still reject v2.

## Role vocabulary / Ownership and order

Basic has 6 roles; advanced 9. Exact named fields, local block refs and independent
machine enums. x-field-order traversal = section block_ids = contiguous document
order. No duplicate/orphan/cross-section refs, and no cycles by construction.

## Canonical identity / Confidence and missing

Full document identity, not text alone. Changed confidence with equal text cannot
reuse approval. high/medium/low and missing[] are independent; labels are refs,
not inference inputs. Collapsed content must pass whole-document admission.

## Approval bundle / v1-only versus paired / Corruption

Schema discriminator distinguishes legitimate v1 absence from corrupt paired
data. One admitted source/objective, pinned compiler versions, independent
validation, exact compiler outputs and semantic coverage precede atomic approval
and atomic publication. No partial persistence or good-side recovery. Reference
witnesses are test oracles, not new runtime approval tokens or cryptography.

## Execution identity / Display negotiation / Replay

Keep existing execution body fingerprint and authenticated key scope; capability
is not a fingerprint member. Early capability eligibility rejects unsupported
input without effects. Whole bundle validation precedes representation selection
and projection. Spec includes A–I replay matrix and same-key/different-body conflict.

## Cache/history boundary

Current default 300s process-memory cache is not durable. Authorized history GET
can redisplay approved data; it is not a POST idempotency lookup. Cache expiry or
restart with no safely associated record does not promise free reexecution.

## Generation states / Rollout matrix / Rollback floor

Slice 1 no runtime support; future bridge generation OFF; activation normal
structured ready only. All fallback/missing_key/error/empty stay v1-only.
The spec freezes ten rollout/rollback combinations. Once paired storage exists,
bridge is rollback floor; pre-bridge rollback is not supported safe rollback.

## Shared vectors

Three valid source witnesses (basic high+[], basic medium+missing, advanced low+[]),
both bundle variants, 24 malformed document and 17 malformed bundle mutations,
four successful replay combinations and seven generation states. Additional tests
cover unsupported capability, body conflict, cache miss, no projection after any
bundle rejection, exact Unicode, source coverage and unchanged actual v1 compiler/A1.
Both languages read the same schema/corpus; helpers are under tests/scripts only.

## Slice plan

1. This specification, shared vectors and reference contract tests only.
2. Pure production v2 compiler/admission and atomic approval, independently reviewed;
   no runtime connection until a subsequent slice.
3. Versioned history/cache read/write support and integrity preservation.
4. Bridge capability gate and representation projection without a new execution.
5. Dual frontend admission/renderer and UI regression.
6. Rollout/rollback evidence, then separately authorized ready-only activation.

## Decisions

All contract decisions above are Slice 1 targets, not activated product behavior.
Keep v1 production behavior and all old v1 expected cases unchanged. Approval of
this slice does not authorize connecting v2 to cache/history/API/frontend.

## Remaining / Unverified

Slice 2 pure compiler/validator/approval is independently approved and committed.
Slice 3 architecture was held; the clarified durable contract above awaits review.
Persistent dual history/cache, actual
cross-version replay, bridge rollout, activation and frontend/device remain
unimplemented. The process-local factory receipt is not a durable storage seal.

The Slice 1 Minor is addressed: all 41 negative vectors now pin stable expected
codes, checked by production/Python reference/JS reference. No separate taxonomy
or production import of a test helper was introduced.

## Next Step

Use the Slice 3 contract clarification and Next Step above. Review it before
separately authorized pure 3A implementation; no runtime connection. Never
deserialize an ApprovedReviewBundle or rebuild v2 from raw semantics on reads.
History uses a non-authenticating durable digest under the stated writer/storage
trust assumptions; cache retains its process-local receipt and existing identity/
TTL boundaries. Client negotiation/frontend/activation remain later slices.
