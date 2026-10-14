# Review display v2 migration

## Final integration follow-up — Current Status (2026-10-15)

Started clean on integration/broker-import-ux-main at
a2ab06a31474c5f62be6181b358d7d91018b4f27, after the approved 15-file Slice 6
commit `feat: prepare review display v2 activation`. This follow-up changes
tests, the chart handoff harness, inventory and documentation only.

### Fixes / Contract evidence

- The producer fixture replaced the shared stdlib datetime.datetime globally.
  main's dynamic exact-type check then accepted the replacement subclass, while
  the execution cache's earlier imported datetime class rejected it. One official
  selected producer matrix reproduced the cache issuance ValueError in all 20
  subcases. The pre-cache main contract already required exact UTC datetime;
  production creates these timestamps internally, not from an API date input.
- Freeze only account/access datetime consumers through a fixture-owned module
  namespace, and use the existing idempotency clock seam with ordinary UTC datetime
  values. Do not change production type admission. The producer asserts that main
  still uses the real stdlib module/type. Cache coverage rejects an equal-valued
  datetime subclass on both factory issuance and HTTP replay, without side effects.
- Split the chart handoff's independent basic, advanced, failure/legacy, history
  title and paired cohorts into five fresh H4 children. Each retains the existing
  60-second deadline and original route/storage/cache/adapter assertions. Every
  stage must have its exact coverage, zero unexpected accesses and successful
  restoration before one final fixture publication. Missing/duplicate stage,
  child error, timeout and failed lifecycle do not publish partial evidence.
- Add fixed relative wildcard sources (`from . import *`, `from ..core import *`,
  relative durable wildcard plus call) to both existing guard tests. The current
  conservative backend.core wildcard rejection and exact admitted edges remain.
- Align current TESTING/quick-verify counts and their test with the actual
  inventory. Historical results retain their old numbers. No production source,
  frontend header, environment/config file or Android file changed.

### Timed diagnostics / Actual verification

All execution uses the approved Python with -I -X utf8 -B and official
tests/run_isolated_tests.py, synthetic H4-owned stores and blocked external I/O.

- Producers: **8/8 PASS**, including all four previously reported ERROR cases.
- strict_writer: **23/23 PASS** via registered --test-case groups of
  4/4/4/4/4/3. Observed testcase time totals 102.26s; longest nested mutation case
  is 32.51s. Every child restores patches/environment and cleans its owned root.
  No single testcase hangs. The original timeout's exact cutoff stage is not
  recoverable from the supplied 120s finding; no claim about that missing trace
  or measured historical baseline timing is made.
- write_content: **25/25 PASS** via 5/5/5/5/2/2/1 selected groups. Exact-type
  mutations take 63.19s; total testcase work is 100.90s. Shared class setup costs
  29.84–32.42s per child, so normal complete coverage exceeds the old 120s budget.
  Class setup and finite nested mutation matrices account for measured cost;
  cleanup is below 0.003s. These two testcase files are unchanged since the
  pre-Slice-6 HEAD. Their source identity alone is not a timing baseline proof.
  While registering the new coordinator test, the next content selector refused
  the temporarily incomplete inventory before executing any case. After adding
  that ID, only the five unexecuted cases ran; successful earlier groups were not
  repeated.
- Node: **71/71 PASS** (ai-chart-source 46, canonical renderer 23, idempotency 2).
  Actual backend stages complete in basic 19.193s, advanced 19.188s, failures
  13.947s, titles 20.285s and paired 26.390s. Their sum is 99.002s and includes
  repeated child startup. Each stage is below 60s; no observed hang or lifecycle
  failure. Existing current/history/export/cache, body/chart/card identity,
  v1 header and fail-closed contracts all pass. Node coverage missing/extra/
  duplicate, guard violation and unexpected access are zero; cleanup succeeds.
- Related Python: **151/151 PASS** — cache 14, idempotency 14, display 33, durable
  28, activation 14, paired history 23, coordinator 16, docs 7, storage runner 2.
  With producers and the two selected cohorts: **207 distinct direct PASS**.
  Guarded unexpected accesses/violations are zero; restoration, patch restoration
  and cleanup succeed. Coordinator intentional negative probes retain their
  expected evidence and null suite counters.
- Inventory: Python **108 modules / 1070 direct / 18 separate probes**;
  baseline 35/997/22 plus Stage 1 16. Node **23 entrypoints / 259 direct**.
  No missing/duplicate/extra or missing Node source dependency. The only new
  direct ID is the chart-handoff coordinator protocol regression.
- Frontend lint and production build pass. Final git diff --check and Git scope
  are checked after this plan update; no stage/commit/push/merge/rebase.

### Remaining / Next Step

Keep activation default OFF, frontend advertisement review-display.v1 and Android
WebView/device verification NOT RUN. No live OpenAI/provider/production DB access.
Full TestOnly and the original monolithic timeout commands were not repeated;
the unchanged Python single-child default can still hit a cumulative deadline.
The selected-case PASS ledger is not a whole-suite PASS claim. Any future full
run must address that scheduling boundary through reviewed bounded cohorts, not
an arbitrary timeout increase. Re-review these focused integration corrections;
real-device smoke and actual activation remain separately authorized follow-ups.

## Slice 6 — Activation preparation (2026-10-14)

Started clean on integration/broker-import-ux-main at
96965585416e3197ab9d49c4e203325a0c6ada92 after approved Slice 5 commit.
Authorized: default-OFF production generation wiring and isolated ON/OFF evidence.
No deployment, live environment change, header advertisement or actual activation.

### Decisions / Remaining / Next Step

- ALPHAMATE_REVIEW_DISPLAY_V2_ENABLED defaults OFF; only explicit true opts in.
- Pair only approved ready/openai structured model semantics; low-confidence
  chart-rules substitution, missing/error/empty and fixed fallback stay v1-only.
- Reuse the original admitted source, snapshot, prepared history content and
  one ApprovedReviewBundle through typed atomic SQL write and whole cache receipt.
- Fresh responses and cache/history replay select admitted bodies after whole
  approval, independently of the unchanged execution fingerprint.
- Frontend continues advertising review-display.v1. Android/device smoke remains
  NOT RUN; actual production activation and rollout require separate authorization.
- [x] Implement and verify isolated actual HTTP ON/OFF, failures and replay.
- [x] Independent Slice 6 review approved (Blocker 0 / Major 0 / Minor 1).
- Next Step: keep activation OFF; re-review the integration follow-up above and
  complete Android/device smoke before any separately authorized rollout.

### Implementation / failure boundaries

The existing configuration resolver reads the new setting; unset/false/unsupported
values keep generation OFF. No environment/config file was edited. The frontend
header helper remains byte-identical and pinned to review-display.v1.

The finalizer retains the original selected ready model source only after existing
safety/body/envelope/history-content approval. With explicit ON, it compiles one
ApprovedReviewBundle, checks its v1 body/A1 against the original snapshot and,
when storage is enabled, captures the original typed source/snapshot/prepared
content/bundle association. Paired errors are outside fallback handling: no good-side
publication, fallback re-generation or partial v1 write. Default OFF preserves the
original snapshot/history approval keys and v1 route output.

The route sends that same bundle to the existing whole execution cache and its
typed capture to the atomic paired writer. It keeps the v1 compatibility response
internally and selects only the admitted body for the fresh client response.
No extra model/access/history operation; no capability in the request fingerprint.
No storage/no idempotency key still performs one approved execution/projection.

Known post-commit publication failures preserve the inserted owner/id for existing
owner-scoped delete/refund compensation, once, without an automatic re-execution.
Unknown commit outcomes return failure, retain the existing pending key/access and
require reconciliation; a same-key retry while pending returns the existing 409.
Normal TTL/restart semantics remain unchanged: this is not a durable POST ledger
or a guarantee after cache loss/expiry. Separate DBs/cache are not a distributed
atomic transaction. No post-commit SELECT is required to retain the known id.

OFF affects new generation only. Existing approved paired cache/history still
use whole admission and dual projection when read by a dual client; this preserves
the approved bridge rollback floor. Old v1-only executions are never upgraded.

### Actual verification

Official H4 with the existing approved Python/Node executables; synthetic model
outputs, account/wallet/history temp stores and blocked providers/network only.

~~~powershell
$py = 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe'
$node = 'C:\Program Files\nodejs\node.exe'
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_activation
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_negotiation tests.test_review_execution_cache tests.test_review_history_paired tests.test_review_history_adapter tests.test_review_finalizer_compatibility tests.test_full_test_entrypoint tests.test_storage_fixture_runner
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_history_paired tests.test_full_test_entrypoint
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-chart-source --node-entrypoint test:journal-mobile-ux --node-entrypoint test:ai-idempotency --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run build
git diff --check
~~~

- New activation: 14/14 PASS (25.962s); basic/advanced x v1/dual, original bundle
  identity through SQL/cache, A != B/charts/cards, fallback/low-confidence/empty,
  storage/key absence, no-effect replay, fingerprint/gate, corruption, v2 compile/
  INSERT/publication failure and uncertain commit. Fresh normal ON executes model,
  charges and inserts exactly once; replay adds zero. OFF fresh remains v1-only.
- Existing focused Python: negotiation 14, cache 14, paired history 23, legacy
  history adapter 44, finalizer 18, H4 coordinator 15, storage runner 2: 130 PASS.
  Including activation: 144 distinct PASS; final FAIL/ERROR/SKIP zero.
- Node: 106/106 PASS (canonical 23, actual AI chart/current/history 46, mobile 35,
  idempotency 2); missing/extra/duplicate zero. v1 header/renderer unchanged.
- Guarded unexpected access zero; restoration, patch restoration and cleanup true.
  Coordinator null counters and intentional negative probes keep their contracts.
  No timeout or guard/allowlist expansion. Python inventory: 108 modules / 1069
  direct / 18 separate probes, baseline 35/997/22 plus Stage 1 15. Node inventory
  remains 23 entrypoints / 259 direct, missing/extra/duplicate/dependencies zero.
- First activation run passed 12/14; two harness assertions failed: None history
  state was treated as a dict, and first SQLite schema bootstrap was compared to
  a nonexistent pre-run DB. Corrected only the wrapper/zero-row rollback check;
  second activation run passed all 14. No third same-approach attempt.
- Initial existing regression batch passed 128/130. The old Slice 3B AST forbade
  any main paired writer call, and the coordinator kept the previous 1040 baseline
  literal. Preserve/strengthen runtime OFF traps for compiler/capture/route writer;
  retain factory separation in main; pin the exact new 1054 baseline. Reran only
  those two affected modules: 38/38 PASS. Other successful modules were not repeated.
- Frontend lint/build, git diff --check and new-source trailing-whitespace checks
  PASS. Final process setting has no true opt-in; no production setting was read
  or changed remotely.
  No full TestOnly, live OpenAI/provider/production DB, deployment, Android build,
  header activation or actual production ON. Three existing pure-layer docstrings
  now describe the typed activated caller; their behavior is unchanged.

### Independent review guard follow-up

The Slice 6 hold identified two stale runtime-import assertions, not a production
behavior failure. The existing display and durable-storage guards now permit only
the exact `main.py` bundle validator import/call and the exact `ai_review_v2.py`
bundle/durable-capture import/calls. Synthetic wrong-file, wrong-symbol and
incomplete-import cases remain rejected; the general pure-layer and no-I/O checks
remain in force. No production code changed in this follow-up.

- Official H4 guard modules: 33 + 28 PASS; activation/history/cache regressions:
  14 + 23 + 14 PASS. All guarded unexpected-access counts were zero; restoration,
  patch restoration and cleanup passed.
- Python inventory: 108 modules / 1069 direct / 0 missing or duplicate. Node
  inventory: 23 entrypoints / 259 direct / 0 missing, extra, duplicate or missing
  source dependency. Frontend lint/build and `git diff --check` passed.

### Remaining / Git

Package-alias follow-up: the remaining guard Major was an AST gap for indirect
access through `import backend.core as <alias>`. Both existing guards now share
a test-only canonical import-binding resolver; package/direct aliases, nested
imports and annotated accesses are checked by module/symbol and call-versus-access
kind. The actual Slice 6 imports and exact permitted access counts remain pinned.
Wrong-file, renamed-alias, forbidden-symbol/call and bare-module accesses are
negative subcases; the real approved edges and aliased validator call pass.
Pure-layer/I/O rules and production code were unchanged in this follow-up.

Wildcard follow-up: `ImportFrom` star imports do not create named bindings, so
the alias resolver alone could not see `from backend.core import *`. Both guards
now share a test-only AST check that rejects star imports from `backend.core` and
the exact guarded review modules (including their relative-import forms), before
access counting. Negative subcases cover the bare package wildcard, later
bundle/durable access and calls, and direct wildcards from both approval modules.
Explicit imports, aliases, nested imports and the exact admitted Slice 6 edges
remain unchanged. No production code changed.

- Official H4: the five guard/activation/history/cache modules passed 112/112.
  After adding annotation/nested-import coverage, both selected guards passed
  again (2/2); repeated cases are not counted as new direct tests. Unexpected
  access/violations were zero; restoration, patch restoration and cleanup passed.
- Python inventory remains 108 modules / 1069 direct; Node remains 23 / 259,
  with zero missing/extra/duplicate. Lint/build passed; final whitespace/Git checks
  are recorded with the completion report. The wildcard cases are subcases of
  existing guard tests, so no testcase ID or inventory edit was needed.

Independent Slice 6 review was approved (Blocker 0 / Major 0 / Minor 1). Its
relative wildcard fixture Minor is now covered by both guard regressions in the
integration follow-up above; conservative `backend.core` rejection is retained.
Android WebView/ad/scroll smoke is NOT RUN due to unavailable JDK/SDK/adb/device/
emulator. The setting must remain OFF pending separate Android verification and
authorization for activation/rollout/rollback.
Slice 6 was committed as a2ab06a31474c5f62be6181b358d7d91018b4f27 with exactly
15 approved files and a clean worktree. The old 13 modified / 2 untracked snapshot
was pre-commit evidence, not current status. Follow-up state is described above;
neither original feature nor main worktree files are modified by this task.

## Slice 5 — Historical approved implementation (2026-10-14)

Independently approved code/browser verification and committed at
96965585416e3197ab9d49c4e203325a0c6ada92 before Slice 6 began.

Started clean on integration/broker-import-ux-main at
78cf71a030e71ae4d5989fb66d81ad1c3356a1be after independent Slice 4 approval
(Major 0 / Minor 0) and commit. Authorized: frontend dual body admission and
semantic renderer, related isolated tests/inventory and this plan only.
Backend contracts and generation remain unchanged. The existing outgoing
review-display.v1 header remains pinned; dual capability advertisement, rollout
and paired production generation require the later separately approved Slice 6.

### Decisions / Verification / Remaining

- Keep the original v1 validator/renderer, including every non-body surface.
- Admit the entire v2 body before rendering any visible or collapsed section.
  Use declared roles/enums/local block references, exact approved runs/separators;
  never parse semantic labels, compile raw review fields or repair rejected bodies.
- Current result/history body, AI chart selection and optional basic-to-advanced
  CTA must share dual body admission. AI chart auxiliary remains its original B;
  SQL chart A cannot repair an invalid v2 response or missing approved auxiliary.
- [x] Confirm requested worktree/branch/HEAD/clean status and inspect current paths.
- [x] Implement bounded production v2 validator and semantic renderer.
- [x] Official focused Node/H4 regressions, inventories, lint/build/diff checks.
- [x] Independent Slice 5 code review and browser visual verification at 320px / 360px.
- [ ] Android WebView/device smoke test — NOT RUN: this execution environment has no JDK,
  Android SDK, adb, device, or emulator. Android code/config remain unchanged.

### Implementation

New reviewDisplayV2.js admits the exact body grammar, bounded Unicode/runs/blocks,
fixed roles, enum/collection limits, unique ownership and explicit field traversal,
references/order and full canonical identity. Errors have controlled codes; all
24 shared negative document vectors match their pinned rejection codes. It imports
no shared fixture/schema/reference helper. This is transport/display validation,
not a new source approval or frontend authenticity proof.

New ReviewBodyRenderer uses the original CanonicalReviewRenderer unchanged for v1.
V2 renders declared semantic references into scoped cards; field/phase/collapse
labels are presentation shell only. All run text, strong spans, separators and
order remain exact. The complete document, including hidden detail/questions, is
admitted before optional empty sections are hidden or native details is collapsed.
Confidence comes from its enum, independently of missing_information and labels.

Live and admitted history AI body use this same renderer; chart selection and the
optional live basic-to-advanced CTA use the same dual body validator/type check.
V2 cannot fall through to legacy SQL A/raw chart extras if B is missing. The optional
CTA also rejects missing/malformed B for v2; correctly approved empty B is valid.
V1's original chart fallback and CTA behavior are preserved. All chart documents,
history titles and other surfaces still use the unchanged v1 surface validator.
No loader request, fingerprint, consent/entitlement/ad/AI/storage path was changed.

### Actual Verification

Approved existing Python/Node executables and official H4 coordinator only:

~~~powershell
$py = 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe'
$node = 'C:\Program Files\nodejs\node.exe'
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:canonical-review-renderer --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:ai-chart-source --node-entrypoint test:journal-mobile-ux --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:review-selection --node-entrypoint test:broker-import --node-entrypoint test:app-navigation --node-entrypoint test:ai-idempotency --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-regressions --node-executable $node
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_full_test_entrypoint
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_negotiation --test-case ReviewDisplayNegotiationTest.test_fresh_dual_requests_generate_only_v1_then_replay_without_more_execution
& $py -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run build
git diff --check
~~~

- Node direct: 146/146 PASS in eight entrypoints: canonical 23, actual AI chart/
  live/history 46, journal-mobile 35, legacy 11, selection 5, broker 19, navigation
  5, idempotency 2. Includes 11 new IDs (eight canonical and three chart), exact v1
  HTML, three v2 goldens, all negative document vectors, Unicode/strong/escaping,
  role/phase/confidence/missing metadata, collapsed-tail and empty-section behavior.
- The existing chart handoff now captures actual typed paired approval, temp SQL
  persistence, whole-row admission and HTTP v1/dual cache/history/export responses
  for basic/advanced. SAME original bundle is used by cache and SQL. Actual original
  frontend JSX and React renderer retain body/B/cards; A != B, replay/charge/insert
  zero-effect assertions and empty/missing B/no-fallback checks pass. No oracle
  replacement or mocked display renderer. Synthetic model inputs only.
- Python: coordinator 15/15 and existing selected generation-OFF case 1/1 PASS.
  Fresh dual basic/advanced still generate v1-only; replay adds no execution.
  Separate Node coordinator 9/9 PASS, not counted as manifest direct tests.
- All commands exit 0; final FAIL/ERROR/SKIP and missing/extra/duplicate zero.
  Guarded unexpected accesses zero; restoration, patch restoration and cleanup
  true. Coordinator intentional negative probes retain their expected contracts.
- Final Node inventory: 23 entrypoints / 259 direct; Python 107 modules / 1055
  direct / 18 separate probes unchanged. Register exact new source reads and test
  IDs/hashes; no runner/guard/timeout/allowlist expansion. Coordinator's old 248
  literal is updated to the exact 259 total, not relaxed to a range.
- Lint and final Vite build PASS; git diff --check and new-source whitespace PASS.
  After the final missing-B CTA guard/test, reran only chart/mobile, Node inventory,
  lint and build. Repeated cases are counted once. No test approach failed. One
  metadata patch-format failure wrote nothing; context-only apply_patch succeeded.
- Original v1 renderer/header helper, all backend runtime/cache/history, schema/
  vectors, package/lock/config/env, Android and official guards remain unchanged.
  No full TestOnly, actual OpenAI/provider/production DB, install or Android build.

Changed 14 files: production TradingJournal.jsx, App.css, aiReviewChartSource.js,
basicReviewInput.js and new ReviewBodyRenderer.js/reviewDisplayV2.js; tests
canonical-review-renderer.test.js, ai-review-chart-source.test.js,
journal-mobile-ux.test.js, review-render-evidence.js, review_chart_handoff.py,
test_full_test_entrypoint.py, test_inventory.json; this plan.
Git: same branch/HEAD, staged 0 / modified 12 / untracked 2 / unmerged 0.
Protected feature remains 609163e9dc7ff8b6bbc5ee13c34e7f8020910c54 with its 9
modified/10 untracked entries; main retains f779e252b823bbd724c8be277c54d494d3b93f89
and its existing Play README change. No command wrote either worktree's files.

Browser visual verification passed at 320px and 360px using the production frontend
build with local sanitized fixtures; screenshots and DOM/layout evidence are saved
outside the repository. Android WebView/device rendering and the real bottom-ad
interaction remain unverified (NOT RUN because the execution environment lacks the
Android toolchain and a device/emulator). Android code/config are unchanged.

Next Step: run the Android Debug build/install and real-device WebView smoke test
when JDK, Android SDK/adb, and a device/emulator are available. Capability
advertisement, rollout/rollback and production activation/generation require later
separate authorization (Slice 6).
No stage/commit/push/merge/rebase is authorized.

## Slice 4 — Historical approved implementation (2026-10-14)

Independently approved Major 0 / Minor 0 and committed at
78cf71a030e71ae4d5989fb66d81ad1c3356a1be before Slice 5 began.

Started clean on integration/broker-import-ux-main at
33b88a18f964ef416e00fef782c3ce6c32b93889. The user confirmed independent
Slice 3C approval (Major 0 / Minor 0) and its commit. This step authorizes the
backend bridge only; frontend dual admission/rendering belongs to Slice 5.
Generation remains v1-only. No stage/commit/push/merge/rebase is authorized.

### Decisions / Implementation

The existing X-Review-Display-Contract header accepts EXACTLY one value:
review-display.v1 (v1 client), or review-display.v2 (dual reader accepting v1/v2).
Missing, unknown, malformed, whitespace/case/parameter/comma or duplicate values
retain the existing fixed HTTP 426 before execution lookup/charge/provider/history.
Capability is separate from request payload and execution fingerprint.

Whole cache receipts and whole SQL-row durable admissions are checked before
selection. For paired approved content, a dual reader receives the exact approved
v2 body in display_snapshot; a v1 reader receives the unchanged approved v1 body.
summary remains the original v1 compatibility alias, not a v2 body source.
No internal bundle/provenance/durable wrapper is exposed. AI charts/chart_cards
remain B, separate from journal SQL chart A; list remains its existing metadata
projection after complete admission. Old legacy/v1-only results always remain v1;
bodyless terminals remain bodyless. Missing v2 never triggers compilation or AI.

Ordinary new/expired/restarted executions retain existing consent/entitlement/
TTL rules and generate v1-only. Existing hits have no new AI/charge/history write.
Paired corruption remains a whole-cache error or fixed unavailable history record,
even for a client requesting the undamaged representation. No history POST ledger.

### Verification / Remaining / Next Step

- [x] Reconcile actual clean worktree, approved Slice 3C and existing contract.
- [x] Implement early gate and post-admission cache/history body selection.
- [x] Official H4 negotiation and existing v1/cache/history/gate regressions.
- [x] Inventory/lint/diff checks and protected worktree preservation.
- [ ] Independent Slice 4 review; no commit authorized.

Actual verification uses the approved
D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe with -I -X utf8 -B and
tests/run_isolated_tests.py. Model/providers are mocked or blocked; databases are
H4-owned synthetic/temp SQLite. No live AI, provider, production DB or build.

- New negotiation: 14/14 PASS in 31.503s. The first run passed 13/14; the sole
  error was the test replay helper parsing the expected HTTP 500 plain
  "Internal Server Error" as JSON (JSONDecodeError). Status and no-effect checks
  had already passed. Corrected only the helper; the second module run passed.
- Then strengthened two existing IDs: same ORIGINAL issued bundle/approval
  through cache and actual SQL history, matching selected body/A1/AI B/history
  identity/wallet across v1/dual/reopen/export; and recomputed valid durable
  digest/encoding negatives reaching whole admission. Both selected cases
  passed 2/2 in 12.114s, counted once in the 14 distinct cases.
- Existing cache 14/14 (27.297s), old idempotency cache 14/14 (56.483s), paired
  history 23/23 (35.212s), legacy/canonical history adapter 44/44 (17.265s),
  display contract 33/33, H4 coordinator 15/15 and storage runner 2/2: 145 PASS.
  The combined official command exited 0. Reports were recovered from the
  captured JSON object boundaries where stdout/stderr shared a line; no rerun
  for reporting. All seven complete lifecycle reports are present.
- Existing client gate: two official 8-ID selectors, 8/8 (12.152s) and 8/8
  (13.609s). Cover missing/unsupported/malformed/duplicate headers, early read
  rejection, old unapproved cache, unrelated routes, all five idempotency states,
  gate/lookup/charge/model order and history compatibility/ownership/opt-in.
  The previously twice-timed-out whole 21-case command was not repeated.
- Total distinct focused Python: 175 PASS in nine modules; final FAIL/ERROR/SKIP
  zero. Guarded unexpected access zero; restoration, patch restoration and cleanup
  true. Coordinator intentional negative probes satisfy their expected contracts.
- Python inventory: 107 modules / 1055 direct / 18 separate probes, missing/
  duplicate/expected skips zero; baseline 35/983/22 plus Stage 1 15. Register
  exactly the 14 new guarded cases; no runner timeout/guard/allowance change.
  Node inventory remains 23 entrypoints / 248 direct, missing/duplicate/extra/
  source dependencies zero. This is inventory verification, not Node execution.
- Existing frontend lint and git diff --check PASS. Frontend runtime, model,
  environment, schema, SQL writer, durable codec/digest/resource bounds unchanged.

Commands:

~~~powershell
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_negotiation
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_negotiation --test-case ReviewDisplayNegotiationTest.test_paired_history_list_detail_reopen_export_project_same_admission_and_chart_sources --test-case ReviewDisplayNegotiationTest.test_corrupt_paired_history_never_selects_good_side_or_legacy_fallback
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_execution_cache tests.test_ai_review_idempotency_cache tests.test_review_history_paired tests.test_review_history_adapter tests.test_review_display_contract tests.test_full_test_entrypoint tests.test_storage_fixture_runner
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
git diff --check
~~~

For the two gate commands use that same Python/coordinator,
tests.test_review_display_client_gate and repeated
--test-case ReviewDisplayClientGateTest.<method> for these exact groups:

1. test_missing_header_blocks_execute_before_lookup_charge_refund_provider_history;
   test_wrong_version_blocks_execute_before_lookup_charge_refund_provider_history;
   test_malformed_and_comma_values_are_fixed_fail_closed_on_actual_http_route;
   test_duplicate_header_lines_including_identical_values_are_unsupported;
   test_history_list_detail_export_unsupported_gate_precedes_reads_adapter_and_all_effects;
   test_unsupported_clients_cannot_read_existing_replay_or_change_cache_wallet_history;
   test_supported_old_cache_without_sealed_approval_never_returns_raw_or_reexecutes;
   test_unrelated_journal_routes_do_not_require_display_header.
2. test_idempotency_valid_done_replays_without_effects;
   test_idempotency_valid_pending_preserves_retry_conflict;
   test_idempotency_fresh_key_executes_once;
   test_idempotency_payload_mismatch_preserves_conflict;
   test_idempotency_valid_expired_entry_keeps_ttl_behavior;
   test_supported_http_execution_orders_gate_lookup_charge_model_and_replay_has_zero_effects;
   test_supported_history_uses_whole_record_adapter_for_canonical_legacy_unsafe_without_db_writes;
   test_supported_header_preserves_history_authentication_storage_opt_in_and_ownership.

Changed files (15): new backend/core/review_display_capability.py; existing
review_display_client.py, review_execution_cache.py, review_history_paired.py,
review_history_adapter.py, ai_review_v2.py (history wrapper only), backend/main.py;
new tests/test_review_display_negotiation.py; existing test_review_execution_cache.py,
test_review_display_client_gate.py (unsupported future version is now v3),
test_inventory.json, isolation_inventory.py, test_full_test_entrypoint.py,
test_storage_fixture_runner.py; this plan.

Git remains integration/broker-import-ux-main at
33b88a18f964ef416e00fef782c3ce6c32b93889, staged 0 / modified 13 / untracked 2 /
unmerged 0. Protected feature remains 609163e9dc7ff8b6bbc5ee13c34e7f8020910c54,
9 modified/10 untracked; main remains f779e252b823bbd724c8be277c54d494d3b93f89
with only its existing Play README modification. No command wrote either worktree.

Next Step: independent Slice 4 review of early syntax gating, whole admission,
execution identity and v1/v2 projections. Frontend dual-reader/device, rollout and paired production generation are
later slices. No activation, environment/DB schema or other-worktree changes.

## Slice 3C — Historical implementation (2026-10-14)

Independently approved Major 0 / Minor 0 and committed at
33b88a18f964ef416e00fef782c3ce6c32b93889 before Slice 4 began.

Started clean on integration/broker-import-ux-main at
f2db0ad30ad9487cc3eb9318d8750a4c1c19e779 after independent Slice 3B approval
(Major 0 / Minor 0). The user authorizes process-memory whole execution cache
support only. Generation remains v1-only; no negotiation, durable POST ledger,
frontend, history schema, env/config or Git mutation is authorized.

### Decisions / Implementation

ApprovedCachedExecution captures the issued ApprovedReviewBundle, original
snapshot and immutable complete response bytes, including access/history identity.
Its process-local weak receipt binds the actual cache key, existing execution
fingerprint and original expiry. Done entries preserve existing result/snapshot
keys and add this typed execution receipt. Whole receipt/bundle/snapshot/response
validation precedes lookup, pruning, trimming or v1-compatible response projection.
Corruption is an error before execution, never a miss. No read-time compiler,
history search, durable wrapper or AI repair is used. Snapshotless rejected terminals
remain bundleless and retain complete response integrity.

Normal finish derives v1_only approval from the existing original snapshot. An
explicit issued paired bundle is accepted only at the internal cache publication
boundary; original live source-to-snapshot identity is checked there once.
Production generation supplies no paired bundle. TTL clock is exposed as a pure
helper so tests advance time without modifying issued immutable expiry. Existing
tests simulate body conflicts using actual changed requests and capacity pressure
with valid pending entries, rather than substituting issued execution identity.

### Verification / Remaining / Next Step

- [x] Inspect actual cache, finalizer/snapshot, whole bundle and H4 boundaries.
- [x] Implement whole cache receipt and add 14 guarded cache regression cases.
- [x] Official isolated cache, v1 route/history and H4 regression verification.
- [x] Exact inventories, lint, diff/scope and protected worktree checks.
- [ ] Independent Slice 3C review; no stage/commit/push authorized.

Actual official H4 results (approved Python 3.12.14, -I -X utf8 -B):

- New whole execution cache: 14/14 PASS; final full-module test phase 31.908s.
  After adding actual empty basic/advanced replay coverage to an existing ID,
  reran that one registered case: 1/1 PASS. Repeated cases are counted once.
- Existing cache 14/14 (63.153s), paired history 23/23 (41.752s), display contract
  33/33, H4 coordinator 15/15 and storage fixture runner 2/2; combined command
  exited 0. All registered counts/lifecycle contracts passed. Its captured output
  was truncated by the tool; no tests were rerun merely to regenerate logs.
- Selected actual v1 route regressions: 13/13 (25.398s); ready/strong body, approved
  AI chart identity, missing-key fallback, safety/invalid-output terminal, refund/
  publication failure, storage off, mutable alias and corrupt-wire behavior pass.
- Selected client gate/cache cases: 8/8 (39.985s); done/pending/body conflict,
  expiry and required-field/malformed/status corruption pass. The previously
  twice-timed-out whole 21-case command was not repeated; official selectors
  retain exact case IDs and original hard timeout/guard/lifecycle checks.
- Total distinct Python coverage: 122 direct PASS in eight modules, FAIL/ERROR/
  unexpected SKIP 0. H4 guarded unexpected accesses zero; restoration, patch
  restoration and cleanup pass. Coordinator-owned intentional negative probes
  satisfy their contracts, not product failures. All providers/model calls were
  mocked or blocked; SQLite/files are H4-owned temporary data only.
- Python inventory: 106 modules / 1041 direct / 18 separate probes; missing,
  duplicate and expected skips zero. Baseline is 35/969/22 plus Stage 1 15.
  Node inventory remains 23 entrypoints / 248 direct, missing/extra/duplicate and
  missing source dependencies zero. No Node test execution is claimed here.
- npm --prefix frontend run lint and git diff --check PASS. No full TestOnly,
  BuildChecks, package install/build, actual OpenAI/provider/private DB or device
  validation was performed.

Commands use D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe and the
official tests/run_isolated_tests.py: --inventory-only, --node-inventory-only;
tests.test_review_execution_cache (then its one updated registered ID);
tests.test_ai_review_idempotency_cache tests.test_review_history_paired
tests.test_review_display_contract tests.test_full_test_entrypoint
tests.test_storage_fixture_runner. The route selection covers the thirteen cases
listed by behavior above; gate selection covers its five idempotency cases and
three required-field/malformed/status cases. No direct unittest execution or
guard bypass, allowance expansion or timeout change was introduced.

Changed files: backend/main.py and new backend/core/review_execution_cache.py;
tests/test_review_execution_cache.py (new), test_ai_review_idempotency_cache.py,
test_review_display_client_gate.py, test_review_display_contract.py,
test_storage_fixture_runner.py, isolation_inventory.py, test_full_test_entrypoint.py,
test_inventory.json; this plan. Only the exact cache module may import bundle
approval; storage/runtime graph guards remain otherwise unchanged. Original
history, pure durable primitives, finalizer, fingerprint function, frontend,
model/provider and environment configuration have no diff.

Git: integration/broker-import-ux-main, unchanged f2db0ad30ad9487cc3eb9318d8750a4c1c19e779;
staged 0 / tracked modified 9 / untracked 2. Protected feature remains at
609163e9dc7ff8b6bbc5ee13c34e7f8020910c54 with 9 modified/10 untracked entries;
main remains at f779e252b823bbd724c8be277c54d494d3b93f89 with only its existing
Play README change. No command wrote to either protected worktree.

Next Step: independent Slice 3C review of whole receipt/bundle, original key/body/
expiry and access/history associations, fail-closed behavior and v1 compatibility.
Report and wait; no commit authorized. Negotiation, frontend v2, paired generation,
durable POST replay ledger and rollout remain later work.

## Slice 3B — Historical implementation (2026-10-14)

Independently approved Major 0 / Minor 0 and committed at
f2db0ad30ad9487cc3eb9318d8750a4c1c19e779 before Slice 3C began.

Started clean at 39f561307d929f53eb0148a9354cad2f23a26e44 on
integration/broker-import-ux-main. The user confirmed final independent Slice 3A
approval (Major 0 / Minor 0) and separately authorized this history integration.
The approved durable contract, codec/resource limits and generation eligibility
are unchanged. The Slice 3B implementation is independently approved
(Major 0 / Minor 0); this scoped commit is separately authorized.

- [x] Typed paired SQL write, actual locked ID allocation, one complete INSERT.
- [x] Frozen admitted result prepared before commit, acknowledgement only afterward.
- [x] Committed publication failure versus unknown commit outcome boundaries.
- [x] Raw SQL owner/context/snapshot retention and reserved-marker read dispatch.
- [x] Whole admission before list/detail/reopen/export v1-compatible projection.
- [x] SQL chart A versus approved AI charts/cards B and approved empty B retention.
- [x] Existing v1/legacy writer/reader/consent/generation regression coverage.
- [x] Official isolated SQL/HTTP tests, inventories, lint and whitespace validation.
- [x] Independent Slice 3B review: approved (Major 0 / Minor 0); the discovery
  finding and correction are recorded below.
- [ ] 3C cache, negotiation, frontend v2 and activation remain future work.

### Implementation / Boundaries

[review_history.py](../../../backend/core/review_history.py) keeps the existing
v1-only 14-bind auto-ID writer intact. Its separate add_paired_review_history
validates original typed capture/write inputs before opening SQL, then uses
BEGIN IMMEDIATE and max(max(id), sqlite_sequence)+1 under that lock. The final
INSERT boundary accepts an issued ApprovedDurableHistoryEnvelope, never a raw
dict. Its fifteen immutable binds include the actual id and one complete wrapper
in existing ai_review_json TEXT. No placeholder, UPDATE, new schema or backfill.

Slice 3A approval gains only validated SQL bind/read snapshot projections and a
factored original-capture/write validator. It retains its live-only ownership
checks and separate durable-read authority. No raw-row write issuance is added.

The full admitted v1 view and CommittedPairedHistoryWrite object are allocated
before INSERT/commit. Its committed flag becomes true only after commit returns.
The writer returns its known id/owner and owned result without a post-commit SELECT.
Optional reread and post-commit close faults carry PairedHistoryPublicationError
with that same result. A commit exception with an ended SQL transaction carries
PairedHistoryCommitUnknown with the reserved id/owner, including acknowledged-write
loss and automatic-rollback simulations. Neither class automatically retries AI,
INSERT, entitlement consumption or compensation. Existing owner-scoped DELETE
and v1 route refund/compensation remain unchanged; there is no distributed atomic
transaction or cross-restart POST deduplication claim.

[review_history_paired.py](../../../backend/core/review_history_paired.py) has no
DB/generation dependency. Its bounded-token root-key dispatch scan preserves
markerless legacy limits and identifies reserved/escaped storage or bundle markers
before paired tree decoding. Malformed/ambiguous JSON also uses rejection-only
paired dispatch. StoredPairedHistoryRow retains actual SQL owner/scalars and four
raw JSON snapshots internally. The strict 3A reader checks the whole wrapper,
both bodies, B, objective/provenance and actual SQL context/snapshot bindings.
Programming/safety callback faults propagate; only controlled contract failures
become the existing fixed unavailable view.

The common history adapter dispatches the typed SQL carrier before any legacy
compiler. Success projects the admitted bundle's v1 body/summary and exact AI B,
with SQL A/trades/access from admitted SQL snapshots. No v2 response or redundant
raw semantic data is published. Body, charts and chart_cards retain complete
approved identity. No SQL A fallback, body regeneration or read-time DB write.
Raw unwrapped reserved markers reject before legacy normalization.

The existing safe_legacy_history_snapshot wrapper remains the single surface for
list/detail/reopen/export. List/detail retain their existing ownership/opt-in gates.
Export forwards the authenticated user's storage flag for paired admission;
storage-off paired rows are unavailable before payload admission, while the old
legacy/v1 data-export behavior is preserved. The only main.py change is this read
flag. No AI generation/finalizer, POST/cache identity or entitlement policy change.
The paired writer/capture/bundle compiler is not called by runtime generation;
normal mocked production requests still write the original v1-only format.

### Verification / Actual outcomes

All tests use the approved Python with -I -X utf8 -B and the official
tests/run_isolated_tests.py boundary, H4-owned synthetic/temp SQLite and mocked
model/market/providers. No live OpenAI/provider/network/private DB was used.

- New paired integration: **23/23 distinct PASS**, first as eight subsets of at
  most three IDs, then final-code 12/11 subsets (25.108s / 19.026s test phases).
  Exact registered IDs retained; no skips or weakened fixture/guard allowances.
  Independent review found the test module imported `ReviewDisplayClientGateTest`
  into its own namespace, so default unittest discovery also collected that
  class's 21 cases. The test now imports the helper module and references the
  class through it. The official default module run then discovered exactly the
  registered 23 cases and passed **23/23** in 39.342s.
  Both basic/advanced A != B and empty/chart-only auxiliary retain exact display
  data; real HTTP list/detail/reopen/export share whole admission. Reserved,
  unknown, partial, duplicate, oversized and malformed carriers, either body,
  auxiliary, objective, row/context and all SQL snapshot corruptions fail closed.
  Recomputed-digest invalid-body/auxiliary negatives reject directly on read.
- SQL trace verifies BEGIN IMMEDIATE before allocation, one full INSERT and zero
  UPDATE/post-commit SELECT. Deleted/high/NULL sequence and safe-id overflow,
  raw dict/read authority rejection, INSERT/commit/result-allocation failures,
  unknown commit with/without an actual row, reread/close publication failure,
  immutable projection copies and owner-scoped compensation pass.
- Actual production-shaped basic/advanced maximum fixture also saves and reopens
  in SQL: 200 source fills, 140 AI candles, 20 markers and 20 cards. Original SQL
  producer A and independently approved AI B/body survive unchanged. Pure codec
  and exact-limit/limit+1 tests remain; resource limits were not changed.
- Related existing Python **203/203 PASS** in 12 modules: durable 28, display 33,
  adapter 44, approved write 24, strict v1 writer 23, history 2, legacy 14,
  history consent 7, coordinator 15, storage runner 2, isolation results 8,
  isolation runner 3. After final commit-result hardening, the maximum fixture
  was rerun and passed; it is not counted a second time.
- Affected existing client gate: **4/4 PASS** via explicit selectors (unsupported
  history access, supported canonical/legacy/unsafe history, auth/opt-in/ownership,
  fresh idempotent v1 execution). The previously twice-timed-out full 21-case gate
  command was not run. Total distinct focused Python coverage is **230 PASS**.
- Official Node canonical/reference + legacy cross-contract + ai-format:
  **33/33 PASS**, missing/extra/duplicate and unexpected guard violations zero.
  These are existing compatibility checks, not a new v2 frontend renderer.
- Official source inventories: Python 105 modules / 1027 direct / 18 probes,
  missing/duplicate/expected skips zero; Node remains 23/248, missing/extra/
  duplicate/dependency issues zero. Only the 23 new Python IDs/migrated registry
  and exact baseline/coordinator counts are added. No boundary/allowlist widening.
- All successful test reports have restoration/patch restoration/cleanup true,
  unexpected guarded access zero and no test-owned temp residue. Existing
  intentional negative coordinator probes satisfy their expected contracts.
- npm --prefix frontend run lint and git diff --check PASS. No build, full
  TestOnly, deployment, production writes or other-worktree changes.

Historical verification failure: before the discovery fix, the full paired
entrypoint exceeded its unchanged 120s child timeout (TimeoutExpired), without a
complete child report. The imported gate class accounts for 21 unintended cases
in addition to the 23 registered paired cases, which is a concrete mechanism
that likely explains the timeout. The old 44-case run was not replayed, so its
exact timing cause cannot be established. After the fix, official default
discovery ran exactly 23 cases successfully; guard, restoration, patch
restoration and cleanup passed. The runner preserves timeout stderr and budgets;
no timeout increase or direct unittest/Node bypass was used.

### Changed files

- Production: review_history.py, review_history_paired.py, review_history_adapter.py,
  review_durable_storage_approval.py, ai_review_v2.py (read wrapper only), main.py
  (export read flag only).
- Tests/meta: test_review_history_paired.py, test_review_durable_storage.py,
  test_review_display_contract.py, run_isolated_tests.py, isolation_inventory.py,
  test_inventory.json, test_full_test_entrypoint.py, test_storage_fixture_runner.py.
- This plan. No frontend, schema migration, env/config, cache or contract-spec diff.

### Remaining / Next Step

Independent review of the 3B SQL authority/atomicity, internal row dispatch,
paired export opt-in and committed/unknown outcome handling is complete with
Major 0 / Minor 0. This scoped commit is the current authorized action; after
reporting it, wait. Generation remains OFF. Cache 3C, client negotiation,
frontend v2, activation and production rollout require separate authorization.

## Slice 3A — Historical implementation (2026-10-14)

Base: integration/broker-import-ux-main at
e7604591ebfaf932c7a7087d2eb671f4b57945c8; started clean (0/0/0/0).
The user confirmed final independent approval of the Slice 3 durable contract;
its two-document commit is the base above. This separately authorized step
implements only its pure 3A layer. The approved contract remains unchanged.

- [x] Paired wrapper, exact field/version/kind, canonical codec and framed SHA-256.
- [x] Plain-type/duplicate/nonfinite/surrogate checks and approved resource bounds.
- [x] Original finalizer source/snapshot/prepared/bundle capture association.
- [x] Typed durable issuance and independent restart-equivalent read admission.
- [x] Required AI auxiliary, separate SQL chart, complete objective/context/binds.
- [x] Current whole-record safety walk with required caller-supplied pure policy.
- [x] Official isolated tests, exact inventories, lint and runtime isolation checks.
- [x] Independent Slice 3A final approval (Major 0 / Minor 0), committed at 39f5613.
- [ ] 3B/3C, runtime connection, negotiation and activation remain future work.

### Timeout diagnostics / Minor follow-up — 2026-10-14

Independent review reported no Slice 3A code Major, but two full client-gate
120-second timeouts. That complete command was **not repeated**. Started with
the same base and preserved 10 uncommitted files; staged/unmerged were zero.

The official Python runner previously selected only entire modules. Added
inventory-validated `--test-case Class.test_method` for exactly one guarded
module, with repeatable selection for small groups. Both parent/child validate
registered identities; probes/coordinators, unknown/duplicate IDs and mixed
modes reject. Subsets retain exact report accounting, sanitized owned storage,
pre-import A1, external/private-access guards and cleanup. Default full-module
coverage, all timeout values and inventory IDs are unchanged. Reports now expose
per-case elapsed time and child bootstrap/import/test/cleanup durations.

Official diagnostic command pattern (applied once to each of the 21 IDs below):

~~~powershell
& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_display_client_gate --test-case ReviewDisplayClientGateTest.<test_method>
~~~

| Test method | Seconds including setup/teardown/cleanup | Result |
| --- | ---: | --- |
| `test_corrupt_cache_malformed_done_is_fail_closed` | 26.706 | PASS |
| `test_corrupt_cache_malformed_entry_is_fail_closed` | 7.009 | PASS |
| `test_corrupt_cache_malformed_pending_is_fail_closed` | 9.902 | PASS |
| `test_corrupt_cache_missing_required_fields_is_fail_closed` | 7.066 | PASS |
| `test_corrupt_cache_unknown_status_is_fail_closed_before_expiry_or_eviction` | 7.775 | PASS |
| `test_duplicate_header_lines_including_identical_values_are_unsupported` | 1.941 | PASS |
| `test_history_list_detail_export_unsupported_gate_precedes_reads_adapter_and_all_effects` | 2.022 | PASS |
| `test_idempotency_fresh_key_executes_once` | 2.585 | PASS |
| `test_idempotency_payload_mismatch_preserves_conflict` | 3.764 | PASS |
| `test_idempotency_valid_done_replays_without_effects` | 4.638 | PASS |
| `test_idempotency_valid_expired_entry_keeps_ttl_behavior` | 6.658 | PASS |
| `test_idempotency_valid_pending_preserves_retry_conflict` | 1.205 | PASS |
| `test_malformed_and_comma_values_are_fixed_fail_closed_on_actual_http_route` | 4.674 | PASS |
| `test_missing_header_blocks_execute_before_lookup_charge_refund_provider_history` | 1.445 | PASS |
| `test_supported_header_preserves_history_authentication_storage_opt_in_and_ownership` | 1.186 | PASS |
| `test_supported_history_uses_whole_record_adapter_for_canonical_legacy_unsafe_without_db_writes` | 1.382 | PASS |
| `test_supported_http_execution_orders_gate_lookup_charge_model_and_replay_has_zero_effects` | 3.179 | PASS |
| `test_supported_old_cache_without_sealed_approval_never_returns_raw_or_reexecutes` | 2.481 | PASS |
| `test_unrelated_journal_routes_do_not_require_display_header` | 0.710 | PASS |
| `test_unsupported_clients_cannot_read_existing_replay_or_change_cache_wallet_history` | 4.138 | PASS |
| `test_wrong_version_blocks_execute_before_lookup_charge_refund_provider_history` | 1.199 | PASS |

All **21/21 PASS**, zero FAIL/ERROR/SKIP, inventory issues or unexpected guard
violations; restoration/patch restoration/owned-root cleanup true in every
child. Sum of independently measured testcase times: **101.664161 seconds**;
this is not a measurement of the full 21-case process, and repeated cold-start
wall time must not be substituted for a one-process suite duration.

The five `test_corrupt_cache_*` cases were additionally selected together via
five repeated `--test-case` arguments, still using the unchanged 120s budget.
**5/5 PASS**: tests 60.588852s, bootstrap 1.029170s, import 4.657350s,
isolation teardown 0.000807s; restoration/cleanup true, violations zero.
The slowest grouped case took 28.572298s. This confirms finite costly mutation
loops rather than a testcase hang or expensive final isolation teardown.

Baseline evidence: gate module, route fixture, API setup/guards and all existing
request production modules have no diff from committed HEAD. The only existing
display-contract test change adds pure-module names to an import-graph assertion;
it does not alter gate fixtures. New 3A modules have no existing request-path
import. The gate's baseline loops execute a fresh `asyncio.run` ASGI request for
each subcase, genuine synthetic SQLite authentication/audit writes and repeated
before/after `get_user_entitlements` (which persists the wallet). These costs
already exist at HEAD; no production performance defect or 3A regression was
established. Aggregate baseline work and execution-time variability are plausible
contributors, **not a proven explanation of the two earlier timeouts**. No
separate full baseline run, full-21 under-120 guarantee or profiler attribution
to a particular database syscall is claimed.

Minor: the existing body-corruption ID now constructs a canonical carrier with
a **recomputed public digest**, bypassing semantic encode validation, and calls
typed read admission. Missing v1/v2, mutated v1/v2 canonical text and invalid
compiler metadata are rejected with their precise contract codes. No production
code change or new test ID was needed.

Validation:
- Durable storage **28/28 PASS**, including direct recomputed-digest read rejection.
- Final H4 coordinator/results/runner **26/26 PASS** (15 + 8 + 3), covering exact
  subset identities, rejected selections before process launch, unchanged gate
  120s timeout and timeout-owned-root cleanup. The first synthetic selector
  self-test failed because its nested classes retained enclosing-class/module
  identity; fixed only those synthetic identities. Second run 15/15 PASS, and
  final expanded regression passed. This was not a production/gate failure.
- Official `--inventory-only`: 104 modules / 1004 direct / 18 probes,
  missing/duplicate/expected skips zero. `--node-inventory-only`: 23/248,
  missing/extra/duplicate/dependency issues zero; no metadata edit this step.
- `git diff --check` PASS. No full TestOnly, frontend/build, live service or
  provider/model invocation. Only runner, coordinator subcases, durable-test
  subcases and this plan changed relative to step start.
- Original feature retains HEAD 609163e9 and 9 modified / 10 untracked entries;
  main retains HEAD f779e252 and its existing Play README modification.
  No other worktree was modified.

### Implementation / Authority

[review_history_json_codec.py](../../../backend/core/review_history_json_codec.py)
owns strict UTF-8/JSON, canonical type-preserving bytes, lexical nesting preflight,
value-node/string checks, and outer versus SQL snapshot budgets.
[review_durable_storage_contract.py](../../../backend/core/review_durable_storage_contract.py)
owns the exact wrapper/payload/context/objective/auxiliary schema, versioned public
checksum domains, complete SQL snapshot checks and whole-paired admission.
No checksum is authenticity or cryptographic authorization; no HMAC or key config.

[review_durable_storage_approval.py](../../../backend/core/review_durable_storage_approval.py)
supplies LivePairedHistoryApproval, ApprovedDurableHistoryEnvelope and
DurableReadAdmission. Capture requires the private finalizer capability and
original issued bundle's source owner, original snapshot and prepared content.
The live-only full source-to-envelope check prevents an equal body/objective from
substituting another source's charts. Typed existing ApprovedHistoryWrite must
match the captured prepared record, complete metadata/access and actual binds.
Issuance rechecks originals after encoding and validates independently decoded
bytes before publishing a process-local receipt. No raw-dict write approval.

Read checks full paired structure/provenance/objective, exact actual row scalars
and four canonical snapshot digests. It reuses the existing pure history adapter's
whole-record safety walk; the caller must provide the current unsafe-text predicate.
Missing/nonboolean policy rejects; callback programming errors propagate rather
than becoming success/unavailable. Read creates no source DTO, live receipt, body
compilation, repair or legacy fallback. Its immutable byte-backed projections own
copies of admitted v1 body/A1, AI charts/cards B and independent SQL chart A.
Original approval/read objects cannot be copied/pickle-restored into write authority.

The new modules import only stdlib and existing pure contracts/compilers. No
existing request/finalizer/history/cache/frontend caller imports them. Existing
API, DB writer/reader, cache/idempotency, frontend, Android and environment have
no content diff. No activation flag is added; paired generation stays OFF.

### Verification / Actual outcomes

Official commands used from this worktree (approved executable, no PATH fallback):

~~~powershell
$py = 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe'
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_durable_storage
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_durable_storage tests.test_review_display_contract tests.test_review_legacy_compatibility tests.test_review_source_contract tests.test_review_envelope_contract tests.test_review_source_admission tests.test_review_history_adapter tests.test_review_history_prepared_content tests.test_review_history_approved_write tests.test_review_display_client_gate tests.test_full_test_entrypoint tests.test_storage_fixture_runner
& $py -I -X utf8 -B tests/run_isolated_tests.py tests.test_review_durable_storage tests.test_review_history_adapter tests.test_full_test_entrypoint
& $py -I -X utf8 -B tests/run_isolated_tests.py --inventory-only
& $py -I -X utf8 -B tests/run_isolated_tests.py --node-inventory-only
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend run lint
git diff --check
~~~

- Initial new entrypoint: 25/27 PASS, one failure and one error. Empty nested root
  object rejection is INVALID_KEYS, not DEPTH_LIMIT; maximum fixture imported
  core.ai_review_v2 before the official API module context. Corrected those two
  harness issues, without relaxing product/guard checks; second run 27/27 PASS.
- Full related focused command: 279/279 PASS (12 modules), after original-source/
  full-snapshot association hardening. Existing distinct regression is 252/252:
  display 33, legacy 14, source 32, envelope 26, source admission 23, history adapter
  44, prepared 18, approved write 24, client gate 21, coordinator 15, storage runner 2.
- Added mandatory read safety case and SELL-only nullable-objective subcase.
  Safety/adapter/coordinator checks passed. This added subcase wrongly assumed
  existing SELL-only realized_pnl=0; the actual backend calculator produces
  4230000.0 for its synthetic input. Corrected only the expectation to compare
  original backend value/type; no accounting behavior was changed. Final new
  module 28/28 PASS. History adapter 44/44 and updated coordinator 15/15 PASS.
  Final distinct focused coverage: 280 tests; repeated runs are not added again.
- Final FAIL/ERROR/SKIP and unexpected guard violations: 0. Restoration, patch
  restoration and cleanup true; no test-owned temp residue. Existing intentional
  negative isolation probes satisfied their expected contracts. No live network,
  provider/OpenAI, private credential or production database access.
- Actual isolated request/builders/chart producer/finalizer/prepared/write chain,
  with model/market mocks: both basic and advanced approve 200 input trades,
  140 AI candles, 20 markers and 20 cards, then preserve them through durable read.
  SQL producer A independently returns its valid unavailable chart, while AI B
  remains available. No durable DB insert. Samples fit the derived 1064696-byte/
  20898-node upper bound. This covers simultaneous producer collection maxima,
  not a claim that every schema/string maximum is jointly attainable.
- Canonical Unicode/int/float/null/-0.0/extreme finite float goldens, duplicate keys,
  nonfinite/surrogates, body/aux/context/snapshot corruption, A != B, approved empty
  and chart-only auxiliary, objective nullable-average/type identity, restart read
  without live receipts/compilers, raw-dict/read-to-write rejection and immutability
  pass. Exact payload 1310720 / outer 2622464 / nodes 32768 / depth 16 pass resource
  preflight; limit+1 rejects. Carrier boundary scaffolds are not production witnesses.
- Python inventory: 104 modules / 1004 direct, baseline 35/932/22 plus Stage 1 15;
  18 separate child probes. Missing/duplicate/expected skips 0. Registered exactly
  28 new IDs and the migrated module, with quantitative coordinator updates only.
- Node inventory remains 23/248; missing/duplicate/extra/source dependency issues 0.
  Node execution/allowlists/coordinator/guard and frontend fixtures are unchanged.
- Frontend lint and whitespace checks PASS. Full TestOnly, build/Android artifacts,
  package install, live API/model/device and actual history/cache integration were
  not run. Validation is isolated/static evidence, not rollout evidence.

### Remaining / Next Step

Return the 21 independent official PASS records and strengthened read-admission
negative evidence for independent review. The earlier two 120s full-module
timeouts have no reproduced specific hang/cleanup/3A defect; their exact
environmental trigger and full-21-under-120 completion remain unverified. Do not
repeat that whole command or enlarge the budget without a separately approved
next approach. Report and wait; no stage/commit/push.
Only after separate authorization may 3B connect typed paired history read/write
with owned synthetic/temp SQL tests; 3C cache and all generation/negotiation/activation
remain outside 3A. Existing protected worktrees are not modified.

## Slice 3 — Historical contract clarification

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
