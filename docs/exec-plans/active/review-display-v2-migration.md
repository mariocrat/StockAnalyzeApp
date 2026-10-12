# Review display v2 migration — Slice 1

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

Production compiler/seal/persistence, cross-version runtime replay, bridge rollout,
generation activation and UI/device evidence remain unimplemented. Test-only
witnesses and modeled zero-effect replay are not evidence that production v2
execution or storage works.

The independent-review Minor is non-blocking: 41 negative vectors currently
assert rejection, while the reference contract tests do not pin a per-vector
expected error code/rejection reason. Add stable codes with the production
validator in Slice 2 and bind the vectors then; do not create a separate error
taxonomy in the test-only validator.

## Next Step

Request independent review of Slice 1, especially atomic approval/read integrity,
execution/capability separation and ownership/traversal. After approval and a
separate implementation request, Slice 2 builds the pure v2 compiler/admission
and whole-bundle approval with these unchanged vectors; no runtime connection.
