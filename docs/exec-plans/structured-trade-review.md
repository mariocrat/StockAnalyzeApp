# Structured Trade Review — Stage A through Integration Regression Phase 5

## Phase 6 P1 Unicode NFD safety bypass: limited correction — 2026-10-10

Current authorization is this **Unicode canonical safety comparison fix only**.
Checkout feature/structured-trade-review, HEAD
787a9d5683803003fe2c7bfe1e786f5874847462; starting staged 0 / tracked
unstaged 37 / untracked 52, with 389 nonignored files captured by SHA-256.

Normalize prohibited regex patterns at their shared compilation boundary and
each comparison copy with the same NFC helper. Keep original source, structured,
body/display/compatibility, seal/history/cache bytes untouched. Preserve F1-F4,
all other canonical contracts, terminal/refund/storage/replay ordering and legacy
read behavior. Do not repair the two known full TestOnly failures or route child
timeout. No runner timeout override, full TestOnly/BuildChecks/browser rerun,
production data/configuration, external requests, Git mutation or other worktree
changes.

Add focused NFC/NFD/mixed/combining-sequence regressions, actual basic/advanced
builder and route rejection, refund/history/cache/replay identity, pre-fix unsafe
history withholding without stored-byte repair, and exact safe Unicode/strong display preservation. Run only
explicit safety/finalizer/route/refund/history/cache modules, coordinator/H4,
inventory-only and whitespace checks. All runtime effects use H4-owned synthetic
DB/cache/environment and mocked model/market boundaries.

- [x] Verify checkout, preserve baseline and inspect common safety comparisons.
- [x] Limit production normalization to regex compilation and comparison copies.
- [x] Add and register focused canonical Unicode safety and byte-identity regressions.
- [x] Run focused checks; preserve and report unrelated failures/timeouts.
- [x] Verify allowlisted changes and record results/status; report and wait.

Focused evidence: **229/229 PASS** across Unicode 12, safety 17, finalizer 18,
structured 79, refund 13, safety-finalization 2, strict writer 23, history adapter
44, cache 14 and history consent 7. NFC/NFD, mixed Hangul and canonical combining
sequences agree across all nine existing rule categories. The reported basic/
advanced counterexample is terminal safety_rejected; refund occurs once and
history connection/INSERT/DELETE/DDL are zero. The safe terminal result/cache/
replay contract is unchanged. Safe decomposed Hangul, accents, combining order,
emoji and strong runs preserve original source/display/seal/history/cache/replay
bytes. The safe filter returns the original str object; NFC does not fold the
tested compatibility characters. Pre-fix synthetic unsafe history is withheld by
the existing adapter safety hook, without changing its raw row, seal or cache.
Existing F1 cache identity admission is unchanged; no retrospective ready-cache
migration or added cache safety validator is in scope.

Coordinator/H4 **20/20 PASS** (entrypoint 15, storage runner 2, SQLite isolation
3). All passing focused children have unexpected effects 0, environment and patch
restoration true and owned-root cleanup true. History adapter retains its eight
expected blocked-write/SQLite-URI probes. Coordinator synthetic negative probes
retain their separate/null effect-counter contract. The sandboxed first Unicode
launch failed at Temp bootstrap with PermissionError before any test; the same
H4 command in the approved execution context uses owned synthetic Temp data and
completes cleanup. New fixture assumptions were aligned with the existing
approved chart and sealed strong-run shapes; production fallback/cache behavior
was not changed to satisfy them.

Python inventory-only **957 direct / 103 modules / 18 child probes**, baseline
942 (35 helper / 885 migrated / 22 OUT), added helper 15. Node inventory-only
**233 direct / 23 entrypoints**; missing/extra/duplicate dependencies are zero.
git diff --check passes, including the added test's no-index whitespace check.

The standard tests.test_review_route_compatibility child reports the existing
**120-second TimeoutExpired** (no completed child ledger, reported tests 0).
It is not counted as passed; root cleanup succeeds, restoration is unconfirmed.
No timeout override or retry, full TestOnly/BuildChecks/browser matrix or repair
of the two excluded full TestOnly failures was performed.

Change audit: 383 of 389 starting nonignored files are byte-identical; only six
existing allowlisted files and one new Unicode test change. Inverse audit restores
the exact starting SHA-256 for each of those six files, preserving all prior
hunks. Production changes are one import, NFC comparison/regex compilation
helpers, nine pattern construction calls and two comparison sites. No F1-F4
contract, main/writer/legacy implementation, frontend source or H4 runner changes.
Final staged 0 / tracked unstaged 37 / untracked 53; branch and HEAD unchanged.
No Git mutation or other worktree write.

## Phase 6 F4 history frontend title sinks: limited correction — 2026-10-09

Current authorization is **F4 P2 only**, in this worktree on
`feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`.
Starting staged 0 / tracked unstaged 37 / untracked 51. Preserve all existing
F1/F2/F3 changes, backend write contracts and legacy database behavior.

The history list and detail heading now pass the adapter's same record-level
display_snapshot to CanonicalReviewRenderer with the existing body surface.
Tabs pass the approved chart_tab document, or the legacy adapter's existing
chart display_snapshot/body document. Raw name/ticker/title reconstruction and
the three reported raw name sinks are removed. Chart selection does not change
the record title. Surface-specific tab labels retain the backend's exact text.

Regression inputs come from an actual H4 route/storage/adapter child: synthetic
double spaces, literal Markdown and decomposed Unicode/emoji names; canonical,
adapted and unavailable legacy records. The older handoff's injected single-
sentence stored bodies are incompatible with the current F3 ready-body contract.
Replace only those test inputs with normal producer plain/strong model outputs,
and align its invalid JSON expectation with the existing F2 bodyless result.
Production contracts, parsers, renderers and database schemas are unchanged.

Verification effects are limited to H4-owned temporary synthetic DB/cache/env,
mocked model/market/external boundaries and temporary browser DOM artifacts.
The supplemental browser harness renders the original archive JSX with the real
canonical renderer and CSS at desktop/mobile widths; chart canvas is omitted.
It requires existing local React/TypeScript/Playwright/browser runtimes, blocks
all page requests, and does not build or start the app/server.

- [x] Verify checkout/status and preserve unrelated work.
- [x] Connect the three history sinks to existing approved documents.
- [x] Add focused backend-output/production-JSX/browser regressions and refresh Node registrations.
- [x] Run focused frontend/browser, coordinator/H4, inventory and git diff --check.
- [x] Record DOM identity and F4 independent-review readiness.

Focused evidence: Node **89/89 PASS** across chart-source 43, canonical renderer
10, legacy cross-contract 11 and mobile UX 25. Python coordinator/H4 **20/20
PASS** across entrypoint 15, storage runner 2 and SQLite isolation 3; Node
coordinator **9/9 PASS**. Backend handoff and Node unexpected effects are 0;
environment/patch restoration and owned-root cleanup pass. Coordinator synthetic
negative probes retain their existing separate/null effect-counter contract.
The Node coordinator's source-inventory expectation changes only 230 to 233 for
the three added F4 direct cases.

Actual Edge browser **38/38 DOM cases, 148 documents PASS** at 1280 and 390px
(19 cases each). List/detail textContent and visible innerText match the same
adapter-approved canonical_text exactly. Each tab matches its own approved
chart_tab or legacy body document; changing the selected chart leaves the record
title unchanged. Double spaces, literal Markdown, decomposed Unicode and emoji
survive. Canonical/adapted/unavailable legacy output passes. Page requests and
JavaScript errors are 0; browser/context closure passes. New-record multi-tab
layout cases duplicate only a synthetic ticker to expose controls, retaining
the actual backend-approved document objects/values; they do not assert a new
production multi-chart storage contract. Chart canvas and full-app/device behavior
are outside this minimum DOM check.

Inventory-only PASS: Python **945 direct / 102 modules / 18 child probes**;
Node **233 direct / 23 entrypoints**; missing/extra/duplicate/source-dependency
issues 0. git diff --check and scoped untracked-file whitespace checks pass.
No full TestOnly/BuildChecks, production/external requests, migrations or Git
mutations were run. F1/F2/F3/backend production bytes and 382 of 388 starting
nonignored files remain identical. No other worktree was changed.

Evidence lives in the task-owned temporary directory
`stockboda-phase6-f4-0dda66847dda412991178984e5343175`: baseline hashes/status,
F4-only before/after diffs, H4 logs, actual generated browser fixtures and
history-title-browser-evidence/browser-report.json. Focused invocations use
the existing approved Python 3.12.14 and Node 24.15.0 with -I -X utf8 -B,
tests/run_isolated_tests.py and the four named Node entrypoints above, the three
named Python modules, --node-regressions, --inventory-only and
--node-inventory-only. For a fresh browser run, create owned tmp/home/config
directories under a new browser-fixtures root and invoke
tests.review_chart_handoff.prepare_chart_results(root, dict(os.environ)) from
an isolated parent interpreter with the repository on its explicit sys.path.
Then run frontend/scripts/review-history-title-browser-harness.mjs with the
evidence root, existing Playwright root and browser executable (see its usage).

Changed files: frontend/src/components/TradingJournal.jsx;
frontend/scripts/ai-review-chart-source.test.js;
frontend/scripts/review-history-title-browser-harness.mjs (new);
tests/review_chart_handoff.py; tests/test_full_test_entrypoint.py (one expectation);
tests/test_inventory.json (three cases and affected source hashes);
docs/exec-plans/structured-trade-review.md (this F4 prefix only).
Final staged 0 / tracked unstaged 37 / untracked 52; branch/HEAD unchanged.
**F4 is ready for independent revalidation; that review has not been performed.**

## Phase 6 F3 redesign Step 6: connect approved writes to production storage — 2026-10-09

Current authorization is **Step 6 only**. Preserve Step 2/3/4/5 contract modules,
finalizer capture, legacy adapter, F1/F2/F4 and client/canonical gate behavior.
Verified this checkout, `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 49; SHA-256 baseline covers 386 nonignored files.

Wire the production save helper to complete-record admission using its retained
PreparedHistoryContent and original seal. The writer accepts ApprovedHistoryWrite
only, validates it before _connect, and INSERTs its existing immutable bind tuple
without defaults, normalization, coercion or late JSON preparation. Keep schema,
ownership-scoped reads/deletes, history ID attachment and existing failure/refund/
retry/replay ordering. No migration/backfill or policy/configuration change.

Legacy rows needed for read/storage/account/client test fixtures move to an
explicit **test-only** fixture insertion helper; production writer cannot accept
those raw legacy kwargs. Test fixture call-site adaptations change no legacy
adapter or canonical/client gate policy. H4 remains mandatory before imports.

Scope/effects: production main save helper and history writer, focused DB-side-
effect/real-save/replay tests, legacy fixture helper/call-site adaptations,
four H4 registrations and this plan prefix. All execution uses H4-owned synthetic
DB/cache/environment and mocked external/model/market boundaries. No private or
production DB, external calls, full TestOnly/BuildChecks/browser/device matrix,
Git mutation or other-worktree writes.

- [x] Verify checkout/status, reconcile existing producer/write/legacy-fixture boundaries.
- [x] Connect strict admission and ApprovedHistoryWrite-only writer without changing other contracts.
- [x] Verify invalid connection/INSERT/DELETE/DDL=0, real producer saves/reads and identity/refund/retry/replay.
- [x] Run focused coordinator/H4, inventory/whitespace checks and verify preserved files/hunks.
- [x] Record evidence, Step 7 readiness and final status; report and wait.

The save helper rejects duplicate metadata JSON keys, validates complete metadata
and result before row assembly, and calls approve_history_write with the retained
PreparedHistoryContent/original snapshot. The route passes original finalizer
content to history admission before the existing API projection can fill a
missing chart or replace equal numeric values of another type. API projection,
cache admission, failure cleanup/refund and legacy read adapter remain unchanged.

The writer validates ApprovedHistoryWrite and reads its immutable bind tuple
before connecting. The existing INSERT/schema and owner-scoped read/delete
operations remain intact. Raw legacy kwargs now use tests/history_legacy_fixture.py
inside H4; no production code imports this fixture helper.

The expanded 23-case strict-writer module passes with zero unexpected H4 effects:
invalid access/metadata/result/key/type/nullability/value/identity/serialization/
bind mutations have history connection/INSERT/DELETE/DDL=0, including absent DB
files. Twenty actual session free/Pro/review and storable dev producer variants
save/read exact approved parameters. Complete available/unavailable general chart
outputs run the actual chart builder against synthetic market data. Source alias
mutation cannot change approved bytes or INSERT values. Basic/advanced ready and
missing-key immediate/history/replay identity and refund/retry/finalization cleanup
are covered.

Initial existing regressions exposed partial legacy chart shorthands, integer/date
metadata that bypassed JournalTradeIn, and a custom body unrelated to structured
content. Update only these test fixtures to real producer/DTO shapes; preserve
all Step 2-5 contracts. The byte-preservation check currently finds 369 unchanged
pre-existing files, 17 scoped existing-file edits and two new files, with no
removed files. The failed bulk fixture-edit approach stopped after two mismatches
(mixed EOL/import order); remaining edits used inspected small patches.

The route module exceeds the runner's default 120-second child limit once its
strict mutation matrix reaches the full producer. An invocation-only parent patch
sets 600 seconds for this explicitly selected child. It retains the actual H4
child, sanitized environment/protected paths, complete inventory validation,
restoration and cleanup ledger; the runner source is unchanged.

Final focused evidence: **247 direct cases / 14 modules PASS**, failures/errors/
skips/unexpected effects all 0, all module environment/patch restoration and
cleanup true. Counts: strict writer 23; producers 8; route compatibility 38;
consent 7; finalization cleanup 2; refund 13; history store 2; legacy read adapter
44; account store 8; data routes 3; structured producer/finalizer 79; coordinator
entrypoint 15; storage-boundary runner 2; SQLite isolation 3. The legacy adapter's
eight guard violations and coordinator child guard/negative probes are intentional;
their unexpected count remains zero. The final route run passes all 38 cases in
the unchanged H4 child with the invocation-only 600-second allowance.

Python inventory-only: 945 direct / 102 modules / 18 child probes, baseline 930,
classification 35/873/22, stage-1 added 15, missing/duplicates/skips=0. Node
inventory-only: 230 direct / 23 entrypoints, missing/extra/duplicates=0 and no
missing source dependencies. No Node/browser execution, full TestOnly/BuildChecks,
device, live service or production database validation was run.
Workspace git diff --check exits 0; both new files' no-index --check reports no
whitespace errors (exit 1 indicates additions relative to NUL). Only existing
Git LF/CRLF conversion warnings are emitted.

The Step 2-5 modules/tests, ai_review_v2 finalizer, legacy adapter, H4 runner/
isolation implementation and F1 cache test bytes match the starting SHA-256
baseline. Five legacy fixture call-site edits invert in memory to the exact
starting bytes. No other worktree or Git operation was mutated. Final staged 0 /
tracked unstaged 37 / untracked 51, including pre-existing work; branch/HEAD remain
feature/structured-trade-review / 787a9d5683803003fe2c7bfe1e786f5874847462.
Step 6 is complete and **Step 7 can proceed when separately requested**.

Step 6 changed-file allowlist (17 existing + 2 new):

- backend/main.py
- backend/core/review_history.py
- tests/history_legacy_fixture.py (new)
- tests/test_review_history_strict_writer.py (new)
- tests/review_source_fixtures.py
- tests/test_account_store.py
- tests/test_main_ai_review_history_consent.py
- tests/test_me_data_routes.py
- tests/test_review_history.py
- tests/test_review_history_adapter.py
- tests/test_review_display_client_gate.py (fixture insertion only)
- tests/test_review_route_compatibility.py
- tests/test_trade_review_refund.py
- tests/test_trade_review_structured.py
- tests/isolation_inventory.py
- tests/test_full_test_entrypoint.py
- tests/test_inventory.json
- tests/test_storage_fixture_runner.py
- docs/exec-plans/structured-trade-review.md (this Step 6 prefix only)

## Phase 6 F3 redesign Step 5: complete immutable write admission — 2026-10-09

Current authorization is **Step 5 only**. Preserve Step 2 access, Step 3 content
and Step 4 original-seal preparation modules/tests and finalizer capture.
Verified this checkout, `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 47; SHA-256 baseline covers 384 nonignored files.

Implement a pure complete-record admission factory and immutable
ApprovedHistoryWrite. The caller must provide every actual INSERT field,
including user_id and UTC created_at; no clock, defaults, ID allocation or
authentication occurs here. Validate five JSON snapshots and all row scalars,
reuse unchanged Step 2/3/4 strict contracts, bind to the retained original seal,
serialize and revalidate the record and exact fourteen SQL bind values before
issuance. The missing-key result model None and row model empty string are
explicit required producer values, not an admission conversion. General chart
metadata and AI chart projection remain independent approved contracts.

Scope/effects: new pure module/test, four H4 registrations and this plan prefix.
Tests use H4-owned synthetic stores and mocked providers to capture real
finalizers without invoking history saves. No main/save-helper/writer/DB
implementation connection, legacy adapter/F1/F2/F4 change, Git mutation,
other-worktree writes, full suite/build/device or external execution.
The object issuer is an in-process application boundary; private Python state
is not a security boundary against arbitrary code execution. User ownership
and storage consent remain the eventual authenticated caller's responsibility.

- [x] Verify checkout/status and trace complete producer/INSERT scalar/JSON shapes.
- [x] Implement strict complete-record serialization/bind admission and immutable approval.
- [x] Run focused record/serialization/immutability, coordinator/H4, inventory and whitespace checks.
- [x] Verify preserved files/hunks, record evidence and Step 6 readiness; report and wait.

Implementation: `backend/core/review_history_approved_write.py` provides
`approve_history_write`, `ApprovedHistoryWrite` and pure
`validate_approved_history_write`. A complete record has exactly fourteen
fields: the seven Step 3 metadata fields, ai_review, access_snapshot, user_id,
review_type, model, source and created_at. User ID is an opaque nonempty plain
string of at most 120 characters; no UUID conversion or ownership lookup is
invented. Created_at is the actual producer's UTC ISO seconds spelling
YYYY-MM-DDTHH:MM:SS+00:00 with a valid calendar/clock. It is caller-supplied;
the admission layer never consults a clock or substitutes a stand-in.

Exact Step 2/3 checks cover both independent access copies and the whole
metadata/result tree. Row source/type/model must agree with result, and access
copies must have identical values and exact types. Unchanged Step 4 matching
checks the retained prepared content against its own original snapshot object
and seal bytes. No new prepared content or seal is created. Body, compatibility
summary, full structured semantics and both distinct chart contracts retain
their exact approval association. Missing keys, legacy partial trees, unknown
fields, invalid types/nullability/numeric/date/variant relations fail closed.

Before issuance, admission independently freezes a typed source identity
(including float bits), serializes canonical UTF-8 JSON, decodes with duplicate
key rejection and validates the decoded record against the same original
approval. It separately prepares all five JSON snapshots and the actual
fourteen INSERT parameters in the existing column order. Decoding those exact
bind strings must reproduce the admitted complete record and original content.
Source values and approval identity are rechecked after serialization/bind
preparation. Scalar substitutions in otherwise valid serialized records are
also detected independently of the encoder. No normalize/default/coercion or
missing body/chart reconstruction is used.

Issued objects retain only immutable record/snapshot bytes, a tuple of plain
str/int/None SQL parameters, the prepared-content digest and a length-delimited
integrity digest/private issuer marker. They retain no input container,
PreparedHistoryContent or snapshot reference. Public construction, subclassing,
assignment/deletion, copy/pickle and restoration reject. The pure integrity
checker rejects uninitialized/forged types or altered bytes/binds/digests;
it neither recaptures content nor issues another approval. A future writer can
consume these prepared parameters; there is no production caller in this step.

Focused evidence (approved Python 3.12.14, `-I -X utf8 -B`, H4 synthetic auth/
storage/cache fixtures; external/model/market boundaries mocked):

- `tests/run_isolated_tests.py tests.test_review_history_approved_write
  tests.test_full_test_entrypoint tests.test_storage_fixture_runner
  tests.test_isolation_sqlite`: **24 + 15 + 2 + 3 = 44 direct PASS**, command
  exit 0, failures/errors/skips=0, inventory issues empty. New guarded tests
  violations/unexpected=0; all primary reports restored/patches_restored/
  cleanup=True. Coordinator-owned negative probes remain intentional.
- Real finalizer captures support all **20** session free/Pro, review and
  storage-capable dev-session x basic/advanced x ready/missing_key combinations.
  Additional actual targets absent/unmatched/outside the recent window, ID-less
  trades, name-only/empty general chart and strong/decomposed Unicode bodies
  pass. Review pro/free wallet and quota exceptions, Pro hidden rewarded counts
  and advanced fallback sources preserve Step 2 behavior.
- Every nested object's missing/extra key and wrong scalar/container types,
  bool/int confusion, row/result/access mismatch, naive/invalid expiry,
  shape-valid metadata/hidden-structured/model replacement, cloned/crossed
  seals, partial/duplicate/malformed/noncanonical JSON, encode failures, valid
  serialized scalar replacement, all five snapshot corruptions and bind
  type/order/value/UTF-8 corruption reject without issuing a write. Invalid
  records never reach object allocation. Input/seal mutation during admission
  rejects; after issuance original/nested/decoded aliases cannot change any
  retained bytes, SQL parameters or digest. No I/O, legacy/cache/normalization
  dependency, finalizer recapture or new seal runs in pure admission regressions.
- The initial run found three test expectations requiring correction: review
  fixtures must explicitly use plan pro, actual producer quota/wallet aliases
  must be detached to test a quota-only mismatch, and identity negatives must
  cross different prepared/seal objects rather than reject another correctly
  paired approval with identical content. No Step 2/3/4 rule was relaxed.
- Python `--inventory-only`: **922 direct / 101 modules / 18 child probes**,
  baseline_direct=907, classification=(35,850,22), Stage 1=15; missing/duplicate/
  expected skips=0. Node `--node-inventory-only`: **230 direct / 23 entrypoints**,
  missing/extra/duplicate=0, missing_source_dependencies empty. These are static
  inventory checks, not full-suite execution.
- `git diff --check`: exit 0. Both new files' no-index whitespace checks have
  no diagnostics (exit 1 is their expected difference from /dev/null).

Preservation: **379/384** starting nonignored files remain byte-identical,
including Step 2/3/4 modules/tests and finalizer, main/writer/legacy and F1/F2/F4.
Only four H4 registrations and this prefix changed among starting files; exactly
two new files, none missing. In-memory reversal of those five scoped edits
recovers each starting SHA-256, including older plan history and shared hunks.
Branch/HEAD unchanged; staged **0**, tracked unstaged **35**, untracked **49**
(47 + 2). No Git mutation or other-worktree write.

Step 6 readiness: **yes** for strict complete-record admission and immutable
SQL-ready approval. Main/save helper/writer/DB consumption remains unstarted.
The future connection must consume issued bytes/parameters without late JSON
serialization, normalization, defaulting, recapture or replacement seals.
Report Step 5 and wait.

## Phase 6 F3 redesign Step 4: immutable prepared content and original seal — 2026-10-09

Current authorization is **Step 4 only**: PreparedHistoryContent captures
approved finalizer content and verifies its identity against the existing
ApprovedReviewSnapshot. Keep Step 2/3 contract modules and their tests unchanged.
Verified this root, `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 45; SHA-256 baseline covers all 382 nonignored files.

Source boundary: the existing seal owns body/charts/status/source/review_type
and a partial objective, but has **no model, history metadata or full structured
tree**. Model/metadata/full semantics therefore bind to that original seal at
the trusted finalizer capture; their later replacement must fail immutable-byte
identity. Do not invent a model field or a new comparison seal. Finalizer
content excludes route-owned access; full pre-write matching still invokes the
unchanged Step 2/3 result validator with its real access object.

Scope/effects: a pure prepared-content module, minimal finalizer capture,
focused identity/mutation tests, their four H4 registrations and this prefix.
The finalizer emits its approved chart projection once before capture; the
prepared layer rejects absent body/projection and never reconstructs them.
No ApprovedHistoryWrite, main/writer connection, implementation DB/I/O,
legacy adapter/F1/F2/F4 change, Git mutation or other-worktree write. Tests use
H4-owned synthetic auth/storage/cache fixtures with external boundaries mocked;
no production/external execution, full suite, build or device checks.

- [x] Verify checkout/status, reconcile original seal and actual finalizer/route boundaries.
- [x] Implement immutable independent bytes and exact original-seal/content identity.
- [x] Run focused identity/mutations, coordinator/H4, inventory and whitespace checks.
- [x] Verify preserved files/hunks; record evidence, Step 5 readiness and final status.

Implementation: `backend/core/review_history_prepared_content.py` owns
`PreparedHistoryContent`, finalizer-authorized `prepare_history_content` and
pure `validate_prepared_history_content`. The class retains independent UTF-8
bytes for metadata, finalized result and the complete structured tree, an
independent copy of original seal bytes, the original snapshot reference and a
length-delimited integrity digest. It has no mutable-container accessor or
`__dict__`; assignment/deletion, public construction, subclassing, copy/pickle
and restoration reject. A private in-process finalizer issuer is required for
capture; ordinary callers cannot replace content by starting a new preparation.
This is an application boundary, not protection against arbitrary Python code
that can access private issuer state or rewrite all private slots.

Preparation checks the exact Step 3 content fields before route access exists,
without inserting a dummy access object or changing Step 2/3. It validates both
source values and independently serialized values, rechecks the finalizer model
and live input/seal identity, then retains bytes. Body document, exact strong
compatibility wire, full charts/cards, status/source/type and the existing sealed
objective fields compare as canonical JSON bytes: equal numeric value with a
different int/float type fails. No body/chart reconstruction, semantic/legacy
normalization, new seal or I/O occurs in this layer. Complete pre-write matching
invokes the unchanged Step 2/3 validator with actual access, then checks original
snapshot **object identity**, seal bytes and every retained content byte. A
fresh seal with identical bytes/digest is still a different approval.

Minimal `_finalize_ai_review` changes: emit its already sealed chart projection
before history content capture, retain `prepared_content` alongside the original
`snapshot` and `metadata_json`, clear capture on each attempt, publish only the
successful history variant. Empty/error/storage-off paths do not prepare.
The existing main/writer does **not** consume the new object. Model, full
semantics and general history metadata have no fields in the existing seal;
their exact approval association is captured in the finalizer, not falsely
claimed as an envelope field or inferred from partial objective/trade windows.

Focused evidence (approved Python 3.12.14, `-I -X utf8 -B`, H4 synthetic fixtures
with mocked providers; implementation has no DB/I/O or external execution):

- `tests/run_isolated_tests.py tests.test_review_history_prepared_content`:
  **18 direct PASS**. Real opt-in pre-write producers cover the same **20**
  session free/Pro, review and dev-session x basic/advanced x ready/missing_key
  variants with independent general and approved chart data. Finalizer hooks
  prove one original seal followed by one preparation before access, and that
  its exact retained object is published. Additional real ready bodies preserve
  strong spans and decomposed Unicode for both types.
- Shape-valid metadata/hidden-structured/model/status replacements, body/wire/
  chart replacement, equal int/float changes, equal-byte cloned and other seals,
  raw finalizer input/candidate/decoded alias mutations, missing/partial fields,
  invalid access expiry, uninitialized/forged objects, issuer bypass, private
  slot tampering, serialization corruption/model race and unsupported restore
  all reject. Mutable inputs never change retained bytes. No normalizer, legacy
  adapter/cache validator, seal constructor, file open, SQLite or environment
  dependency runs in the pure regression; blocked dependency tests pass.
- Final selected command also ran `tests.test_full_test_entrypoint`,
  `tests.test_storage_fixture_runner`, `tests.test_isolation_sqlite`:
  **18 + 15 + 2 + 3 = 38 direct PASS**, failures/errors/skips=0 and no inventory
  issues. Guarded identity tests violations/unexpected=0; all primary children
  restoration/patch restoration/cleanup=True. Owned negative probes remain
  intentional and checked by their coordinators.
- Python `--inventory-only`: **898 direct / 100 modules / 18 child probes**,
  baseline_direct=883, classification=(35,826,22), Stage 1=15;
  missing/duplicates/expected skips=0. Node `--node-inventory-only`: **230
  direct / 23 entrypoints**, missing/extra/duplicate=0 and no missing dependencies.
  Inventory is static evidence; full Python/Node suites were not run.
- `git diff --check`: exit 0. New module/test no-index whitespace checks produce
  no diagnostics (exit 1 denotes their expected difference from /dev/null).
  Existing LF-to-CRLF notices are not failures.

Preservation: only this prefix, finalizer capture and four inventory registrations
changed among starting files. All **376/382** other files are byte-identical,
including Step 1, both Step 2/3 modules/tests, main/writer/legacy and F1/F2/F4.
Exactly two new files, none missing. Reversing only these six scoped edits in
memory recovers each starting SHA-256, including earlier finalizer hunks and
older plan history. Branch/HEAD unchanged; staged **0**, tracked unstaged **35**,
untracked **47** (45 + 2). No Git mutation or other-worktree write.

Step 5 readiness: **yes** for the original-seal-bound immutable content layer.
ApprovedHistoryWrite and production main/writer consumption remain unstarted;
the next layer must consume the retained finalizer object rather than recapture
mutable caller content or create a replacement seal. Report Step 4 and wait.

## Phase 6 F3 redesign Step 3: new-write content contracts only — 2026-10-09

Current authorization is **Step 3 only**: metadata, structured_review and result
strict admission based on the confirmed Step 1 producer contract. Keep the
Step 2 access module and its tests unchanged. Earlier step records below are
historical. Verified this root, `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 43; SHA-256 baseline covers all 380 nonignored files.

Scope/effects: a separate pure content-contract module, focused producer and
mutation tests, their four H4 inventory registrations and this plan. Synthetic
H4 storage/cache/environment only, external model/market calls mocked or blocked.
No repair/default/coercion, semantic-normalization or legacy-adapter dependency.
No PreparedHistoryContent/ApprovedHistoryWrite, seal identity coupling,
main/writer connection, legacy adapter changes, F1/F2/F4, Git mutation,
other-worktree writes, full suite/build/device or production/external execution.

- [x] Verify checkout/status and reconcile actual metadata/chart/semantic/result producers.
- [x] Implement independent exact content schemas and value/variant relations.
- [x] Run focused producer/mutation and preserved access tests, coordinator/H4,
  inventory and `git diff --check`; verify starting files/hunks preserved.
- [x] Record evidence, Step 4 readiness and final status; report and wait.

Implementation: `backend/core/review_history_content_contract.py` exports
`validate_new_history_metadata`, `validate_new_history_structured_review` and
`validate_new_history_result`. Each returns None or raises the unchanged Step 2
`HistoryWriteContractError`; inputs are neither copied nor repaired. Independent
closed schemas check complete metadata, journal trade/chart/marker/tooltip/card,
objective/summary/basic/advanced semantics and pre-write result shapes. Bounded
plain JSON is checked before any rendering callback: exact class/key identity,
required nullable keys, safe integer counts/IDs and finite numbers. Schema,
date, enum, array/text limits and producer value/variant relations follow.

No semantic normalization or legacy adapter is reused. The existing **pure
display grammar and template** are used only after independent exact shape/type
admission, to verify canonical documents and ready-body rendering equality.
Summary must serialize the original body runs and owned separators, retaining
strong spans and Unicode. Missing-key has its own chart-rules body: the contract
checks its complete document and summary, rather than reconstructing it from
the partial metadata window. Step 4 will bind content to seal identity; no seal,
approval object, connection, writer, clock or environment is consulted here.
No production caller imports the new module.

Producer boundaries preserved: optional trade ID key versus required nullable
fill/card IDs; omitted/unmatched/out-of-window target; name-only empty ticker;
naive trade date/datetime versus offset-required access expiry; independently
built general metadata and AI-approved display charts; empty metadata chart
list and unavailable chart without period_label; daily/weekly/intraday 1m/3m;
buy versus sell fields and unmatched/zero-profit sell nullability. Result chart
numbers retain the Step 1 exact int|float union and nullable label/tooltip/card
metric leaves. Seal-based int/float/content identity remains Step 4 work.

Rejection matrix covers every nested object missing/extra key and each nested
field's wrong/subclass/null type, bool/int/float confusion, nonfinite/unsafe or
negative numbers, malformed calendar/clock/offset dates, enum/length/array
limits, incomplete legacy semantics and chart aliases. Relations cover
metadata/trade identity, objective count/date order, confidence label/level,
candle OHLC/timeframe/interval/source, marker buy/sell controls, fill count/
prices/quantity/average/profit, unmatched return-rate nullability, canonical
raw metadata documents, complete outbound paragraph surfaces, marker label/
tooltip side/count, chart header/timeframe, ready/missing-key origin/model,
review_type/access, placeholders, summary/body and ready semantic rendering.
Cyclic/custom/duck-typed values fail before callbacks; error paths exclude data.
The journal outcome map can leak `matched_cost` onto a buy fill when anonymous
IDs collide; it is an unknown producer field, rejected without changing source.

Validation (approved Python 3.12.14, `-I -X utf8 -B`, H4-owned synthetic stores,
mocked model/market boundaries; no external/production execution):

- `tests/run_isolated_tests.py tests.test_review_history_write_content`:
  **25 direct PASS** after final surface/nullable hardening. Actual captured
  pre-write producers cover **20 storage variants**, **20 journal chart
  variants**, **10 outbound journal/admission/envelope variants** including
  actual intraday/weekly times and empty projection, 16 ID/target/name/window
  cases, 8 partial-fill/multi-symbol/unsorted
  cases, 8 grouped/unmatched/zero-profit cases and both ready strong/Unicode
  bodies. Capture uses save=False/keyed=False; no new writer is exercised.
  Input preservation and blocked semantic/legacy/cache/I/O dependencies pass.
  Final focused content rerun after adding outbound variant coverage: **25
  PASS**, 66.385s; no additional direct IDs or inventory count changes.
- Same focused command also selected `tests.test_review_history_write_access`,
  `tests.test_full_test_entrypoint`, `tests.test_storage_fixture_runner` and
  `tests.test_isolation_sqlite`: **17 + 15 + 2 + 3 direct PASS**. Total **62**
  direct PASS; failures/errors/skips=0, inventory issues=[]; guarded content
  and access violations/unexpected=0. All primary children report restoration,
  patch restoration and cleanup=True. Coordinator-owned negative probes are
  intentional and checked by their owning tests.
- `--inventory-only`: **880 direct / 99 modules / 18 child probes**,
  baseline_direct=865, classification=(35,808,22), Stage 1=15;
  missing/duplicates/expected skips=0.
- `--node-inventory-only`: **230 direct / 23 entrypoints**,
  missing/extra/duplicate=0; no missing source dependencies. Node tests not run.
- `git diff --check`: exit 0; existing LF-to-CRLF notices are not failures.

Changed paths are the new content module/test, `tests/isolation_inventory.py`,
`tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`,
`tests/test_inventory.json` and this Step 3 plan prefix. All **375/380** starting
files outside those five existing edited paths are byte-identical, including
Step 1 contract, Step 2 access module/tests, main/writer/legacy/F1/F2/F4 source.
There are exactly two new files, none missing. Reversing only this step's five
edits **in memory** recovers each starting SHA-256: prior shared-file hunks and
older plan history are preserved. Final branch/HEAD unchanged; staged **0**,
tracked unstaged **35**, untracked **45** (43 + 2). No Git mutation or writes to
other worktrees.

Step 4 readiness: **yes** for the pure access/content contracts and focused
producer/mutation evidence. PreparedHistoryContent/ApprovedHistoryWrite,
seal identity coupling and main/writer integration are unstarted and require
the next step's scope. Stop after reporting this Step 3 result.

## Phase 6 F3 redesign Step 2: new-write access contract only — 2026-10-09

Current authorization is **Step 2 access only**, based on the completed
[producer contract](structured-trade-review-f3-producer-contract.md). Earlier
step authorization/results below are historical. Verified this root,
`feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 41. Starting hashes cover all 378 nonignored files.

Goal: add a pure new-history access validator for supported session free/Pro,
review and storage-capable dev sessions, basic/advanced and ready/missing_key.
Require exact keys/types, variant nullability and producer relations; reject
the Step 1 date exceptions without relying on legacy/cache validators.

Scope/effects: one unconnected access-contract module, focused access tests,
their H4 inventory registration and this plan. Tests may use H4-owned synthetic
SQLite/cache/environment and mocked external boundaries for producer evidence.
No metadata/structured/result contract, PreparedHistoryContent/ApprovedHistoryWrite,
writer/main connection, legacy adapter change, F1/F2/F4, Git mutation,
other-worktree writes or production/external/device execution.

- [x] Verify checkout/status and reconcile Step 1 with current producer source.
- [x] Implement pure access validation with no repair or I/O dependencies.
- [x] Run focused access mutation/producer variants, coordinator/H4, inventory
  and `git diff --check` only; verify preservation of existing work.
- [x] Record evidence and Step 3 readiness; report and wait.

Implementation: `backend/core/review_history_write_contract.py` exports
`validate_new_history_access(access, *, review_type, status)` and
`HistoryWriteContractError`. Its only imports are stdlib datetime/re. A closed
schema checks all object keys and exact scalar types by class identity before value checks;
nonnegative safe integers, quota/wallet equality, fixed products/policies,
source/plan/type, new-write flags, variant balances and validity follow.
Validation returns None or raises without repair, normalization or I/O.
No production caller imports it; status/type are scalar access coordinates,
not a result contract. Existing writers, legacy adapter and F1/F2/F4 are unchanged.

Supported exceptions: review quota above regular Pro 35/25 (including partial
expiry snapshots), `access.pro / wallet.free` after successful consumption,
review null resets and zero ads-needed, Pro hidden rewarded residual in daily
max, Pro advanced signup/weekly sources and separately timed dev Pro expiry.
Storage-capable dev is ordinary session access; standalone auth_mode=dev is
rejected. Consent/authentication stay at the existing route boundary.

Rejection coverage: every nested object missing/extra key; every scalar's
wrong/null/subclass type, bool/int/float confusion; negative/unsafe/nonfinite
counts; quota mismatch; source/plan/type/status and refund/replay flags;
policy/product/limit/balance relations; variant nullable violations; naive,
date-only, empty, malformed, impossible-calendar, invalid-clock/offset expiry;
internal reset format, calendar relationships and weekly-expiry equality.
Custom metaclass equality cannot substitute for an exact scalar type or run
callbacks during type checks; its mutation regression verifies early rejection.
Externally supplied expiry is preserved and neither compared with now nor
forced equal to the monthly reset. Cyclic/duck-typed inputs are rejected.

Validation (approved Python 3.12.14, `-I -X utf8 -B`, H4-owned synthetic stores
and mocked model/market boundaries; no production or external execution):

- `tests/run_isolated_tests.py tests.test_review_history_write_access`: **17
  direct PASS**, including actual pre-write producer **20 variants**, actual
  consumption **14 sources** in both statuses, review expiry race **4 variants**,
  and actual upstream invalid/naive expiry **28 rejected variants**. The writer
  capture uses save=False/keyed=False; this step does not exercise a new writer.
  Legacy/cache validators, clock, built-in file open, SQLite and environment reads are
  blocked during the pure-validator dependency regression. No input mutation.
  Final access rerun after exact class-identity hardening: **17 PASS** again;
  no extra direct test IDs or inventory registrations were introduced.
- `tests/run_isolated_tests.py tests.test_full_test_entrypoint
  tests.test_storage_fixture_runner tests.test_isolation_sqlite`: **15 + 2 + 3
  direct PASS**. Overall **37 direct PASS**, zero failures/errors/skips and no
  inventory issues. Guarded access child unexpected=0; all children report
  restoration, patch restoration and cleanup=True. Coordinator-owned negative
  probes are intentional and verified by their owning tests.
- `--inventory-only`: **855 direct / 98 modules / 18 child probes**,
  baseline_direct=840, classification=(35,783,22), Stage 1=15,
  missing/duplicates/expected skips=0.
- `--node-inventory-only`: **230 direct / 23 entrypoints**, missing/extra/
  duplicate=0 and no missing source dependencies. Node tests were not run.
- `git diff --check`: exit 0; Git's existing LF-to-CRLF notices are not failures.

Preservation: all **373/378** starting files outside the five authorized edited
paths are byte-identical; only two new files (contract and focused tests), none
missing. Reversing only Step 2's five edits in memory recovers each starting
SHA-256, proving existing shared-file hunks and prior plan history preserved.
Final branch/HEAD unchanged; staged **0**, tracked unstaged **35**, untracked
**43** (41 + 2). No Git mutation or writes to other worktrees.

Step 3 readiness: **yes for access**, based on the confirmed producer variants
and strict mutation/date evidence. Metadata/structured/result admission,
PreparedHistoryContent/ApprovedHistoryWrite and writer/main connection remain
unstarted and require the next step's explicit scope. Stop here and wait.

## Phase 6 F3 redesign Step 1: production producer characterization — 2026-10-09

Current authorization is **Step 1 only**. Earlier F3 completion statements
below are historical and do not approve the redesigned write contract.
Root/branch/HEAD were verified: this worktree, `feature/structured-trade-review`,
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 35 / untracked 39. Baseline hashes cover all 376 nonignored files.

Goal: fix the required keys, exact types, nullable/date conditions, relations,
supported variants and producer exceptions before implementing new history
write admission. Trace real session free/Pro, review and storage-capable dev
paths for basic/advanced and ready/missing_key.

Scope/effects: documentation and characterization tests/fixtures, their H4
inventory registration, synthetic H4-owned SQLite/cache/environment and mocked
model/market boundaries. Preserve all existing production files and other
worktrees. No `review_history_write_contract.py`, writer connection, legacy
adapter change, F1/F2/F4, Git mutation, production/external/device execution,
schema migration, full TestOnly or BuildChecks.

- [x] Verify checkout/status and read the actual access, date, auth, storage and
  review-result producers; distinguish producer output from legacy admission.
- [x] Record the complete variant contract and explicit rejection decisions.
- [x] Run focused H4 characterization and inventory/preservation checks.
- [x] Prepare the Step 1 report and Step 2 readiness decision; wait for authorization.

Contract/evidence: [F3 producer contract](structured-trade-review-f3-producer-contract.md).
Step 2 remains unimplemented and requires the next instruction.

### Step 1 result and evidence

The contract fixes five provenance variants, each with basic/advanced and
ready/missing_key: **20 actual storage combinations**. Dev login returns an
ordinary session; standalone dev bearer cannot authenticate for storage.
Review supports quota above ordinary Pro limits, null reset dates and
access.plan=pro / wallet.plan=free immediately after successful consumption
and expiry. Regular Pro retains hidden rewarded counts in free_daily_max;
Pro advanced may consume signup/weekly credits after its other balances.

Expiry producers preserve the original offset/Z text. Their upstream parsers
also accept naive/date-only values, while replay requires an explicit offset.
ACTIVE/GRACE subscriptions can even emit empty/unparseable expiry. These are
reachable producer exceptions to reject **before new storage in Step 2**;
Step 1 does not add that rejection or modify the F1 replay validator.

Focused **76/76 direct PASS across six modules** on 2026-10-09: new producer
characterization 8, review access 5, history store 2, legacy history adapter 44,
Python coordinator 15 and storage/H4 coordinator 2. The new module also covers
14 actual consumption branches, four review expiry races, calendar boundaries,
storage-off/dev bearer and unsaved/stale-target metadata. Guarded unexpected 0;
the adapter's declared negative URI probes and coordinator nested contracts
pass. Restoration, patch restoration and cleanup are true; direct failures,
errors, skips and inventory issues are 0.

Used the existing absolute `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`
3.12.14 with `-I -X utf8 -B`. The new module used the actual H4 `run_module`
and reviewed inventory with an evidence-only 600-second child timeout (17.221
seconds of tests); the other five modules used the unchanged explicit-module
`tests/run_isolated_tests.py` CLI. No repository runner timeout changed.
Python inventory-only PASS: **838 direct / 97 modules / 18 child probes**,
baseline 35/766/22 plus Stage 1 15. Node inventory-only PASS: **23 entrypoints /
230 direct**. This is source inventory, not full-suite execution.

Only five starting files changed: this plan, `tests/isolation_inventory.py`,
`tests/test_inventory.json`, `tests/test_full_test_entrypoint.py` and
`tests/test_storage_fixture_runner.py`. Added the linked contract document and
`tests/test_review_history_producers.py`. All other **371/376** starting files
are byte-identical, including every production file, F1/F2/F4 and the legacy
adapter. Reversing only the five scoped text edits in memory reproduces their
starting byte hashes, including mixed LF/CRLF, proving existing hunks preserved.
No starting file is missing. Whitespace and local documentation links pass.

Branch/HEAD unchanged; final staged **0** / tracked unstaged **35** / untracked
**41**. No Git mutation or other-worktree write. Full TestOnly/BuildChecks,
HTTP/device/external/production checks were not run. Step 1 is complete and
Step 2 has a concrete input contract; report and wait without implementing it.

## Phase 6 F3 strict new history admission continuation — 2026-10-09

Independent review found that the earlier F3 boundary still accepts missing
new access fields through legacy optional shapes, and permits a missing chart
projection that replay restores. The earlier F3 result below is historical;
it does not close these two findings. This continuation requires a separate
new-write contract while leaving the whole-record legacy adapter unchanged.

Verified this root/branch/HEAD: `feature/structured-trade-review`,
`787a9d5683803003fe2c7bfe1e786f5874847462`, staged 0 / tracked unstaged 35 /
untracked 39. Preserve existing work and other worktrees. Evidence directory
`stockboda-phase6-f3-strict-99567ac291f843ad9a449f5afc3261eb` contains hashes
for all 376 starting nonignored files and scoped copies.

- [x] Inspect production wallet/review-entitlement access producers and seals.
- [x] Reproduce missing access and canonical projection failures under H4.
- [x] Require the complete production access shape and exact sealed canonical
  projections before history connection/INSERT; no defaults or normalization.
- [x] Run only focused route/history/persistence, coordinator/H4, inventory and
  `git diff --check`; record preservation/results and wait.

Effects: scoped source/test/inventory/plan edits, owned temporary evidence and
H4-owned synthetic SQLite/cache/environment. Use the existing absolute Python
3.12.14 with `-I -X utf8 -B`, mocked providers and the evidence-only 600-second
child harness already verified in F3. No legacy read change, F1/F2/F4,
canonical/client gate change, migration/backfill, full TestOnly/BuildChecks/
browser matrix, external/device/production work or Git mutation.

### Strict continuation correction and final evidence

`admit_new_ai_review_history_candidate` is a new-write-only boundary. It
requires the complete access object emitted by `_wallet_snapshot` and
`_review_entitlement_snapshot`: both quota sections and both wallet sections,
all four products and their fields, settings/ad_policy/free_policy, validity
and all top-level access fields. Every object has exact required keys; nullable
validity leaves must still be present. The existing whole-record adapter keeps
its legacy optional contract and continues to validate field types/content.

New canonical records must carry their body, compatibility wire, structured
review, chart projection, production chart/context/card keys and access. The
original status/source/review_type, body, summary and entire chart projection
must match the sealed `ApprovedReviewSnapshot`. Canonical JSON comparison also
rejects numeric type differences such as an integer replaced by an equal float.
Persistence no longer calls the result normalizer: missing or mismatched
projections cannot be restored at this boundary. All checks finish before
`add_review_history` and its write connection; accepted values remain independent
copies of the original input. The finalizer's earlier metadata admission,
legacy adapter, canonical/client gates and F1/F2/F4 remain unchanged.

The pre-fix H4 route run completed 38 direct cases. Its five expected failure
observations came from the three new tests: missing access reached INSERT and
then DELETE (1/1, with two write connections) on both basic and advanced;
the complete-field probe reached INSERT; missing chart projection was accepted
on both routes. The 35 earlier route cases passed. Boundary unexpected 0 and
restoration/patch restoration/cleanup true; no test infrastructure failure.

Final focused **147/147 direct PASS across 11 modules**: actual routes 38,
history adapter 44, history store 2, history/consent 7, account export 3,
safety finalization 2, refund 13, finalizer compatibility 18, Python coordinator
15, storage/H4 coordinator 2 and SQLite/H4 coordinator 3. Final reports have
failures/errors/skips/inventory issues 0 and restoration/patch restoration/
cleanup true. Guarded unexpected 0; the adapter's eight declared negative URI
probes and coordinator nested contracts pass. Final reports are recorded in
`final-reports.json` in the evidence directory.

The new actual-route matrix covers 12 access omission paths and six canonical
projection omissions/mismatches, on both basic and advanced, with two attempts
per invalid key: **72 rejected requests**. Each request refunds exactly once;
history write connection/INSERT/DELETE 0, existing rows and history DB bytes
unchanged, and no done cache or pending key survives. Invalid same-key retries
cannot become replay successes. After removing the fault, each route group
admits a valid same-key retry; replay adds no charge/refund/model/provider/history
effects and preserves the new history's canonical identity. A separate probe
removes every field actually emitted in each basic/advanced production access
tree, including nullable fields and independent quota/wallet copies; all fail
before write without changing input or DB bytes.

Normal basic/advanced ready and missing-key storage, immediate/history/list/
export/replay canonical identity, existing error/refund/cleanup, and legacy
canonical/adapted/unavailable/no-backfill/DB-byte regressions pass. Python/Node
inventory-only PASS: **830 direct / 96 modules / 18 child probes**, baseline
35/758/22 plus Stage 1 15; Node **23 entrypoints / 230 direct**, with missing/
duplicate/extra/expected-skip/dependency issues 0. `git diff --check` passes.

Only seven starting files changed: `backend/core/ai_review_v2.py`,
`backend/main.py`, `tests/test_review_route_compatibility.py`,
`tests/test_inventory.json`, `tests/isolation_inventory.py`,
`tests/test_full_test_entrypoint.py` and this plan. All other 369/376 starting
nonignored files are byte-identical; no files added/missing. Full Git status,
branch and HEAD are unchanged: staged 0 / tracked unstaged 35 / untracked 39.
Other worktrees were not modified. Full TestOnly/BuildChecks/browser matrix,
external/device/production work, migration/backfill and Git mutation were not
performed. Report and wait for the continued F3 review.

## Phase 6 F3 history closed admission: limited correction — 2026-10-08

Scope: align pre-write history admission with the existing list/detail/export
whole-record adapter. Preserve legacy read behavior and existing refund/error
contracts; no migration/backfill, F1/F2, F4 frontend, canonical/client gate or
Git mutation. Root/branch/HEAD verified: this worktree,
`feature/structured-trade-review`, `787a9d5683803003fe2c7bfe1e786f5874847462`.
Starting status: staged 0 / tracked unstaged 35 / untracked 39. Preserve all
starting changes and other worktrees. Baseline hashes/copies for 376 nonignored
files are in `stockboda-phase6-f3-8d60d2d03c764d03b851afa2a6104e7e`.

- [x] Inspect finalizer metadata, persistence and whole-record read admission.
- [x] Reproduce unknown nested and missing/extra/wrong-type candidates under H4.
- [x] Reuse the read admission before history approval and before DB write.
- [x] Run focused history/route/persistence modules, coordinator/H4, inventory
  and `git diff --check`; record evidence and wait.

Effects: scoped source/test/inventory/plan writes and owned temporary evidence.
Use the existing absolute Python 3.12.14 with `-I -X utf8 -B`; explicit tests
run under H4 with synthetic SQLite/cache/environment and mocked providers.
Full TestOnly/BuildChecks/browser matrix and external/device/production work
remain unrun. This is a bounded admission fix with no schema or billing policy
change; the existing plan records progress and verification.

### F3 correction and final evidence

`admit_ai_review_history_candidate` assembles the whole persisted contract and
calls the unchanged `safe_legacy_history_snapshot` / `adapt_history_record`
boundary. Valid stand-ins cover only the storage-generated id/created_at and
are removed before persistence. Every caller-supplied field, including the
final access snapshot, uses the same closed shape/content/projection checks
as list/detail/export. Rejected/adapted candidates cannot be saved; new metadata
must also equal its read projection, so admission never repairs or prunes it.

The finalizer checks the candidate before publishing history approval and
returns the existing error/refund fallback for invalid metadata. Persistence
rechecks the exact frozen metadata plus the normalized response and final
access before calling `add_review_history`; it saves an independent copy of
the admitted input, never the read adapter's transformed output. A late failure
uses the existing exception/refund/pending-key cleanup path. Legacy reads,
storage schema, F1/F2, F4 frontend and canonical/client gates are unchanged.

Pre-fix actual basic/advanced routes both accepted the reported unknown nested
candle as ready and wrote history. Final focused **144/144 direct PASS across
11 modules**: history adapter 44, history store 2, history/consent 7, account
export 3, actual routes 35, safety finalization 2, refund 13, finalizer 18,
Python coordinator 15, storage/H4 coordinator 2 and SQLite/H4 coordinator 3.
All final reports have failures/errors/skips/inventory issues 0 and restoration,
patch restoration and cleanup true. Guarded unexpected violations are 0;
the adapter's eight declared negative URI-blocking probes and coordinator
nested contracts pass. `final-reports.json` contains the final unique reports.

The 38 invalid metadata route combinations (unknown nested candle plus 18
missing/extra/wrong-type candle/marker/fill/tooltip/card/metric cases, each on
basic and advanced) return error, refund exactly once and perform history write
0. Replays add no charge/refund/model/provider/history effects. Seven late
invalid whole-record cases (unknown/missing/type candle, target/recent trade,
access and semantic metadata) fail before history connection/INSERT/delete,
preserve existing synthetic rows and DB bytes, refund once and clear pending
idempotency state. Each same-key retry succeeds and replays without extra effects.
Normal basic/advanced ready and missing-key records preserve body, summary,
structured review, chart projection, trade metadata and access across storage,
list/detail/export/replay. Existing canonical/adapted/unavailable legacy and
read-only/no-backfill regressions all pass.

The first standard route run exceeded its 120-second child budget and produced
no testcase report. An evidence-only harness then kept the approved H4 runner,
guard and module inventory while increasing that child budget to 600 seconds;
no repository runner/environment policy changed. The two known processes left
by the first timed-out run were cleaned up by exact PID/start-time scope. The
initial coordinator run also caught one remaining 808 baseline expectation;
it was corrected to 812 and the 15-case coordinator rerun passed.

Inventory-only PASS: Python **827 direct / 96 modules / 18 child probes**,
baseline 35/755/22 plus Stage 1 15; Node **23 entrypoints / 230 direct**.
Missing/duplicate/extra/expected-skip/dependency issues 0. `git diff --check`
passes. Only these seven starting files changed in F3:
`backend/core/ai_review_v2.py`, `backend/main.py`,
`tests/test_review_route_compatibility.py`, `tests/test_inventory.json`,
`tests/isolation_inventory.py`, `tests/test_full_test_entrypoint.py` and this
plan. The other 369/376 starting nonignored files are byte-identical; no files
were added/missing. Branch/HEAD and full Git status remain unchanged: staged 0 /
tracked unstaged 35 / untracked 39. Other worktrees were not modified. No DB
migration/backfill, full TestOnly/BuildChecks/browser matrix, external/device/
production work or Git mutation was performed. Report and wait for F3 review.

## Phase 6 F2 decode failure continuation — 2026-10-08

Current F2 authorization supersedes the malformed-JSON fallback contract in
the earlier F2 evidence below. All JSON parsing/conversion failures must be
terminal at model decode admission; post-decode semantic fallback remains.
F1, F3/F4, billing/canonical/client gates and Git mutation remain excluded.

Verified root/branch/HEAD and status again: this structured-trade-review
worktree, `feature/structured-trade-review`,
`787a9d5683803003fe2c7bfe1e786f5874847462`, staged 0 / tracked unstaged 35 /
untracked 39. Evidence `stockboda-phase6-f2-decode-tmdj3hl2` holds hashes for
all 376 starting nonignored files and scoped copies. Preserve starting work
and other worktrees.

- [x] Inspect strict decoder, terminal return and semantic fallback boundaries.
- [x] Reproduce 4300/4301-digit, duplicate-order and nonduplicate cases under H4.
- [x] Wrap only JSON parsing/conversion failures in a terminal decode exception;
  preserve the duplicate subtype and post-decode semantic exception handling.
- [x] Run explicit focused decoder/route/refund/cache/finalizer modules,
  coordinator/H4, Python/Node inventory-only and `git diff --check`.
- [x] Record final results and preservation, then report and wait.

Effects: scoped source/test/inventory/plan writes and owned temporary evidence.
Tests use existing absolute Python 3.12.14, `-I -X utf8 -B`, explicit modules
and H4-owned synthetic SQLite/cache/environment. Digit-limit changes are local
to test children with cleanup restoration; no production limit change. No full
TestOnly/BuildChecks/browser matrix, external request/private DB, deployment,
Git mutation or other-worktree writes.

The pre-fix run demonstrated all ten 4301-digit actual-route combinations
returning fallback, including nonduplicate input. The 4300-digit unique objects
parsed normally, and all eight 4300-digit duplicate route cases were already
terminal. JSON syntax failure fixtures also showed the earlier fallback/seal
behavior. Reports had violations/unexpected 0 and restoration/patch restoration/
cleanup true. The initial semantic-error control rejected both the model and
the fallback producer; it now injects only the model admission failure so the
unchanged fallback is independently admitted.

Production now has `_StructuredModelDecodeError`; the duplicate-key exception
retains its identity as a subtype. Only the `json.loads()` call wraps TypeError,
ValueError (including JSONDecodeError), RecursionError and OverflowError, with
the original cause retained. The finalizer catches that type before its
unchanged generic semantic exception handler. Whitespace/fence-empty responses
reach the JSON parser instead of silently returning an absent candidate.
Actual missing-key/no-output handling remains outside decode, unchanged.

Two manual inventory patches failed on context/order matching and were stopped.
The four affected testcase lists were instead recomputed from AST declarations
without importing targets, preserving all other manifest data; four new IDs
and five renamed malformed/semantic IDs were reconciled. Counts now include
823 Python direct, baseline 35/751/22 plus Stage 1 15, with 18 child probes.
Existing semantic-fallback fixture inputs now use `{}` instead of malformed
JSON, and the raw-safety fixture is valid JSON containing the same forbidden
text. These changes preserve the intended semantic/safety assertions under
the newly requested terminal decode policy.

The first post-fix run passed structured 79, refund 13 and source admission 23;
cache 14 and coordinators 15+2 also passed. Two old route/finalizer assertions
still expected snapshots for syntax failures and were reconciled. The initial
deep-JSON fixture at depth 1200 actually parses in Python 3.12; it is a semantic
traversal failure, so no production behavior was broadened to make it terminal.
A pure JSON probe verified depth 10000 raises RecursionError, and that actual
parse-failure fixture now passes on both routes.

### F2 continuation final evidence

Final focused **195/195 direct PASS across 8 unique modules**: structured 79,
actual routes 31, purchased/basic refund 13, finalizer compatibility 18,
source admission/semantic fallback 23, cache 14, Python coordinator 15 and
storage/H4 coordinator 2. Final reports have failures/errors/skips/duplicate IDs/
inventory issues 0. All six guarded reports have violations/unexpected 0;
both coordinators pass their nested contracts. Restoration/patch restoration/
cleanup is true in all eight reports. The final reports combine the passing
unchanged modules from `focused-after.log`, the repaired route/finalizer reports
in `focused-routes-final.log`, `focused-cache.log` and `focused-coordinator.log`;
`final-reports.json` holds only the eight final unique reports.

The 20-case actual basic/advanced integer matrix passes: unique 4300-digit
integers parse and retain their existing schema-invalid semantic fallback;
4300-digit duplicates are terminal in all eight orders; 4301-digit inputs are
terminal in all ten orders, including both nonduplicate inputs. Duplicate pairs
precede/follow the number and the number occupies either duplicate value slot.
The prior 66 duplicate/Unicode/forbidden-order route combinations also pass.
Fourteen actual-route syntax/whitespace/fence/trailing-data/RecursionError cases
are terminal. These 98 terminal combinations observe model/charge/refund/history
1/1/1/0, original balances restored, semantic admission/fallback/seal 0, no
structured/display/chart body, history approval `None` and cache snapshot `None`.
Only the existing done terminal error is cached; replay adds no model, charge,
refund, history, provider, market or charts-once effects. A separate injected
post-decode semantic ValueError on each route preserves chart-rules fallback
and a sealed snapshot. Valid basic/advanced JSON, low-confidence/semantic/safety
fallbacks, missing-key and legacy fallback exact-content regressions pass.

Inventory-only passes: Python 823 direct / 96 modules / 18 child probes,
baseline 35/751/22 plus Stage 1 15; Node 23 entrypoints / 230 direct. Missing,
duplicate, extra, expected skip and source dependency issues are zero.
`git diff --check` and added-line whitespace checks pass. Only ten existing
files changed this turn: `backend/core/ai_review_v2.py`, this plan,
`tests/test_trade_review_structured.py`, `tests/test_review_route_compatibility.py`,
`tests/test_trade_review_refund.py`, `tests/test_review_finalizer_compatibility.py`,
`tests/test_review_source_admission.py`, `tests/test_inventory.json`,
`tests/isolation_inventory.py` and `tests/test_full_test_entrypoint.py`.
Other 366/376 starting nonignored files are byte-identical, missing/new files 0.
Full Git status, branch and HEAD are unchanged: staged 0 / tracked unstaged 35 /
untracked 39. F1/F3/F4, billing/canonical/client gates and other worktrees are
unchanged. Full TestOnly/BuildChecks/browser matrix and external/device/
production validation were not run. Report and wait for F2 re-review.

## Phase 6 F2 duplicate JSON keys: limited correction — 2026-10-08

Current authorization is F2/P2 only. The F1 scope and results below remain
historical; F3/F4, cache implementation, canonical/client gates and billing
policy are excluded. Phase 6 independent approval remains pending.

Verified worktree `D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`,
branch `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; staged 0 / tracked unstaged 35 /
untracked 39. Preserve all starting changes and all other worktrees.

Goal: reject duplicate JSON object keys at every depth after JSON key escape
decoding, without selecting either value. The common production model decoder
must terminate duplicates before fallback, semantic admission, sealing or
history approval. Existing error/refund/replay contracts remain in force.

- [x] Inspect the actual decoder/finalizer, route/refund/cache and H4 boundaries.
- [x] Add focused counterexamples and observe failure before the decoder fix.
- [x] Use one strict model decoder and a distinct terminal duplicate error.
- [x] Run focused basic/advanced, malformed/safety, refund/history/cache/sealed
  regressions, coordinator/H4, source inventory and `git diff --check`.
- [x] Record the scoped delta, preservation and results, then report and wait.

Effects: read source/Git state; write only scoped source/tests/inventory/this
plan and owned temporary evidence. Tests use the existing absolute Python
3.12.14 with `-I -X utf8 -B tests/run_isolated_tests.py` and explicit modules.
H4 owns synthetic SQLite/cache/environment and blocks external requests.
Evidence directory `stockboda-phase6-f2-cqay9lgf` records hashes for all 376
starting nonignored files and scoped source copies. Full TestOnly/BuildChecks/
browser matrix, live services/private DB, Git mutation and other-worktree
writes are excluded.

Before repair, the new decoder cases failed in all 9 subcases and the three
route cases failed in all 42 initial basic/advanced subcases. Existing cases
remained passing; both H4 reports had violations/unexpected 0 and restoration,
patch restoration and cleanup true. The strict decoder now uses a generic
`object_pairs_hook` after JSON key escape decoding. A distinct duplicate-key
exception reaches the finalizer's terminal bodyless error return. Decoding
precedes raw safety selection so plain forbidden text cannot select fallback.
No field allowlist, duplicate-detection regex or cache/billing change was added.
The first post-fix run passed all 77 structured tests and reached correct
bodyless/refunded/replayed results in all duplicate route cases, then exposed
a test-only cache assertion using `state` instead of production `status`.
That assertion is corrected; the expanded final route matrix also includes
the original plain-key/Unicode-value counterexample.

### F2 final verification

The single production decoder rejects every object through the same hook,
including nested objects and objects inside arrays. JSON-decoded key equality
also rejects escaped/plain keys and surrogate-pair/literal Unicode collisions.
The dedicated exception is caught before the finalizer's general malformed
handling; approval/history state stays `None`, with an empty bodyless terminal
`error` / `invalid_structured_output` result. Neither duplicate value is selected.
Existing malformed JSON and nonduplicate safety handling retains its fallback.

All 9 direct decoder counterexamples pass. Actual basic/advanced routes pass
**66 duplicate combinations**: 6 plain-key/all-depth, 12 escaped-first/second-key
and 48 forbidden-first/second-value combinations with plain/escaped values and
plain/escaped keys. Each route observes model/charge/refund/history **1/1/1/0**,
unchanged original entitlement balance, semantic admission/fallback/seal **0**,
no approved history or content snapshot, and no structured/display/chart body.
The unchanged cache retains only its normal done terminal error with snapshot
`None`; replay is identical apart from its replay flag and has model/charge/
refund/history/provider/market/charts-once **0**. Storage opt-in is enabled, and
the synthetic history rows remain identical before/after each failure.

Final focused result: **272/272 direct PASS across 15 unique modules**:
structured 77, actual routes 29, refund 13, cache 14, HTTP client gate/cache 21,
sealed envelope 26, finalizer compatibility 18, OpenAI client 16, transport 10,
AI safety 17, safety finalization 2, history consent 7, review access 5, Python
coordinator 15 and storage/H4 coordinator 2. Normal basic/advanced JSON, Unicode
escapes, malformed/schema-invalid output, safety and missing-key contracts pass.
Failures/errors/skips/duplicate IDs/inventory issues are zero. The 13 guarded
reports have violations/unexpected 0; both coordinators pass their nested
contracts. All 15 reports have restoration/patch restoration/cleanup true.

Commands use the verified absolute Python and
`-I -X utf8 -B tests/run_isolated_tests.py tests.<explicit module> ...`.
Evidence logs: `focused-before.log`, `focused-after.log` (the corrected test
assertion), `focused-f2-final.log`, `focused-regressions.log` and
`focused-coordinator.log`; `final-reports.json` retains the final unique reports.
Inventory-only passes: Python **819 direct / 96 modules / 18 child probes**,
baseline 35/747/22 plus Stage 1 15; Node **23 entrypoints / 230 direct**.
Missing/duplicate/extra/expected skip/source dependency issues are zero.
`git diff --check` passes; changed untracked source/plan have no trailing whitespace.

Only seven existing files changed in this turn: `backend/core/ai_review_v2.py`,
`tests/test_trade_review_structured.py`, `tests/test_review_route_compatibility.py`,
`tests/isolation_inventory.py`, `tests/test_inventory.json`,
`tests/test_full_test_entrypoint.py` and this plan. Five new direct regression
IDs account for all inventory/coordinator count changes. Other **369/376**
starting files are byte-identical, missing files zero. Branch/HEAD and full Git
status are unchanged: staged 0 / tracked unstaged 35 / untracked 39. No other
worktree was modified. P1 cache, F3 history persistence, F4 frontend sink and
canonical/client/billing policy remain unchanged. Full TestOnly/BuildChecks/
browser matrix and external/device/production validation were not run.

Next step: report and wait for the requested F2 re-review. This correction does
not establish independent approval or completion of the other Phase 6 findings.

## Phase 6 F1 residual cache bypasses: limited correction — 2026-10-08

The independent P1 recheck found cross-key prune/trim deletion of corrupt
entries and incomplete access admission. The earlier P1 results below are
historical and do not establish the stronger invariant requested here. Only F1
is authorized; F2 and all three P2 findings remain excluded. Phase 6 is HOLD.

Scope: verified `feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; staged 0 / tracked unstaged 35 /
untracked 38. Preserve unrelated files/hunks and all other worktrees. Production
changes concern cache admission/mutations only; no billing policy, canonical
contract, history persistence/admission or frontend change.

- [x] Reconcile actual status and inspect direct lookup, prune/trim/finish/abort,
  route serialization and both production access/wallet builders.
- [x] Add actual-route cross-key, nested access corruption and normal expiry/
  capacity regressions; demonstrate the two residual failures before repair.
- [x] Apply one strict entry validator before all entry reads and cache
  maintenance; validate all candidates before any prune/trim mutation.
- [x] Close the exact production access/wallet/quota/product/policy/validity
  structure and stored replay flag without changing entitlement policy.
- [x] Run focused cache/route/refund/sealed, Python coordinator/H4, inventory and
  whitespace checks; record preservation, then report and wait for re-review.

Effects: source/Git reads and scoped source/test/inventory/plan writes. The
existing absolute Python 3.12.14 executable is used read-only; H4 owns all
synthetic temporary storage/cache/environment and blocks external effects.
Evidence directory `stockboda-phase6-f1-e5080b6d8ab04712b2197a058070e2d1`
contains hashes for all 375 starting nonignored files and scoped source copies.
No full TestOnly/BuildChecks/browser matrix, live provider/private DB, deploy,
Git mutation or other-worktree writes. Independent approval remains pending.

### F1 final contract and call order

`_validate_ai_review_idempotency_entry` is the single full-entry validator.
`_validated_ai_review_idempotency_entries` completes validation of every cache
entry under the existing lock before exposing the list to any operational
lookup, expiry or capacity decision. Begin, prune, trim and finish share this
boundary; abort validates its target with the same entry validator before pop.

1. Begin validates the entire cache, then handles the requested valid live
   done/pending/mismatch. Replay changes only the approved owned response copy's
   flag to true after all stored entries have passed validation.
2. A fresh/valid-expired request validates its new pending candidate, then calls
   prune and trim. Each maintenance helper independently validates the complete
   cache before calculating expiry/overflow, sorting, or removing anything.
   Even trim's no-overflow return follows validation. An invalid later entry
   therefore cannot leave earlier valid expired entries partially deleted.
3. Finish validates all existing entries, requires its valid pending predecessor,
   and validates the complete candidate done entry before assignment/trim.
   No default access object or replay flag is manufactured during admission.
   Finish(None) and abort also reject corrupt existing targets before deletion.
4. If an in-flight failure encounters newly corrupted pending state, abort leaves
   it intact. Its validation exception is captured so the existing history
   cleanup/refund-on-exception behavior still runs. This is covered with an
   injected builder failure: charge/refund 1/1, history 0, original balance
   restored, pending write 1 and corrupt-entry delete/overwrite 0. It is distinct
   from preexisting-corruption cases, which are blocked before any charge.

Access shape comes from the unchanged production serializers in
`access_control._wallet_snapshot` (ordinary/dev/Pro accounts),
`_review_entitlement_snapshot` (review accounts), `_ad_policy`, `PRODUCTS`,
`verify_ai_review_access`, `refund_ai_review_access`, and the route access builder:

| Object | Exact required fields / types |
| --- | --- |
| access | auth_mode, plan, review_type, source: string; quota, wallet: exact dict; refunded, idempotent_replay: exact bool |
| quota | basic, advanced: exact balance dicts, equal to the corresponding wallet balances |
| basic balance | signup_remaining, free_daily_remaining, free_daily_max_remaining, free_available_now, rewarded_ad_available, rewarded_ad_daily_remaining, free_monthly_remaining, free_monthly_limit, pro_monthly_remaining, purchased_remaining: exact nonnegative int |
| advanced balance | signup_remaining, pro_monthly_remaining, weekly_reward_remaining, weekly_advanced_granted, weekly_ad_views, weekly_ad_views_needed, purchased_remaining, max_hold: exact nonnegative int |
| wallet | plan: string; basic, advanced, products, settings, validity: exact dict |
| products | Exact four logical IDs from production PRODUCTS; each has kind: string, quantity/price_krw: exact nonnegative int; kind matches its production product |
| settings | allow_advanced_ticket_for_basic: bool; ad_policy, free_policy: exact dict |
| ad_policy | basic_reviews_per_rewarded_ad, rewarded_basic_daily_max, ads_per_advanced_ticket: int; force_rewarded_ad_chain: bool; preferred_rewarded_ad_sequence: fixed single |
| free_policy | daily_basic, rewarded_basic_daily_max, monthly_basic_max, weekly_advanced_max: int |
| validity | timezone: fixed Asia/Seoul; daily_reset_at, weekly_reset_at, monthly_reset_at, weekly_reward_expires_at, pro_allowance_resets_at: mode-specific aware ISO timestamp string or None; signup_pass_expires_at and purchased_pass_expires_at: None |

Unknown/missing keys at every dict level, wrong exact types (including bool as
int), negative counts, unsupported auth/plan/review/source values, quota/wallet
divergence, malformed/naive timestamps, wrong fixed literals, incorrect refund
flag or stored replay flag other than literal False are rejected. Review mode's
null daily/weekly/monthly/reward deadlines and ordinary/Pro deadlines remain
valid. Policy amounts are validated as stored values; no current environment,
wallet DB, entitlement provider or external lookup runs during validation.
Billing consumption/refund policy and canonical admission code are unchanged.

### F1 evidence and preservation

The pre-fix new module exited 1 with 220 failed subtest assertions reproducing
both residual bypasses. Its one additional review-account fixture setup error
was a missing synthetic review configuration and was corrected without changing
production configuration. The first repaired F1/safety run passed 14/14 and
17/17. Final F1 cases break quota/wallet mutable aliases before independent
missing/extra/type mutations and record each corrupt HTTP request's counters.

| Actual ASGI corruption group | Requests | Model/provider/charge/refund/history/content/write/overwrite/delete |
| --- | ---: | --- |
| Corrupt A + fresh B, then A; both insertion orders | 4 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Expired corrupt A + fresh B, then A; valid expired entry first | 4 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Capacity overflow corrupt A + fresh B, then A; both insertion orders | 4 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Required access fields, minimal replay-only object, flags/values | 30 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Every nested required field missing | 88 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Extra field at every nested dict level | 16 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Every nested field with wrong type | 88 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Expired corrupt access, cross-key B followed by A | 10 | 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 |

All **244** new corrupt HTTP requests return only fixed 500 and preserve cache
keys/entry identity/value, wallet balance and history DB bytes. Direct prune/
trim cases also reject both state and access corruption with write/overwrite/
delete 0, including a valid expired entry preceding corruption. Direct finish,
finish(None) and abort corruption cases have the same zero mutation result.
The earlier 150-input basic/advanced HTTP matrix remains passing (21/21 module).

Positive controls pass: done replay with zero effects, pending 409 with
Retry-After 5, payload mismatch 409, and fresh keys with model/charge/history
1/1/1, refund 0, replay false, write/overwrite/delete 2/1/0. Normal expiry
prunes two valid old entries; normal capacity trims to one entry. Both have
write/overwrite/delete 2/1/2 and one normal model/charge/history execution.
Runtime event traces prove all existing entries validated before the first pop,
and every new/replacement candidate validated before its actual assignment.
Production Pro and review wallet builders round-trip through the real keyed
route/cache/replay; existing basic/advanced/refund/snapshot regressions pass.

Final focused result: **241/241 direct PASS across 13 unique modules**. This
includes new cache 14, HTTP gate/cache 21, route 26, refund 13, AI safety 17,
finalization 2, sealed envelope 26, finalizer compatibility 18, structured 75,
history consent 7, review access 5, Python coordinator 15 and storage/H4
coordinator 2. Fail/error/skip/duplicate IDs/inventory issues are zero; all
11 guarded reports have violations/unexpected 0. Both coordinators pass their
nested contracts; all 13 reports have restoration/patch restoration/cleanup true.

Commands use the verified absolute Python and
`-I -X utf8 -B tests/run_isolated_tests.py tests.<explicit module> ...`.
Evidence logs: `focused-f1-final.log`, `focused-regressions.log`,
`focused-coordinator.log`, and the unchanged-production safety report in
`focused-f1.log`. Parsed unique reports are `final-reports.json`; the eight
runtime zero-effect summaries are `f1-side-effects.json`; the production-only
delta against turn start is `production-f1.patch` in the evidence directory.
Inventory-only: Python **814 direct / 96 registered modules / 18 child probes**,
baseline 35/742/22 plus Stage 1 15; Node **23 / 230**. Missing/duplicate/extra/
expected skip/source dependency issues zero. `git diff --check` exits 0; scoped
untracked source/plan have no trailing whitespace.

Seven existing files changed: `backend/main.py`, `tests/test_ai_review_safety.py`
(two old invalid cache fixtures now use real production begin/route entries),
`tests/isolation_inventory.py`, `tests/test_inventory.json`,
`tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`,
and this plan. Added only `tests/test_ai_review_idempotency_cache.py`.
Other **368/375** starting files are byte-identical; missing files zero.
Branch/HEAD unchanged; staged 0 / tracked unstaged 35 / untracked 39 (one new
test module). No other worktree modified. F2/P2 findings and full
TestOnly/BuildChecks/browser matrix remain excluded.

Next step: independent F1/P1 revalidation of the single shared validator,
cross-key maintenance and full access-shape regressions. Ready for that review;
**Phase 6 remains HOLD** pending its independent result. Report and wait.

## Phase 6 P1 corrupted idempotency cache: limited correction — 2026-10-08

Goal: reject corrupt existing idempotency entries before model/provider, access
charge/refund, history writes or cache replacement. Phase 6 remains HOLD pending
independent revalidation. This authorization supersedes earlier repair stops
only for this P1; the three Phase 6 P2 findings remain out of scope.

Scope: verified `feature/structured-trade-review` at
`787a9d5683803003fe2c7bfe1e786f5874847462`, staged 0 / tracked unstaged 35 /
untracked 38. Preserve all existing work and other worktrees. Modify only the
production cache admission, actual-route regression coverage, necessary Python
inventory/count declarations and this execution record.

- [x] Verify checkout/status and inspect begin/finish/abort, expiry/eviction,
  sealed response admission and H4/ASGI test boundaries.
- [x] Reproduce the unknown-status fallthrough with actual production HTTP and
  add closed-state, zero-effect and normal-behavior regression cases.
- [x] Validate existing entries before expiry/eviction or replacement; retain
  valid replay/pending/fresh, mismatch and sealed-snapshot rejection contracts.
- [x] Run focused idempotency/route/refund, cache/sealed snapshot, Python
  coordinator/H4, source inventory and whitespace checks.
- [x] Record evidence and preservation; report independent P1 recheck readiness
  and wait for the user. No independent approval is claimed by this repair.

Effects: source/Git reads and scoped source/test/plan writes. Existing Python
3.12.14 at `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe` is used
read-only; H4 owns synthetic temporary DB/cache/env and blocks external effects.
The owned evidence directory is
`stockboda-phase6-p1-0b4010e19dd246b1903a5070c32588f8`; it contains hashes for
all 375 starting nonignored files and original scoped source copies.

Excluded: duplicate JSON keys, history metadata admission, history title/tab
frontend, billing policy, canonical contracts, full TestOnly/BuildChecks/browser
matrix, private/persistent DB, live providers, deployment, Git mutations and
other-worktree changes.

### P1 correction and evidence

Cause: begin previously pruned/trimmed before lookup, used cache truthiness, and
handled only `done`/`pending` explicitly. Any other status with a matching
fingerprint fell through to assignment of a new pending entry and execution.
Empty entries also fell through; eviction/expiry could remove evidence before
admission. The pre-fix actual-ASGI module run exited 1 with 95 failed subtest
assertions, including all five new corruption families. H4 restoration/cleanup
was true and unexpected violations were zero; this was the intended red run.

The new private cache admission contract is closed:

- The requested key's presence is checked under the existing lock before any
  prune/trim/write. A present value must be an exact dict.
- `pending` has exactly `status`, `payload_fingerprint`, `expires_at`; `done`
  has exactly those plus `result` and `snapshot`. Unknown/missing/extra fields
  or unknown/nonstring status fail closed.
- Fingerprints are exactly 64 lowercase hexadecimal characters; expiry is an
  exact UTC-aware datetime. Corrupt entries are rejected even if expired or
  the cache is over capacity.
- Done requires a result dict with status/source/review_type/summary/access,
  plain string summary, basic/advanced review type, access dict and stored
  `idempotent_replay is False`. The existing sealed body/wire/chart admission
  validates content; its existing bodyless terminal-error allowance remains.
  This does not add a second canonical contract or change billing policy.
- Valid unexpired done replays a validated owned copy; pending retains HTTP 409
  and `Retry-After: 5`; valid payload mismatch retains its existing HTTP 409.
  Valid expired entries retain the prior TTL/fresh-execution behavior.
- Invalid entries raise before route access/rate/capacity/producer/history work,
  return only the existing fixed HTTP 500 and preserve the same entry object,
  content and cache keys. There is no abort/refund/replacement on this path.

Actual production ASGI requests use the existing route and idempotency helpers,
synthetic opt-in history and real temporary wallet/history storage. Existing
provider/model mocks and direct operation spies count calls; an observed cache
dict counts actual assignments, replacements and removals. Each corrupt
request checks all counters and response content, entry identity/value, wallet
balance and history DB bytes, independently of its HTTP status.

| Corruption family (basic + advanced) | Requests | Model/provider/charge/refund/history/content/cache overwrite |
| --- | ---: | --- |
| Unknown status, including expiry/eviction pressure | 16 | 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Every required pending/done entry field missing | 16 | 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Malformed outer entries, including empty/falsy values | 14 | 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Malformed done/result/access/snapshot/common fields | 70 | 0 / 0 / 0 / 0 / 0 / 0 / 0 |
| Malformed pending/common fields or unexpected content | 34 | 0 / 0 / 0 / 0 / 0 / 0 / 0 |

All 150 corrupt requests also have cache assignment/removal counts zero.
Valid done (including capacity pressure) returns the same approved content with
replay true and zero extra effects; valid pending returns its unchanged retry
conflict. Basic/advanced fresh keys each have model/charge/history = 1/1/1,
refund 0, balance -1, replay false, pending then done writes = 2 and one normal
pending-to-done replacement. Done/pending mismatch and valid-expiry controls
pass. Existing missing/None/raw seal and changed-wire cases remain fail closed.

Focused H4 results: **227/227 direct PASS in 12 explicit modules**, no
failures/errors/skips/inventory issues. Ten guarded modules have violations and
unexpected both zero; both coordinators pass their nested contracts. All 12
reports have restoration, patch restoration and cleanup true.

| Explicit modules | Direct passed |
| --- | ---: |
| review_display_client_gate / review_route_compatibility / trade_review_refund / ai_review_safety / ai_review_safety_finalization | 21 / 26 / 13 / 17 / 2 |
| review_envelope_contract / review_finalizer_compatibility / trade_review_structured / main_ai_review_history_consent / review_access | 26 / 18 / 75 / 7 / 5 |
| full_test_entrypoint / storage_fixture_runner | 15 / 2 |

Each selection ran with the verified absolute Python executable and
`-I -X utf8 -B tests/run_isolated_tests.py tests.<module> ...`; full logs are
`focused-routes.log`, `focused-snapshots.log`, `focused-coordinator.log`, with
the parsed reports in `final-reports.json` under the evidence directory above.
Inventory-only: Python 800 direct / 95 registered modules / 18 child probes,
baseline 35/728/22 plus Stage 1 15; Node 23 entrypoints / 230 direct. Inventory
missing/duplicate/extra/expected skip/dependency issues are zero. The ten new
direct route tests account for the Python increase; subtests are not counted
as additional direct cases. `git diff --check` exits 0 and both scoped
untracked files have no trailing whitespace.

Changed relative to this turn's baseline: `backend/main.py`,
`tests/test_review_display_client_gate.py`, `tests/isolation_inventory.py`,
`tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`, and this plan.
The other **369/375** starting files are byte-identical; new/missing files zero.
Branch/HEAD and staged 0 / tracked unstaged 35 / untracked 38 remain unchanged.
No other worktree was modified. The three P2 findings, canonical/history
admission/frontend, billing policy and full TestOnly/BuildChecks/browser matrix
were not changed or rerun.

Next step: independent P1 revalidation of this scoped diff and the production
HTTP regressions. P1 is ready for that review; **Phase 6 remains HOLD** until
the user reports its independent result. Report and wait.

## Phase 5 P2 marker tooltip whitespace: limited CSS correction — 2026-10-06

User authorizes only tooltip legacy selector scope and focused regression.
Verified branch/HEAD and staged 0 / tracked unstaged 34 / untracked 38.
375 starting files captured. Existing renderer uses nested paragraph/run nodes;
legacy tooltip uses direct section children. Change only the three display:block
selectors to direct section children, preserving declarations and legacy markup.

- [x] Inspect CSS/renderer/legacy structure and capture source baseline.
- [x] Apply three CSS selector changes and scoped browser mode. Strengthen the
  existing tooltip Node testcase without removing its assertions: actual legacy
  branch output plus exact CSS scope. Strict inventory adds only the CSS read and
  test source hash; 23 entrypoints / 230 cases remain unchanged.
- [x] Focused Node 75/75, coordinator 9/9, lint and production build pass.
  Edge 1440px/390px: 10 checks PASS across unchanged real-route buy/sell tooltip,
  shared valid strong-vector CSS fixture and actual production legacy DOM branch.
  Canonical textContent/innerText, paragraph order/count and strong ranges match;
  hidden/clipping/extra blank lines 0. External requests/page errors 0, browser
  and server closed. No full browser matrix executed.
- [x] Full official TestOnly exit 0: Python 790/790, probes 18/18 and Node
  230/230 PASS; inventory issues/missing/duplicate/extra/skip 0. H4 unexpected 0,
  restoration/patch restoration/cleanup true.
- [x] Full official BuildChecks exit 0: backend compile, tracked secret scan,
  full lint (0 errors) and production build PASS.
- [x] Final preservation, lifecycle, inventory and diff check. Exactly five
  scoped files changed; other 370/375 starting files byte-identical, new files 0.
  Production CSS matches the starting file with only three selector substitutions.
  Python inventory 95 modules / 790 direct / 18 probes; Node 23 / 230.
  H4 unexpected and probe mismatch 0, restoration/patch restoration/cleanup true.
  Browser profiles and owned synthetic backend runtime cleaned. Git staged 0 /
  tracked unstaged 35 / untracked 38; branch/HEAD and other worktrees unchanged.

Both official gates PASS. The limited tooltip defect correction is complete;
the remaining full Phase 5 browser matrix can resume in a subsequent task.
No full matrix or Phase 6 was performed. Evidence root:
`stockboda-phase5-tooltip-8184e8c695eb4e4b9259ecf1fc97a8af`.

Production changes restricted to App.css selectors; no renderer/JS/backend/
canonical/history/cache/replay changes. H4 fixtures use owned synthetic storage;
Edge uses production dist, loopback API stubs, blocked external requests and
owned profiles. No installation, Git mutation, deployment, Phase 6 or full
browser matrix. Stop on any additional production defect.

## Phase 5 official gate blockers: limited correction — 2026-10-06

The user authorizes only the reported Node assertion pair, M2 placeholder line,
three test lint errors and history-handler refs lint. Branch/HEAD match the
requested values. Starting staged 0 / tracked unstaged 31 / untracked 38, with
375 starting file hashes and copies of scoped source captured.

- [x] Confirm current source/diff and exact causes; one refs approach only.
  Candidate `useCallback` declaration passes current ESLint with 0 errors;
  handler body and request-race logic remain unchanged.
- [x] Apply minimal corrections, production-execution assertions and exact H4
  dependency/inventory updates. Keep trial balance and admission assertions.
- [x] A: focused tests/lint, scanner positive controls and literal-value identity.
- [x] B: full official TestOnly: Python 790/790, probes 18/18 and Node 230/230;
  missing/extra/duplicate/skip 0, inventory issues 0, wrapper exit 0.
- [x] C: full official BuildChecks exit 0: backend compile, tracked secret scan,
  full lint and production build. Separate lint has 0 errors; separate
  production build exit 0. Final inventory/lifecycle/preservation/diff check pass.

### Limited correction results

- Node assertion 1 executes original basic/advanced `loadAiReview` and live
  production JSX/renderer: all follow-up refreshes fail while the same approved
  response/document and visible text survive.
- Node assertion 2 executes canonical production rendering with literal labels,
  Markdown-like text, strong ranges, paragraphs/newlines/spaces, and invalid
  documents. Text identity and fail-closed absence of raw/legacy/chart fallback
  pass. Both existing trial balance assertions are unchanged.
- M2 changes only the documented placeholder braces to angle brackets. Scanner
  code is byte-identical; all five synthetic secret families still trigger it.
- The quote escape edit produces the exact same fixture value. Only the two
  unused callback parameters are removed; admission assertions remain intact.
- Production change is limited to three `TradingJournal.jsx` lines: import
  `useCallback`, wrap the history handler and declare API/token dependencies.
  The handler body is identical. Existing 40 chart/history cases, including stale
  response races, pass using the actual React hook. No rendering contract changes.
- A: focused Node 99/99; focused Python 35/35; Node coordinator 9/9; changed-file
  lint and separate full lint exit 0. Eight malformed snapshot metadata controls
  still fail closed. React/TypeScript snapshots remain strictly pinned.
- B: Python 790/790 in 95 modules, probes 18/18, Node 230/230 in 23 entrypoints.
  Actual coverage equals inventory; missing/duplicate/extra/skip/issues are 0.
- H4: Python guarded violations 60, unexpected 0; probes 52 violations, six
  contract-matched negative raw attempts, mismatch 0. Node unexpected 0.
  Python/probe/Node restoration, patch restoration and cleanup are all true.
- Final preservation: exactly nine scoped files changed relative to turn start;
  other 366/375 files are byte-identical, no new nonignored files. Staged 0 /
  tracked unstaged 34 / untracked 38. Other worktree statuses are unchanged.

Both official gates now pass. Phase 5 browser matrix may resume in the next
authorized task; no browser execution or Phase 6 was performed in this task.

No backend/canonical/client gate/schema/adapter/scanner-rule change, global lint
suppression, browser run, Phase 6, install, live provider/private DB, deployment
or Git mutation. H4 owns synthetic storage and blocks external effects;
BuildChecks writes reviewed ignored bytecode/dist only, with loopback effective
API and disabled dev tools. The full browser matrix remains a subsequent task
even if both gates pass. Evidence root:
`stockboda-phase5-blockers-93a10278c5c04beb8ec49f4aeaadc5c2`.

## Phase 5 P2 limited Axios structured-detail correction — 2026-10-05

The user authorizes only the confirmed client-gate error-detail finding. Verified
branch/HEAD match the requested values; starting staged 0 / tracked unstaged 29 /
untracked 38, with all 375 starting non-ignored file hashes recorded. This narrow
authorization supersedes the no-production-repair rule for this finding only.

- [x] Inspect the installed common interceptor, four actual display consumers,
  existing focused tests, H4 inventory and previous browser reproduction.
- [x] Preserve structured detail losslessly; keep string decoration and malformed
  error fail-safe behavior; add interceptor and production-consumer regression.
- [x] Run focused H4 Node/Python gate regressions and Node coordinator; rebuild
  with existing dependencies and run only the gate-notice browser reproduction
  at 1440px and one mobile width. Do not resume the full Phase 5 matrix.
- [x] Record evidence, preservation, Git state and Phase 5 resume readiness;
  report and wait.

Scope: one common frontend interceptor plus directly related tests, Node
inventory/current inventory documentation, minimal browser selection/evidence and this plan. Backend gate/routes,
canonical/history/cache/replay, existing two Node source failures, M2 secret scan
and four lint failures are excluded. No Git mutation, other-worktree write,
provider/network/private DB access, dependency install or deployment.
Effects: H4 children use owned synthetic storage with blocked external requests;
local production rebuild writes ignored dist; browser uses a fresh owned profile
and intercepted synthetic loopback API. Evidence root:
`stockboda-phase5-p2-6236d1dbe0714780a56d586c5d331fbd`.

### Limited correction result: PASS; full Phase 5 remains pending

Cause: `main.jsx` installs the shared `installAxiosRequestIdMessages` interceptor.
Its retry/request-ID decoration converted object `detail` to a string before the
four `TradingJournal.jsx` error consumers called `reviewDisplayFailureMessage`.
The structured `unsupported_review_display_client` code was lost even without
support headers, so the fixed update notice was replaced by generic failure.

Only production change: `frontend/src/utils/apiErrorRequestId.js` rejects the
same error immediately when detail is a non-null object, preserving the exact
data/detail references, code, message, nested values and arrays without coercion
or mutation. String decoration is unchanged. The message-mutation branch now
accepts only object errors, so malformed primitive rejections remain fail-safe.
The backend gate, route order and four production UI consumers are byte unchanged.
The UI still chooses its existing fixed message:
`AI 복기를 표시하려면 앱을 업데이트해 주세요.`

Executed with existing Python 3.12.14 and Node 24.15.0, without installs:

- H4 focused Node **71/71 PASS**: interceptor 12, actual production consumers 40,
  canonical React renderer 10, idempotency 2, user-message 7. New declarations:
  six interceptor cases and one consumer case. Original cases/expectations remain.
- H4 focused Python **59/59 PASS**: actual ASGI client gate 11, production route
  compatibility 26, full-entrypoint coordinator 15, inventory documentation 7.
  Unsupported execution/history/export/replay gate contracts retain zero business
  side effects; supported execution/refund/replay/corrupt-cache assertions pass.
- Node coordinator **9/9 PASS**. Missing/extra/duplicate/skip/inventory issues 0
  for focused execution. Guarded unexpected 0; all restoration, patch restoration
  and cleanup true. Foundation coordinator counters are intentionally null.
- Production `npm run build` **PASS** using existing dependencies, loopback API
  and disabled dev tools. No Capacitor sync, external requests or deployment.
- Real Edge **154.0.4258.53**, built production App/main/TradingJournal/axios/CSS:
  `--client-gate-only` **10/10 PASS**, five response variants at **1440px** and
  **390px** (no support headers, request ID, retry, both, raw backend message).
  Fixed text matches DOM textContent and visible innerText; notice is visible
  within the viewport. Screenshots inspected. Raw backend message, request ID and
  retry decoration are absent. Browser findings/page errors/external requests 0;
  browser/context/server closed. Owned synthetic browser-fixture runtime removed.
  The full browser matrix was not resumed.
- Final inventory: Python **790 direct / 95 modules / 18 child probes**, Node
  **230 direct / 23 entrypoints**; missing/duplicate/extra/source dependency issues
  0. The exact count checks/current docs were updated for seven new Node cases;
  historical evidence counts were retained.
- `git diff --check` **PASS**. Existing excluded findings were rerun and remain
  identical: `test:journal-mobile-ux` **23 PASS / 2 FAIL**, M2 secret scan at
  `docs/release_preparation_checklist.md:205`, lint **4 errors** at the same
  existing locations. No added lint failure. Their source files are byte unchanged.

Changed files in this correction (10):
`frontend/src/utils/apiErrorRequestId.js`,
`frontend/scripts/api-error-request-id.test.js`,
`frontend/scripts/ai-review-chart-source.test.js`,
`frontend/scripts/review-display-browser-harness.mjs`,
`tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`,
`tests/test_quick_verify_docs.py`, `docs/TESTING.md`, `docs/quick_verify.md`,
`docs/exec-plans/structured-trade-review.md`.

Preservation: **365/375** starting non-ignored files byte unchanged; exactly the
ten authorized files changed, including one production source. Backend files and
excluded finding sources unchanged. No new non-ignored files. Main/broker worktree
statuses unchanged. Final Git staged **0** / tracked unstaged **31** / untracked
**38**, same branch and HEAD. No stage/commit/push/reset/revert/stash operation.

Evidence: owned temp root above contains `validation-summary.json`, raw focused
and coordinator logs, inventory logs, excluded-finding rerun logs, production
build log, browser report and ten PNGs under `browser-evidence/`, plus synthetic
fixture handoff and cleanup report. The P2 browser blocker is corrected and its
limited regression is PASS; Phase 5 integrated verification can resume. This does
not resolve the excluded findings or complete/approve Phase 5 or Phase 6. Report
this result and wait for the user before resuming.

## Phase 5 canonical display integration regression — 2026-10-05

The user reports independent approval of Phase 2D-4 and authorizes full
official TestOnly, full BuildChecks and real browser/DOM/CSS verification.
This supersedes earlier full-suite/browser HOLD and pending Phase 2D-4 approval
statements below. Actual worktree, branch and HEAD match the requested
`structured-trade-review`, `feature/structured-trade-review`,
`787a9d5683803003fe2c7bfe1e786f5874847462`. Starting staged 0 / tracked
unstaged 29 / untracked 36; all 373 non-ignored starting files have byte hashes.

Goal: integrate existing canonical display regression evidence across source
admission, immutable DTOs, finalization, whole-record legacy reads, route
billing/cache/replay, supported clients and actual production frontend rendering.
Only tests, inventory, documentation and a minimal browser harness may change.
Existing expected values and production behavior must remain unchanged.

- [x] Verify actual checkout, worktrees, baseline hashes, instructions, official
  entrypoints and existing isolation/dependency tooling.
- [x] Run full official TestOnly and reconcile Python/Node execution inventory,
  skips, missing/duplicate/extra cases and H4 lifecycle/violation evidence.
- [x] Run full official BuildChecks with existing dependencies only; record
  its secret-scan failure and supplemental lint/build results.
- [ ] Run the production frontend in an isolated real browser at desktop and
  mobile width; verify exact text/strong/paragraph/whitespace and CSS visibility
  for live basic/advanced/fallback, history, charts/tooltips and notices.
- [ ] Reconcile response/history/cache/replay/frontend snapshot identity,
  real-route billing/refund/zero replay effects and unchanged synthetic legacy
  DB bytes; report coverage for every requested prior finding family.
- [x] Record final preservation, Git status, limitations and whether Phase 6
  independent safety review can proceed; then wait for the user.

Effects: inventory/source/Git reads; scoped test/doc/harness writes; H4 test
children use owned temporary synthetic DB/cache/environment with blocked live
providers/network. BuildChecks writes backend bytecode and frontend dist and is
not the H4 boundary; dependency resolution and build lifecycle are inspected
before execution. Browser input is synthetic, with isolated browser storage and
network restricted to its local fixture server. No package installation,
private/persistent production DB, migration/backfill, production configuration,
deploy/Play, other-worktree write or Git mutation is authorized.

Stop rule: on a confirmed production defect, do not repair production code.
Report P1/P2/P3, exact reproduction, affected boundary and the next smallest
correction, and stop Phase 5. Tooling/test preparation errors are recorded as
such; after two failures of the same material approach, stop that approach.

Current evidence: Python 3.12.14 and Node 24.15.0 are verified at their existing
absolute executable paths. The worktree has no local frontend node_modules;
the main checkout has an existing dependency tree used read-only by H4.
Build/browser dependency preparation must preserve that tree. Evidence and
baseline hashes are in the owned temporary directory
`stockboda-phase5-13d1929c5957487e85e1840785dcd260`.

Phase 5 stopped on confirmed **P2**: the real production entrypoint installs
the common Axios error interceptor, which stringifies structured HTTP 426
`detail` and removes `unsupported_review_display_client` before the display
failure helper sees it. The actual Edge-rendered production bundle shows its
generic request error and never shows the required update notice. No production
repair was applied. Smallest next correction: preserve structured error detail
through the common interceptor, with real entrypoint/browser regression.

Full official TestOnly exited 2: Python 790/790 and all 18 probe contracts PASS;
Node 221/223 with two unchanged obsolete source assertions FAIL. Both source
inventories exactly match execution, with missing/duplicate/extra/skip and
unexpected violations 0. Python acknowledges 60 intentional negative-boundary
violations and probe contracts acknowledge 6 negative raw unexpected attempts;
contract mismatches 0, all Python/Node restoration/patch restoration/cleanup true.
Official BuildChecks exited 2 at the existing M2 documentation secret-scan
finding after successful compile. Supplemental lint has four errors; supplemental
production build passes after read-only copying the already installed matching
PDF dependency. No package download or installation command was used.

Real Edge 154.0.4258.53 completed 17 desktop DOM/CSS checks at 1440px before
the update-notice failure. Basic/advanced/strong/whitespace/fallback/replay and
snapshotless behavior, chart card/header, exact visible/logical text, strong
ranges, block order and absence of clipping were observed. Mobile 390px,
history detail/unavailable DOM and actual marker tooltip hover remain unrun
because of the required stop. Backend/Node history, billing, replay, cache,
adapter and synthetic legacy DB-byte regressions passed in the full suite.

Detailed evidence, reproduction, remaining scope, regression matrix and final
state: [Phase 5 results](structured-trade-review-phase5-results.md).
Phase 6 completion/approval review is **HOLD**. Independent review of this
finding can proceed; resumed Phase 5 needs separate authorization after the
finding is handled. Report to the user and wait.

## Phase 2D-4 review-display.v1 client compatibility gate — 2026-10-05

The user reports independent approval of Phase 2C and Phase 2D-1/2/3 and
authorizes only Phase 2D-4. This supersedes the historical Phase 2D-4 HOLD
entries below. Verified worktree is
`D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`, branch
`feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 26 / untracked 33. All 370 non-ignored starting file hashes are recorded.

Goal: only clients explicitly sending the single exact
`X-Review-Display-Contract: review-display.v1` value can execute/replay AI or read
AI history via list/detail/account export. This is a display compatibility
boundary, with existing authentication, consent, ownership and billing intact.

- [x] Confirm checkout/status, preserve existing work, inspect production
  request/route, sealed replay, whole-record adapter and H4 inventory contracts.
- [x] Add one frontend header helper only to the four AI display requests;
  add a shared backend gate before replay/access/providers/history reads.
- [x] Verify missing/wrong/malformed/duplicate headers, zero unsupported
  effects, supported execution/replay and canonical/legacy history admission
  on real production routes; retain snapshotless frontend unavailability.
- [x] Run focused Phase 2D-1/2/3, Phase 2C/2B, Python/Node coordinator,
  storage/docs/inventory and whitespace checks; record results and preservation.
- [x] Prepare independent-review handoff; report then wait. Independent approval of
  Phase 2D-4 is pending.

Command effects: source/Git/inventory reads; scoped source/test/doc writes;
focused H4 tests use owned temporary files, synthetic DB/cache/environment/
process boundaries and blocked external network. Python 3.12.14 and Node
24.15.0 executable versions are verified. In-process ASGI requests require no
server, socket connection or live service. No full TestOnly/BuildChecks,
browser/CSS/device final gate, live network/private DB, dependency install,
DB migration/backfill, production configuration/deployment/Play publication,
Git mutation or other-worktree writes are authorized.

Decisions: fixed unsupported-client/update-required error without reflecting
header/request values; duplicate headers fail closed even when both values
match. AI gate precedes idempotency lookup, access/quota charge, model/providers
and history write. History gate precedes reads and leaves the approved
whole-record adapter in place. Replay uses existing sealed canonical admission;
unsealed legacy/raw cache is never reconstructed. Renderer, chart/race guards,
source admission, finalizer/refund and identifiers remain unchanged.

### Implementation and production evidence

- Frontend `src/utils/reviewDisplayContract.js` owns the header name, version,
  request helper and fixed update notice. Only AI execute/history list/detail/
  account export use it. Authorization/idempotency are preserved, headers are
  copied, and ordinary journal/chart/review/data-summary requests do not declare
  AI display support. Structured unsupported-client errors cannot become raw
  message objects or reflect raw error/request/header values.
- Backend `core/review_display_client.py` uses the existing canonical
  `SCHEMA_VERSION`. Each of the four production routes calls it first. Exact
  single list value only; HTTP 426 with code `unsupported_review_display_client`
  and fixed `AI 복기를 표시하려면 앱을 업데이트해 주세요.` for every unsupported
  form. This adds no authentication, entitlement, user-agent or build-number rule.
- Actual execute function order: gate; batch limit/type normalization;
  fingerprint/idempotency lookup and replay return; rate/capacity; access/quota
  charge; consent/history candidate; basic/advanced provider/model generation;
  unchanged canonical finalization/refund/history save/cache completion.
  Basic/advanced ASGI traces observe `gate, lookup, charge, model`; retry appends
  only `gate, lookup`. Existing HTTP audit middleware still reads sessions and
  records failure/exception events. Required zero-effect claims cover replay,
  quota, model/provider and history operations, not those existing audit events.
- New actual-ASGI gate tests: missing/wrong/empty/spaced/case/parameter/comma/
  duplicate/mixed duplicate headers return exactly the same error. Fingerprint,
  idempotency begin, rate/capacity, charge/refund, model/market/context/chart,
  consent, history preparation/write and read/adapter calls are zero. Existing
  cache content is withheld; cache entry/key/result, wallet balances and history
  DB bytes are unchanged. Both review modes are covered.
- Supported normal execution charges once and saves once with opt-in; replay
  preserves content and adds zero model/provider/charge/refund/history effects.
  Existing `_normalize_ai_review_result` and sealed/A1 boundary remain intact.
  Reading missing cached approval now uses `get` so it reaches that boundary;
  missing/None/invalid approval or changed wire fails closed with the existing
  fixed 500 HTTP body, no replay content and no re-execution/refund. An older
  cache with valid sealed approval still replays normally. No legacy/raw adapter
  reconstruction is added.
- All three history reads still call `safe_legacy_history_snapshot` after gate
  and ownership/opt-in checks; list retains `history_list_projection`. Supported
  canonical/legacy/unsafe rows respectively remain canonical/adapted/unavailable.
  Nine whole-record adapter calls across list/three details/export are observed;
  history DB bytes/rows remain unchanged, with no model/billing/backfill/migration.
  Invalid session, other owner and storage-off remain 401/404/403 (list empty).
- Actual production frontend requests prove the exact header on all four
  surfaces. Original React/JSX loaders and export handler retain approved body,
  chart and strong identity. Snapshotless old-server live/history responses keep
  the fixed unavailable UI, legacy summary fallback zero and charts-once zero.
  The Phase 2D-3 renderer, Phase 2D-2 chart selector/race guards, Phase 2D-1 adapter
  and Phase 2C finalizer/compatibility and Phase 2B source admission modules
  keep starting bytes.

### Verification and inventory

Final selected evidence: Python **433/433 PASS** across **28** explicit modules
(gate 11, existing route 26, adapter 44, Phase 2C/2B and coordinator/storage/docs),
Node **69/69 PASS** across five entrypoints (production 39, cross-contract 11,
canonical 10, parser 7, idempotency 2), Node coordinator **9/9 PASS**. All **25**
guarded Python reports have unexpected zero. The three coordinator reports have
null counters and passing nested contracts. All final reports have restoration,
patch restoration and cleanup true; inventory issues/FAIL/ERROR/SKIP zero.
Source-only inventory: Python **790 direct / 95 modules / 18 child probes**,
baseline 35/718/22 plus Stage 1 15; Node **23 entrypoints / 223 direct**;
missing/duplicate/extra/skips/missing source dependencies zero. These are not
full-suite execution counts.

Commands used the verified absolute Python with `-I -X utf8 -B
tests/run_isolated_tests.py`. Explicit Python modules and Node selections:

```text
tests.test_review_display_client_gate tests.test_review_route_compatibility tests.test_review_history_adapter tests.test_review_history
tests.test_main_ai_review_history_consent tests.test_me_data_routes tests.test_journal_query_limits tests.test_journal_batch_limits tests.test_isolation_sqlite
tests.test_review_finalizer_compatibility tests.test_review_legacy_compatibility tests.test_trade_review_structured tests.test_trade_review_refund
tests.test_ai_review_openai_client tests.test_ai_review_safety tests.test_ai_review_safety_finalization
tests.test_review_source_contract tests.test_review_source_admission tests.test_review_market_source_admission tests.test_review_display_contract tests.test_review_envelope_contract
tests.test_ai_review_openai_transport tests.test_ai_review_chart_provider tests.test_ai_review_quality tests.test_review_access
tests.test_full_test_entrypoint tests.test_storage_fixture_runner tests.test_quick_verify_docs
--node-entrypoint test:ai-chart-source --node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-format --node-entrypoint test:ai-idempotency --node-executable "C:\Program Files\nodejs\node.exe"
--node-regressions --node-executable "C:\Program Files\nodejs\node.exe"
--inventory-only
--node-inventory-only
```

The initial gate import failed because httpx is absent; the final test uses
direct ASGI messages without installing dependencies. Handoff import before its
path setup, imported TestCase discovery, an overbroad audit-session spy, Node
AST self-binding collisions and two historical Python inventory literals were
test preparation/measurement issues. These approaches were corrected and the
affected checks rerun; production validation/admission was not weakened. A
manifest helper's ordering assertion and one partial-line documentation patch
were tool issues; neither failed attempt wrote its targets. Final evidence logs
and `verified-summary.json` are in task-owned temporary directory
`stockboda-phase2d4-9e255c7d-b486-440a-a421-48ed645d38fc`.

### Changed files and preservation

Exactly **22** existing scoped files change and **3** files are added. Other
**348/370** starting non-ignored files remain byte-identical; no file is removed.
The initial 26 tracked/33 untracked prior changes are preserved. Git remains
`feature/structured-trade-review` at the verified HEAD, staged **0** / tracked
unstaged **29** / untracked **36**. No other worktree or Git mutation.

- Production: `backend/main.py`, `backend/core/review_display_client.py` (new),
  `frontend/src/components/TradingJournal.jsx`,
  `frontend/src/utils/reviewDisplayContract.js` (new).
- Regression sources: `tests/test_review_display_client_gate.py` (new),
  `tests/test_review_route_compatibility.py`, `tests/test_review_history_adapter.py`,
  `tests/test_ai_review_safety.py`, `tests/test_ai_review_safety_finalization.py`,
  `tests/test_trade_review_refund.py`, `tests/test_main_ai_review_history_consent.py`,
  `tests/test_review_access.py`, `tests/test_me_data_routes.py`,
  `tests/test_journal_query_limits.py`, `tests/test_journal_batch_limits.py`,
  `tests/review_chart_handoff.py`, `frontend/scripts/ai-review-chart-source.test.js`.
- Inventory/coordinator: `tests/isolation_inventory.py`, `tests/test_inventory.json`,
  `tests/test_storage_fixture_runner.py`, `tests/test_full_test_entrypoint.py`,
  `tests/test_quick_verify_docs.py`.
- Docs: this plan, `docs/TESTING.md`, `docs/quick_verify.md`.

Next step: independent Phase 2D-4 review of this working diff. Report and wait.
Full TestOnly/BuildChecks, browser/CSS/device, live network/private DB,
deployment/Play publication and later work are out of scope and unverified.

## Phase 2D-3 canonical exact renderer production transition — 2026-10-05

The user reports independent approval of Phase 2C, 2D-1 and 2D-2 and
authorizes only Phase 2D-3. This supersedes historical 2D-3 HOLD entries below.
Client version/header gate and Phase 2D-4 remain HOLD. Verified worktree is
`D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`, branch
`feature/structured-trade-review`, HEAD
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 26 / untracked 32. All 369 non-ignored starting file hashes are recorded.

- [x] Inspect actual live/history/export, renderer/validator, chart source,
  request guards and H4 regression/coordinator contracts.
- [x] Connect the same canonical renderer to live/history body and approved
  chart document surfaces; remove production summary/parser rendering.
- [x] Keep exact text/strong/block/separator rendering and fixed unavailable
  UI; separate transport failure from backend content. Preserve chart identity,
  history race protection, whole-record admission and zero post-AI chart reload.
- [x] Execute original production React views/loaders against H4-generated
  route/storage/detail/export/replay outputs, plus exact/invalid/transition
  regressions and Phase 2D-1/2C/2B, coordinator/storage/docs checks.
- [x] Reconcile source inventories, inspect scoped changes and preservation,
  run whitespace checks, report independent-review readiness and wait.

Command effects: source/Git/inventory reads; scoped frontend/test/doc writes;
focused H4 tests use owned temporary files, synthetic DB/cache/env/process
boundaries and blocked external network. Existing Python 3.12.14 and Node
24.15.0 executables are verified. No full TestOnly/BuildChecks, browser/CSS/device
final gate, live network/private DB, install, DB migration/backfill, production
configuration, deployment, client support header/gate, Git mutation, other
worktree writes or Phase 2D-4. Backend compatibility summary stays on the wire;
historical parser compatibility checks retain the actual unchanged parser while
React output checks move to the existing canonical production renderer.

### Implementation and focused evidence

- Live JSX and `renderReviewHistoryArchive` pass the unchanged approved
  `display_snapshot` to the same `CanonicalReviewRenderer`. History body also
  requires whole-record `canonical`/`adapted` status. All production definitions,
  uses and imports of AiReviewSummary, ReviewInlineText, reviewDisplayText and
  aiReviewFormat are removed. Backend production and the existing compatibility
  parser retain their starting hashes; summary remains in the response/export.
- The renderer adds only an explicit `expectedSurface` argument and calls the
  existing, byte-unchanged validator function. Existing text/strong/block/
  separator rendering is unchanged. Header/tab/card documents use this component;
  DOM tooltip JSX mounts it through the React DOM root with synchronous layout
  measurement and root cleanup. Canvas markers receive the same canonical string.
  The whole-record adapter's older `display_snapshot` chart/card/tooltip documents
  retain their approved `body` surface; new projection documents retain their
  explicit chart surfaces. No document is recompiled, relabeled or normalized.
- `aiReviewChartSource` additionally validates body before returning any chart
  or card. Valid projection identity and the old adapter branch remain unchanged;
  missing/corrupt body returns the same empty source. History request counter,
  immediate state clearing and latest-only success/error/finally stay intact.
  Transport failure has a frontend-only `request_error` state and fixed notice,
  without synthesizing a summary. History transport failure also has fixed text.
  Contentless success responses use the same fixed frontend failure path;
  original live/history loader tests cover null and missing response bodies.
- The existing production Node/React entrypoint grows from 24 to **34** cases.
  Its original AST live JSX, loaders, history archive, account export handler and
  chart effect execute against six actual H4 synthetic backend results: normal
  basic/advanced plus plain/strong compiler-boundary fixtures in both modes.
  Immediate, raw saved, admitted saved, detail, export, cache and replay body
  documents agree. Each view receives its record's original document object;
  exact React logical text, HTML, block order and strong ranges agree across
  live/history/replay. The actual JSON export handler preserves the same snapshot.
- Strong evidence: `strong("체결 기록") + text("을 확인합니다.")` renders
  `<strong>체결 기록</strong>을 확인합니다.`, visible text
  `체결 기록을 확인합니다.`, Unicode-codepoint strong range **[0,5)**.
  Plain Markdown-like text remains literal; the mid-word AST retains only `수`
  at [5,6), with no legacy-parser conversion. Existing A1 P1 counterexamples and
  all 65 forbidden wires still reject before frontend execution; the 10 admitted
  compatibility wires still pass the unchanged legacy parser contract.
- **16** missing/corrupt-body combinations with a normal legacy summary render
  only the fixed unavailable body, no legacy summary, strong, chart or card.
  Version, empty/malformed blocks/runs, unknown fields, mismatch and wrong surface
  are covered. Full whitespace/newline/Unicode/HTML-like text and explicit label/
  numbering fixtures remain exact. The existing **66** invalid-chart combinations
  and source/race regressions remain green. History A→B, invalid→valid,
  valid→invalid and stale response/failure/finally yield no previous body/card.
  Even an injected valid body cannot bypass unavailable whole-record status.
- Approved card/header/tab/DOM tooltip strong nodes and exact strings survive
  the same renderer; legacy body-surface documents do too. Tooltip root unmount,
  DOM removal and chart cleanup are observed. This is actual React server output
  plus external DOM-root/chart API observers, not browser/CSS/device evidence.
- AI completion/replay issue **0** charts-once requests. Each actual backend
  replay adds **0** model/provider/market/charts-once/charge/refund/history-write
  effects and has the same renderer input/output. Ordinary pre-AI chart loading
  remains separate, and a late general response cannot replace approved charts.
- Focused Python **409/409 PASS** in **26** modules, including route 26, adapter
  44, Phase 2C/2B, refund/access/history and coordinator/storage/docs. All 23
  guarded reports have unexpected 0; the 3 coordinator reports have null counters
  and passing nested contracts. Every report has restoration/patch restoration/
  cleanup true, inventory issues 0 and FAIL/ERROR/SKIP 0. Final selected Node
  **62/62 PASS** (production chart/body 34, cross-contract 11, canonical 10,
  unchanged parser 7); Node coordinator **9/9 PASS**. Primary Node unexpected 0,
  restoration/patch restoration/cleanup true and missing/extra/duplicate 0.
- Inventory-only source checks: Python **779 direct / 94 modules / 18 child
  probes**, baseline 35/707/22 plus Stage 1 15; Node **23 entrypoints / 218 direct**.
  Missing/duplicate/extra/skips/missing dependencies are 0. Only the three related
  Node entries change; production chart tests no longer copy/import the parser.
  Canonical/legacy entries share a DOM evidence reader, not a cloned renderer.
- First selected Node run was 61/62: legacy tooltip used the adapter's `body`
  surface, not the new `marker_tooltip` surface. Explicit existing/new contract
  selection fixes that without rewriting documents; final rerun is 62/62.
  Inventory-helper import, partial-line patch and log-consumer errors were tool
  setup issues, not product failures. A diagnostic Git command disabling CRLF
  conversion produced artificial CRLF whitespace reports; abandon that override
  and preserve files. Ordinary Git diff whitespace checks pass.
- Preservation: exactly **15** existing scoped files change and one test-only
  DOM evidence helper is added. Other **354/369** starting files remain
  byte-identical; no files are removed. Every backend production file, Phase
  2D-1/2C/2B contract/adapter/finalizer source, existing parser, package manifest,
  Python execution coordinator and module-isolation boundary keep starting bytes.
  Git remains `feature/structured-trade-review` at the verified HEAD, staged 0 /
  tracked unstaged 26 / untracked **33**. No other worktree or Git mutation.

### Phase 2D-3 files and stop

- Production frontend: `frontend/src/components/TradingJournal.jsx`,
  `frontend/src/components/JournalTradeChart.jsx`,
  `frontend/src/components/CanonicalReviewRenderer.js`,
  `frontend/src/utils/aiReviewChartSource.js`.
- Tests/inventory: the chart/canonical/legacy Node entrypoints,
  `frontend/scripts/review-render-evidence.js` (new),
  `tests/review_chart_handoff.py`, `tests/isolation_inventory.py`,
  `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`,
  `tests/test_quick_verify_docs.py`.
- Docs: this plan, `docs/TESTING.md`, `docs/quick_verify.md`.

Executed the same 26-module explicit Python selection listed in Phase 2D-2,
the four related `--node-entrypoint` selections, `--node-regressions`, both
inventory-only modes and Git diff/added-file whitespace checks. Reports are in
the task-owned temporary `stockboda-phase2d3-3406b928-c129-4a03-871a-aba0a2e27e72`
directory; persistent results are summarized here. Full TestOnly/BuildChecks,
HTTP/live provider/private DB, browser/CSS/device final gate, migrations,
deployments and forbidden Git operations were not run. Phase 2D-3 is ready for
independent review, not independently approved here. Client version/header gate
and Phase 2D-4 remain HOLD. Report and wait.

## Phase 2D-2 P2 limited corrections — 2026-10-05

Only the independently reported history-detail race and invalid chart-display
snapshot admission are authorized. Phase 2D-3 remains HOLD. Verified branch/HEAD
remain `feature/structured-trade-review` /
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0 / tracked
unstaged 26 / untracked 32. All 369 starting non-ignored file hashes are recorded.

- [x] Guard history-detail success, failure and finally by the latest request;
  clear the previous detail/chart selection immediately on each request.
- [x] Reuse the existing frontend canonical display validator for every
  approved chart/header/tab/marker/tooltip/card document; reject the whole chart
  projection on any contract failure and retain the whole-record history adapter.
- [x] Execute original production functions/JSX in Node/React with controlled
  response ordering and corrupt-document matrices; preserve identity and zero
  chart reload/replay side effects. Run focused Phase 2D-1/2C/2B and
  coordinator/storage/docs checks, actual inventories and whitespace checks.
- [x] Inspect only this correction's changes and preservation, report evidence
  and Git state, then wait for independent re-review.

Command effects: source/status/inventory reads; scoped frontend/test/doc writes;
H4 tests use owned temporary files, synthetic DB/cache/env/process boundaries
with external network blocked. No full TestOnly/BuildChecks, browser/device/live
network/private DB, DB migration, Git mutation or other worktree changes.
CanonicalReviewRenderer rendering stays disconnected; summary rendering and
the existing general pre-AI chart loader stay unchanged.

### Correction and focused evidence

- `TradingJournal.openReviewHistoryDetail` uses a persistent request counter.
  Start clears the old detail, ticker and error immediately. Success/failure
  ignore a stale counter, and finally only clears loading for the latest counter.
  Original production-function regressions observed every state setter: A→B,
  B success→A success retains B without any stale state updates; A success→B
  failure never admits A and ends with no detail/chart/card; A failure→B success
  keeps B loading/error intact and ends at B. Rapid A/B/C selections clear old
  surfaces immediately, and stale failure after latest success changes no state.
- `aiReviewChartSource` imports the existing named `validateReviewDisplay` from
  `frontend/src/components/CanonicalReviewRenderer.js`. The same validator now
  accepts an explicit supported expected surface; default validation/rendering
  still permits only body. Version, exact keys, block/run types and bounds,
  character/separator limits and canonical-text equality are unchanged. All
  header/tab/marker-label/nullable-tooltip/card documents pass this full contract
  before chart/card JSX. Any failure returns the one empty source, including
  history with separate valid metadata charts. No abbreviated validator or
  representation regeneration was introduced; valid projection identity stays
  unchanged and the whole-record adapter branch remains intact.
- The actual Node/React chart entrypoint passes **24/24**. Its document matrix
  covers v99 at all five positions plus the exact reported empty-block card
  (6), malformed block/run (35), canonical mismatch (5), unknown document/block/
  run field (15) and wrong surface (5): **66 corrupt combinations** with zero
  immediate/history chart or card renders. Valid controls, invalid→valid
  recovery and valid→invalid clearing also pass. Existing actual marker/tooltip/
  card text and whitespace remain exact; the whitespace fixture now keeps its
  AST and canonical text consistent instead of fabricating an invalid document.
- Selected Node entries: chart 24 + A1 cross-contract 11 + canonical renderer
  10 + format 7 = **52/52 PASS**. Node coordinator **9/9 PASS**, including
  changed production contract hash rejection before execution. H4 copies
  and hashes the actual validator dependency, with no renderer production switch.
  Immediate/storage/detail/cache/replay identity and metadata independence,
  zero post-AI charts-once, unsafe/error fallback 0, and replay extra model/
  provider/market/charts-once/charge/refund/history 0 remain green.
- Focused Python **409/409 PASS** in 26 explicit modules: route 26, adapter 44,
  Phase 2C/2B and coordinator/storage/docs included. No Python cases were added;
  only Node dependency/case/hash inventory and corresponding coordinator/docs
  assertions changed. Every primary report passed with inventory issues 0,
  guarded unexpected 0 and restoration/patch restoration/cleanup true;
  FAIL/ERROR/SKIP 0. Actual source inventory: Python **779 direct / 94 modules /
  18 child probes**, baseline 35/707/22 plus Stage 1 15; Node **23 entrypoints /
  208 direct**, missing/duplicate/extra/missing dependencies 0. These are source
  inventory counts, not full-suite execution claims.
- Only 12 existing files changed in this correction: production frontend
  `TradingJournal.jsx`, `CanonicalReviewRenderer.js`, `aiReviewChartSource.js`;
  chart/canonical Node tests; `tests/isolation_inventory.py`,
  `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`,
  `tests/test_quick_verify_docs.py`; this plan, TESTING and quick_verify docs.
  No backend production/test file changed. Other 357/369 starting files are
  byte-identical, with no added/removed non-ignored files. Git diff --check and
  the untracked scoped whitespace scan pass. Branch/HEAD and staged 0 / tracked
  unstaged 26 / untracked 32 remain. No Git mutation or other worktree writes.
  Ready for independent Phase 2D-2 P2 re-review; Phase 2D-3 remains HOLD.

## Phase 2D-2 live AI review chart source unification — 2026-10-04

Phase 2C and Phase 2D-1 (including P2) are independently approved per the user.
Only Phase 2D-2 is authorized. Verified checkout is this worktree, branch
`feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`;
starting staged 0 / tracked unstaged 24 / untracked 29. All 366 starting
non-ignored file hashes are recorded before edits; preserve earlier changes.

- [x] Trace the actual production response/state/context/HTTP/chart path.
- [x] Publish the chart-only projection of the immutable approved envelope;
  retain exact documents and data through response, storage, detail and replay.
- [x] Remove the post-AI chart reload. Read AI chart/cards only from
  that projection; render snapshot marker/tooltip/header/tab text directly.
  Keep general pre-AI chart loading and all existing summary renderers.
- [x] Extend the same whole-record history adapter for the closed projection;
  keep unsafe legacy/canonical/trade/tooltip rejection and no failed fallback.
- [x] Run synthetic production-route/backend and real frontend Node/React
  regressions, including deliberately different general charts, replay effects,
  Phase 2D-1/2C/2B and coordinator/storage/docs checks plus actual inventories.
- [x] Inspect scoped changes, preservation, Git state and whitespace; report
  independent-review readiness, then wait. No Phase 2D-3 or later work.

Command effects: source/status/inventory reads; scoped source/test/doc writes;
H4 focused checks with owned temporary DB/cache/env/process effects and network
blocked. No full TestOnly/BuildChecks, browser/device/live network/private DB,
DB migration/backfill, production configuration, Git mutation or other worktree
changes. CanonicalReviewRenderer stays disconnected; AiReviewSummary,
ReviewInlineText and aiReviewFormat remain, with the existing summary structure.

Production finding: `loadAiReview` awaited `loadReviewContextForTrades`, which
POSTed both review-once and charts-once, then rendered `chartReview` through
JournalTradeChart. History used independent metadata charts. JournalTradeChart
rebuilt tooltip text from numbers. General loadChartReview and explicit history
trade restoration are separate pre-AI chart paths and remain available.

### Implementation and focused evidence

- `main._normalize_ai_review_result` binds `chart_display_snapshot` to a JSON
  copy of `charts`/`chart_cards` in the same immutable seal used for body/A1 wire.
  A supplied different projection is rejected; error responses have empty or
  absent chart content. No model, provider, raw trade/context or chart producer
  runs in this projection. Response, saved `ai_review`, detail/export, cache and
  replay retain exactly these chart objects/documents. Independent old metadata
  charts remain checked by the whole-record adapter and are not the new AI UI
  source. Access, history ID and replay flag stay outside the projection.
- The projection validator reuses the unchanged envelope chart schemas. The
  existing history adapter admits the new optional closed field, scans it along
  with every old field and preserves its documents without recompilation. New
  unsafe/unknown/corrupt chart/header/tab/card/marker/tooltip cases, error/bodyless
  records and valid-new-chart/unsafe-old-chart/trade/body counterexamples all
  return unavailable. Existing P2 semantic admission remains byte-identical.
- Production frontend selects response/history chart sources through one small
  pure selector. Header/tab/card/marker/tooltip canonical text is read directly;
  no reviewDisplayText/aiReviewFormat or numeric tooltip reconstruction enters
  the approved chart branch. JournalTradeChart's general branch remains. Safe
  legacy history uses only whole-record-admitted existing documents; failed or
  missing live snapshots and unavailable history never use general chart state.
  A failed detail fetch clears the previous detail to prevent a stale chart.
- Exact source-region comparisons confirm unchanged AiReviewSummary,
  ReviewInlineText/reviewDisplayText, general loadChartReview, explicit history
  trade restoration, AI route billing/refund/history orchestration and history
  preparation/save. Whole Phase 2B source/DTO/admission/market code, Phase 2C
  finalizer/body/compatibility compilers, aiReviewFormat and isolated
  CanonicalReviewRenderer files retain their starting hashes.

Final focused evidence uses verified Python 3.12.14 and Node 24.15.0, with H4
synthetic databases/cache/environment and blocked network:

- Python **409/409 PASS**, **26** selected modules: production route **26**,
  history adapter **44**, other history/query/export/SQLite **20**, Phase 2C
  finalizer **18**, legacy compatibility **14**, structured **75**, refund **13**,
  OpenAI client **16**, safety **17**, safety finalization **2**, Phase 2B source
  **81** (32/23/26), display **14**, envelope **26**, transport **10**, provider
  **1**, quality **3**, access **5**, Python coordinator **15**, storage runner
  **2**, docs **7**. Nested coordinator evidence is not added to direct counts.
- Node selected **40/40 PASS**: new production chart path **13**, existing
  cross-contract **11**, canonical renderer **9**, format **7**. Separate Node
  coordinator **9/9 PASS**. The new entrypoint requires actual basic/advanced
  route/storage/detail/replay/error/legacy outputs from an H4 backend child;
  original production AST loaders/views and JournalTradeChart are executed,
  with React server render and external DOM/chart API observers.
- Deliberately different general/history-metadata charts and a general request
  finishing after AI cannot replace the snapshot. Actual immediate/saved/detail/
  export/cache/replay chart objects and canonical strings agree. Metadata-only
  additions leave content and rendered chart surface equal. AI completion and
  replay issue **0** charts-once calls. Replay deltas for model/provider/market/
  charts-once/charge/refund/history are all **0**. Safety/invalid/compatibility
  errors and unavailable legacy chart/tooltip/trade/canonical records expose
  **0** fallback chart/cards; failed history restoration makes **0** requests.
- Guarded primary unexpected **0**, restoration/patch restoration/cleanup true;
  final FAIL/ERROR/SKIP/inventory issues **0**. Three Python coordinator reports
  have no top-level unexpected counter; their nested positive/expected-negative
  contracts pass. Node backend handoff has unexpected **0** and restored/patch
  restored true. The first Node attempt stopped before test launch because its
  generated handoff parent directory did not exist; create that owned temporary
  directory only. One docs regression retained the old 22/183 expectation;
  update it to actual source counts and rerun its seven cases successfully.
- Actual inventory: Python **779 direct / 94 modules**, baseline **35/707/22**
  plus Stage 1 **15**, separate child probes **18**. Node **23 entrypoints / 196
  direct**. Inventory-only checks pass, missing/duplicate/extra **0**, missing
  Node source dependencies []. These totals are not full-suite execution claims.
- Preservation: **349/366** starting files remain byte-identical; exactly **17**
  scoped existing files change and **3** are added, none removed (369 total).
  All **132** unaffected starting frontend files retain their bytes. Only the
  intended route/adapter testcase lists and new Node entry/source hash change
  in the manifest; unrelated case ordering is preserved. Git branch/HEAD stay
  unchanged, staged **0** / tracked unstaged **26** / untracked **32**. No other
  worktree or prohibited Git operation is affected. Whitespace checks pass.

### Phase 2D-2 changed files and stop

- Backend production: `backend/main.py`,
  `backend/core/review_envelope_contract.py`,
  `backend/core/review_history_adapter.py`.
- Frontend production: `frontend/src/components/TradingJournal.jsx`,
  `frontend/src/components/JournalTradeChart.jsx`,
  `frontend/src/utils/aiReviewChartSource.js` (new).
- Tests/coordinator/inventory: `tests/test_review_route_compatibility.py`,
  `tests/test_review_history_adapter.py`, `tests/review_source_fixtures.py`,
  `tests/review_chart_handoff.py` (new), `tests/isolation_inventory.py`,
  `tests/run_isolated_tests.py`, `tests/test_full_test_entrypoint.py`,
  `tests/test_quick_verify_docs.py`, `tests/test_inventory.json`,
  `frontend/scripts/ai-review-chart-source.test.js` (new), `frontend/package.json`.
- Docs: `docs/TESTING.md`, `docs/quick_verify.md`, this plan.

Executed focused selections, with absolute verified Python and
`-I -X utf8 -B tests/run_isolated_tests.py`:

```text
tests.test_review_route_compatibility tests.test_review_history_adapter
tests.test_review_history tests.test_main_ai_review_history_consent tests.test_me_data_routes tests.test_journal_query_limits tests.test_isolation_sqlite tests.test_review_finalizer_compatibility tests.test_review_legacy_compatibility tests.test_trade_review_structured tests.test_trade_review_refund tests.test_ai_review_openai_client tests.test_ai_review_safety tests.test_ai_review_safety_finalization tests.test_review_source_contract tests.test_review_source_admission tests.test_review_market_source_admission tests.test_review_display_contract tests.test_review_envelope_contract tests.test_ai_review_openai_transport tests.test_ai_review_chart_provider tests.test_ai_review_quality tests.test_review_access
tests.test_full_test_entrypoint tests.test_storage_fixture_runner tests.test_quick_verify_docs
tests.test_quick_verify_docs
--node-entrypoint test:ai-chart-source --node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-format --node-executable "C:\Program Files\nodejs\node.exe"
--node-regressions --node-executable "C:\Program Files\nodejs\node.exe"
--inventory-only
--node-inventory-only
```

Only Phase 2D-2 is prepared for independent review. No full TestOnly/BuildChecks,
browser/device/CSS final QA, live network/private DB, migration/backfill, client
version/header gate, CanonicalReviewRenderer connection, summary renderer change,
Phase 2D-3 or later work ran. Report then wait for the user's independent review.


## Phase 2D-1 P2 semantic section admission correction — 2026-10-04

Scope: fix only the independently reported merge-before-validation finding.
Verified branch/HEAD remain `feature/structured-trade-review` /
`787a9d5683803003fe2c7bfe1e786f5874847462`; starting staged 0,
tracked unstaged 24, untracked 29. No Phase 2D-2 or other worktree work.

- [x] Reproduce summary corruption hidden by a valid basic/advanced duplicate.
- [x] Validate each original semantic section against the current closed schema
  before combining; explicitly reject cross-section duplicate keys.
- [x] Exercise both reproductions through list/detail/export, with and without
  canonical bodies; prove deterministic reads, synthetic row/file immutability,
  no raw exposure/restoration and zero model/provider/chart/billing/DB writes.
- [x] Run focused adapter, Phase 2C, coordinator/storage/docs and inventory checks,
  record exact counts, compare start hashes and run `git diff --check`.
- [x] Prepare independent re-review evidence and wait after reporting. No Git mutations, frontend
  production edits, live network, private DB or complete TestOnly/BuildChecks.

### Correction and evidence

The old `_structured` merged common summary fields with basic/advanced using
dictionary unpacking before `admit_semantic_source`. A later normal duplicate
therefore hid an unknown nested decision_quality member or an object main_issue.
The canonical-body branch then skipped the semantic body compiler that rejected
some noncanonical cases. Adding the six new tests before production editing
reproduced both canonical approvals in basic and advanced, and accepted equal
duplicates (three failing test IDs, ten failing subtests). Normal canonical and
supported legacy controls passed before and after the fix.

`_semantic_shape` now reads the existing `structured_output_schema` without
changing it: original common fields, the disjoint review-type fields, every
nested object key set and string/list/object type are checked before semantic
assembly. Optional summary confidence fields retain their closed validation and
are checked before assembly too. Cross-section overlap is explicitly rejected,
even for equal valid values. Only validated disjoint fields reach the unchanged
source admission policy. No original is repaired or deleted to gain approval.
The adapter's only changed existing function is `_structured`; one shape helper
and one pure schema import are added. There are no other semantic merge targets.
`_record` still checks every separate raw field before the canonical branch.

Final focused evidence (H4 synthetic SQLite/temp roots, approved existing
Python 3.12.14 and Node 24.15.0; `-I -X utf8 -B`):

- Python **281/281 PASS**, 15 explicitly selected modules: adapter **39**,
  route compatibility **22**, finalizer compatibility **18**, legacy compatibility
  **14**, structured review **75**, refund **13**, safety **17**, safety finalization
  **2**, OpenAI client **16**, source contract **32**, history consent **7**, history
  store **2**, Python coordinator **15**, storage runner **2**, docs **7**.
- Node selected `test:legacy-review-cross-contract`,
  `test:canonical-review-renderer`, `test:ai-format`: **27/27 PASS**;
  `--node-regressions`: **9/9 PASS**. An initial mistyped format entrypoint
  failed inventory preflight before Node launch; using the actual manifest name
  fixed the invocation without code changes.
- Both P2 examples, basic/advanced and canonical present/absent: list/detail/export
  return `unavailable` on all three repeated reads. Each target row crosses the
  same full-row adapter nine times. No hidden raw string, canonical approval or
  restoration trade is returned; summary is fixed unavailable content. Normal
  records keep `canonical` or deterministic `adapted`, with exact canonical
  body/strong wire preserved. All malformed section matrix entries are rejected
  before semantic source admission is called.
- Synthetic row values and SQLite file bytes equal the pre-read baseline;
  caller input remains equal. Forbidden history write/schema initialization,
  model/provider/live chart/billing/event mocks receive **0** calls. Existing
  SELECT-only `mode=ro`, unsafe/unknown chart/tooltip/trade and malformed version
  tests pass. Guarded unexpected **0**; all restoration/patch restoration/cleanup
  true; final FAIL/ERROR/SKIP/inventory issues **0**.
- Actual source inventory: Python **770 direct**, **94 modules**, baseline
  **35/698/22** + Stage 1 **15**, separate child probes **18**. Node **22
  entrypoints/183 direct**. Both inventory-only checks pass, missing/duplicate/
  extra **0**. These are source counts, not a full-suite execution claim.
- Start/end content hashes: **358/366 files unchanged**, exactly eight existing
  files changed, added/deleted **0**. All **135 frontend files byte-identical**;
  Phase 2B/2C source/finalizer/route/provider/storage production files unchanged.
  Changed files are adapter, adapter tests, manifest, inventory count, coordinator
  count assertions, TESTING, quick_verify and this plan. Git branch/HEAD unchanged;
  staged **0**, tracked unstaged **24**, untracked **29**. `git diff --check` passes;
  untracked adapter/tests/plan are additionally checked for whitespace.

Only this P2 correction is prepared for independent re-review. Phase 2D-2,
frontend production connection and all Git mutations remain out of scope.

## Phase 2D-1 whole-record legacy history read adapter — 2026-10-04

### Goal and scope

The user reports independent approval of all Phase 2C and authorizes only
Phase 2D-1. This supersedes the historical Phase 2D HOLD below for this subset;
Phase 2D-2 and later remain out of scope. Verified checkout/branch/HEAD:
`D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`,
`feature/structured-trade-review`, `787a9d5683803003fe2c7bfe1e786f5874847462`.
Starting state: staged 0, tracked unstaged 21, untracked 27. Preserve the
approved existing changes, production finalizer/source/DTO/billing policy,
frontend files and other worktrees.

### Decisions

- List, detail and export must pass full stored records through one closed
  read adapter before projecting a list item. Metadata-only admission is unsafe.
- Validate existing canonical version/shape/content and all separate legacy
  chart, tooltip, trade restoration and metadata surfaces. A valid body cannot
  excuse another field. Unknown fields/versions and corrupt documents fail closed.
- Supported legacy content becomes a deterministic memory copy with canonical
  display documents and derived compatibility summary. No semantic/raw-summary
  fallback after canonical rejection. Unsafe/unsupported records expose only
  fixed unavailable content and no restoration trades.
- History reads use SQLite read-only connections without schema initialization.
  No migration/backfill/update/delete, model/provider, chart generation or billing
  operation is allowed in adaptation. Only H4-owned synthetic databases are used.

### Current status

- [x] Confirm checkout/status, read applicable instructions and current paths.
- [x] Identify metadata-only list and canonical-body short-circuit findings.
- [x] Implement the common whole-record boundary and read-only storage path.
- [x] Add safe/unsafe/unknown, deterministic, copy and DB immutability regressions.
- [x] Run explicit focused Phase 2B/2C, Python/Node coordinator, storage/docs,
  inventory and whitespace checks; verify preservation and final Git state.
- [x] Prepare review evidence and final report. Independent Phase 2D-1 review
  remains pending; stop after reporting and wait for the user.

### Verification and remaining work

Commands are classified as source/inventory reads, scoped source/doc writes,
or H4 checks whose DB/cache/environment/process writes are test-owned temporary
effects with external network blocked. Existing approved Python 3.12.14
(`D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`) and Node 24.15.0
(`C:\Program Files\nodejs\node.exe`) were verified. Full TestOnly/BuildChecks,
browser/device/live network/private DB access and prohibited Git operations
are excluded. Final focused results and preservation checks follow below.
Independent review is the next step after implementation evidence is reported.

### Implementation and evidence

- `backend/core/review_history_adapter.py:adapt_history_record` owns bounded,
  finite JSON copies, closes the actual metadata/five-snapshot fields and nested
  chart/candle/marker/tooltip/card/context/trade/semantic/access variants, validates
  review-display.v1 shape/content and compatibility wire, and checks raw and
  composed visible text with the existing pure safety policy. The existing
  `safe_legacy_history_snapshot` entry point delegates to this one boundary.
- Canonical records preserve their exact body and A1 strong wire without semantic
  reconstruction. Supported summary-only or trade-review.v1 legacy records get
  deterministic canonical documents in memory; old semantic trees are not returned
  as a second display authority. Supported body grammar is A1 paragraph/text/strong;
  reserved markup/section/MA tokens and unsupported shapes are withheld.
- Supplied chart/trade documents must match the deterministic display projection;
  they cannot hide unsafe or unknown raw fields. Stored-trade owner/creation
  metadata is checked before display projection and retained as typed metadata.
  Prices/quantities, fee/tax, dates, candle labels, timeframe/interval/source and
  marker/tooltip control combinations use the current producer constraints.
- Unsafe/unknown/corrupt rows return fixed unavailable content, empty original
  metadata/chart/access, null restoration trade/target and an empty recent list.
  `history_read_status=unavailable` and `trade_restore_allowed=false`. The tested
  body-safe/chart-unsafe counterexample is rejected as a whole record, also with a
  valid canonical body present. Unknown nested safe strings fail closed too.
- Store list reads now decode full rows; list projection occurs only after full
  admission. Detail and export use that same adapter; export has no second per-ID
  read. The route spy observes three full-record calls for list/detail/export and
  identical unavailable results (list equals the detail's metadata projection).
- Read connections use existing SQLite files with `mode=ro`, without CREATE/ALTER
  or parent/DB initialization. Malformed/duplicate snapshot JSON stays invalid
  instead of becoming an empty legacy fallback. Synthetic tests prove SELECT-only
  SQL and unchanged row values/file bytes across repeated safe, canonical,
  structured, unsafe and unknown reads. Intentional fixture-corruption UPDATEs
  happen only during synthetic setup, before the byte/value baseline.
- First focused storage checks were blocked before connection by H4 treating a
  file URI as an ordinary path. This was a test-boundary path interpretation
  failure, not an adapter/content failure. H4 now authorizes only explicit
  absolute `file:` URIs with `uri=True` and exactly `mode=ro`, resolves their real
  path and still requires it inside the owned root. Outside-root, authority,
  fragment, relative URI and other query/mode variants are blocked before open;
  eight expected negative violations are acknowledged, unexpected remains zero.
  Existing SQLite alias/factory/ATTACH/VACUUM rejection probes remain passing.

### Final focused results and stop

- Selected Python **394/394 PASS in 26 modules**, including adapter 33, existing
  history/consent/export/query 17, SQLite coordinator 3, Phase 2B source 81,
  Phase 2C route 22/finalizer 18/A1 14/structured 75/refund 13 and safety,
  transport, access, display/envelope, Python coordinator 15/storage 2/docs 7.
  Adapter/route/consent passed their final read refinement rerun (33/22/7), and
  adapter/docs passed again (33/7) after checking the actual weekly-ad access
  source literal and stored-trade metadata fixture. All 23 guarded primary
  reports have unexpected 0; all 26 reports have restoration/patch restoration/
  cleanup true, inventory issues/FAIL/ERROR/SKIP 0. The three coordinator reports
  have no top-level unexpected counter; their nested positive/negative evidence
  contracts pass and are not added to direct counts.
- Node selected A1 cross-contract 11 + canonical React 9 + format 7 = **27/27
  PASS**; Node coordinator **9/9 PASS** separately. Coverage missing/extra/
  duplicate 0; guarded unexpected 0; restoration/patch restoration/cleanup true.
- Adapter guards assert zero model/provider/live chart/charge/refund/storage/event
  calls. Its module imports only standard-library and pure contract validators.
  Generation/finalizer/sealing/refund/replay policy is unchanged. Response/history/
  cache/replay exact body/strong wire, one refund on failure and zero additional
  replay model/charge/refund/history operations pass their existing Phase 2C tests.
- Source inventory is Python **94 modules / 764 direct** = baseline **749**
  (35 / 692 / 22) + Stage 1 **15**, with **18** separate child probes; Node
  **22 entrypoints / 183 direct**. This adds 33 adapter testcase IDs only;
  final source/manifest missing/duplicate/expected skip are 0; Node missing/extra/
  duplicate 0 and missing source dependencies []. These are source inventory
  totals, not whole TestOnly execution counts.
- `git diff --check` passed with exit 0. Untracked adapter/test/plan whitespace
  checks against NUL have no whitespace diagnostics (no-index exit 1 means the
  files differ from NUL; only expected LF-to-CRLF informational warnings occur).
- Hash preservation: 352/364 starting non-ignored files remain byte-identical;
  the only 12 existing-file edits are the scoped files listed below, plus two new
  files. All 135 frontend files and the approved body/envelope/compatibility/
  source DTO/projection/compiler implementations are byte-identical. No file was
  removed, no other worktree was changed, and no Git mutation was performed.
- Final Git: same branch/HEAD, staged **0**, tracked unstaged **24**, untracked
  **29**. This preserves the starting 21/27 and adds tracked edits to history
  storage, DATA and the URI isolation helper, plus the two new adapter/test files.
  No full TestOnly/BuildChecks, browser/device/live network/private DB or
  production configuration/data/deployment work ran. Phase 2D-1 is ready for
  independent review; Phase 2D-2 and later remain unstarted.

### Changed files in this phase

- Backend: `backend/core/review_history_adapter.py` (new),
  `backend/core/ai_review_v2.py` (history wrapper only),
  `backend/core/review_history.py` (whole-row/read-only/strict JSON reads),
  `backend/main.py` (history read/projection/export boundary only).
- Tests: `tests/test_review_history_adapter.py` (new),
  `tests/module_isolation.py` (closed read-only URI authorization),
  `tests/isolation_inventory.py`, `tests/test_inventory.json`,
  `tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`
  (33-case module registration/counts and pre-import coverage).
- Docs: `docs/DATA.md`, `docs/TESTING.md`, `docs/quick_verify.md`,
  `docs/exec-plans/structured-trade-review.md` (this plan and focused evidence).

### Executed H4 selections

All commands use the verified absolute Python with `-I -X utf8 -B
tests/run_isolated_tests.py` in this worktree. Exact successful selections:

```text
tests.test_review_history_adapter tests.test_review_history tests.test_main_ai_review_history_consent tests.test_me_data_routes tests.test_journal_query_limits tests.test_isolation_sqlite
tests.test_review_route_compatibility tests.test_review_finalizer_compatibility tests.test_review_legacy_compatibility tests.test_trade_review_structured tests.test_trade_review_refund tests.test_ai_review_openai_client tests.test_ai_review_safety tests.test_ai_review_safety_finalization tests.test_review_source_contract tests.test_review_source_admission tests.test_review_market_source_admission tests.test_review_display_contract tests.test_review_envelope_contract tests.test_ai_review_openai_transport tests.test_ai_review_chart_provider tests.test_ai_review_quality tests.test_review_access
tests.test_full_test_entrypoint tests.test_storage_fixture_runner tests.test_quick_verify_docs
tests.test_review_history_adapter tests.test_review_route_compatibility tests.test_main_ai_review_history_consent
tests.test_review_history_adapter tests.test_quick_verify_docs
--inventory-only
--node-inventory-only
--node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-format --node-executable "C:\Program Files\nodejs\node.exe"
--node-regressions --node-executable "C:\Program Files\nodejs\node.exe"
```

Reruns replace earlier reports for the same testcase IDs; **394** is the final
unique selected Python count. No `--all`, `--node-all` or verification wrapper
mode was executed. The only next step is independent Phase 2D-1 review.



## Phase 2C independent review P2 — prompt/admission consistency — 2026-10-04

### Scope and decision

Fix only the finding that the advanced production terminology prompt requests
reserved moving-average abbreviations. Verified worktree, branch and HEAD match
the request: feature/structured-trade-review,
787a9d5683803003fe2c7bfe1e786f5874847462. Starting Git state is staged 0 /
tracked unstaged 21 / untracked 27. All 364 starting source hashes and planned
edit target copies are recorded in task-owned host temporary evidence.

Only the advanced terminology instruction changes in production: daily charts
use 5일/10일/20일 이동평균; non-daily charts name the actual timeframe and bar
count (1분봉 차트의 5개 봉 이동평균). Keep the existing distinction between
timeframe and moving-average period. A1 reservations, finalizer order, summary/
canonical roles, source/DTO/market-data, route/refund policy and frontend stay
unchanged. Phase 2D HOLD. No unrelated refactor or prohibited Git operation.

### Progress and verification

- [x] Confirm actual checkout/status and inspect the contradictory prompt and
  existing prompt assertions. Preserve other worktrees and pre-existing work.
- [x] Replace only the advanced terminology paragraph; update its existing
  prompt regression and add one production route consistency testcase.
- [x] Validate real captured prompt, the exact safe natural-language semantic,
  and reserved MA20/MA5/MA 20/ma20 counterexamples through the real route.
- [x] Run selected H4 Phase 2C/Phase 2B/core/coordinator/storage/docs and A1
  cross-contract regressions, recompute inventory and inspect focused diff.
- [x] Prepare final evidence and Git/preservation report; await finding re-review.

Commands are classified as source/inventory reads, limited source/doc writes
and task-owned temporary evidence writes. Tests use only the existing H4
boundary with synthetic DB/cache/environment, mocked model/providers and
blocked external network. Verified existing Python 3.12.14 and Node 24.15.0
are reused; no install. Full TestOnly/BuildChecks, browser/device/live network/
private DB and production configuration/data/deployment are out of scope.
Independent re-review of this finding remains pending after the report.

First selected run passes all existing core, prompt, source, coordinator/storage/
docs modules and A1 cross-contract. The new route testcase alone expected one
serializer call across both production generation and history restoration;
actual count is two because canonical history restoration validates the same
body's wire. Do not change production or remove history validation. Replace
that invented global count with admission rejection calls 0 and positive success
calls whose every input equals the same sealed body. A2's existing generation/
seal-order regressions remain unchanged and passing. Rerun route and final docs.

### P2 final results and stop

- Actual captured advanced instructions contain no case-insensitive MA-number
  pattern and do contain daily natural-language and non-daily bar-count terms.
  The exact `일봉 차트의 20일 이동평균과 체결 기록을 비교했습니다.` semantic
  returns ready, seal 1, refund 0 and one opt-in history row. Generation and
  subsequent history-wire validation use only the same sealed body; summary
  equals A1_serializer(sealed body). No finalizer/serialization policy changes.
- Exact counterexample `일봉 차트의 MA20과 체결 기록을 비교했습니다.` and
  MA5/MA 20/ma20 variants each return error/invalid_structured_output, seal 0,
  serializer 0, refund exactly 1 and new history save/approval 0. Replay adds
  model/charge/refund/history 0 for both successful and rejected results.
- Final focused Python **280/280 PASS in 13 modules**: route 22, OpenAI client
  16, A2 finalizer 18, A1 compatibility 14, structured 75, refund 13, safety 17,
  source contract 32, source admission 23, market admission 26, Python coordinator
  15, storage coordinator 2 and docs 7. The corrected passing route report
  supersedes only its initial new-test expectation failure in the final count.
  All 11 guarded reports have unexpected 0; all 13 have restoration/patch
  restoration/cleanup true and official report validation issues 0. Coordinator
  nested evidence contracts pass; they have no top-level unexpected counter.
- A1 actual frontend cross-contract **11/11 PASS** and synthetic Node coordinator
  **9/9 PASS**. Missing/extra/duplicate selected coverage 0, cross-contract
  unexpected 0, restoration/patch restoration/cleanup true. No frontend edits.
- Current source inventory: Python **93 modules / 731 direct** = baseline
  **716** (35 / 659 / 22) + Stage 1 **15**, with **18** separate child probes;
  Node **22 entrypoints / 183 direct**. Missing/duplicates/expected skips 0,
  Node missing/extra/duplicate 0 and missing source dependencies []. Exactly
  one route testcase ID is added; all existing manifest entries/order/IDs stay.
  Inventory totals are source counts, not a whole-suite execution claim.
- Production delta is exactly one terminology hunk: three old instruction
  string lines become four natural-language string lines. The rest of
  ai_review_v2.py is unchanged from this turn's start. A1 validator/fixtures,
  finalizer order, body/envelope/source/DTO/market implementations, main route/
  refund/cache/history policies and all 135 frontend files are byte-identical.
  **355/364 starting files are unchanged; 9 changed, new files 0.**
- Changed files are backend/core/ai_review_v2.py; tests/test_ai_review_openai_client.py,
  tests/test_review_route_compatibility.py, tests/isolation_inventory.py,
  tests/test_full_test_entrypoint.py, tests/test_inventory.json; docs/TESTING.md,
  docs/quick_verify.md and this plan. Limited source changes, source hashes/copies,
  focused logs and official verification/preservation JSON are retained in the
  task-owned temporary evidence directory. One documentation patch failed on
  an incomplete long-line context; a smaller exact-context patch succeeded.
  No product failure was inferred from that tool error.
- Git remains feature/structured-trade-review at
  787a9d5683803003fe2c7bfe1e786f5874847462; staged 0 / tracked unstaged 21 /
  untracked 27. Diff whitespace and untracked text whitespace checks pass.
  No other worktree write, forbidden Git operation, full TestOnly/BuildChecks,
  browser/device/live network/private DB, install or deployment. Evidence is
  isolated direct-route/unit and React server rendering, not live HTTP/device.
- The P2 finding is implemented and focused verification passes; independent
  re-review is pending. **Phase 2D HOLD. Report and wait.**

## Phase 2C-A3 — route/refund/replay/history/cache — 2026-10-04

### Goal and scope

A1/A2 are independently approved. Remove only the production assumption that
compatibility summary bytes equal canonical visible text. Display authority is
the sealed canonical body; summary is its unchanged deterministic A1 wire.
Connect opt-in history to that same approval, without a new API/schema/version,
legacy whole-record adapter expansion, frontend production change or Phase 2D.

Verified root/branch/HEAD match the request: this worktree,
feature/structured-trade-review, 787a9d5683803003fe2c7bfe1e786f5874847462.
Starting state: staged 0 / tracked unstaged 21 / untracked 26. All 363 starting
source files have recorded hashes; planned edit targets have task-owned host
temporary starting copies. Preserve unrelated edits and every other worktree.

### Decisions and current status

- [x] Inspect actual route/finalizer/history/cache and A1/A2/Phase 2B contracts.
- [x] Pass internal sealed approval to route and validate body/wire against it.
- [x] Preserve terminal compatibility error, one refund and no failed history.
- [x] Save only preapproved opt-in history metadata with the same sealed body.
- [x] Verify strong/plain, normal/fallback, replay, history and mutation isolation
  through production routes; retain A1/A2/safety/source regressions.
- [x] Recompute inventory, run selected H4 Python/Node/storage/docs and diff checks.
- [x] Prepare evidence and Git/preservation report for whole Phase 2C independent review.

### Verification and remaining work

Production equality assumptions found in main._normalize_ai_review_result and
ai_review_v2.safe_legacy_history_snapshot's existing canonical-document branch.
Cache/replay already copy result values but must retain internal sealed approval.
Current finalizer deliberately leaves history approval empty under Phase 2B;
A3 authorizes success-only history wiring. Legacy rows without a canonical
document retain their existing adapter; no new legacy conversion is added.

Read-only source/inventory checks and task-owned temporary evidence writes are
separate from tests. Use verified Python 3.12.14 at
D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe and Node 24.15.0 at
C:\Program Files\nodejs\node.exe. Explicit H4 module/entrypoint selection only:
synthetic DB/cache/environment writes and coordinator children stay inside the
existing isolation boundary; providers mocked and external network blocked.
No full TestOnly/BuildChecks, browser/device/live network/private DB, production
configuration/data/deployment, prohibited Git action or other-worktree write.
Phase 2D HOLD. Independent review is pending after A3's implementation/report.

### A3 production contract and first focused evidence

- Route consumes the existing internal approval_state snapshot and compares the
  complete returned body, A1 wire and status/source/review_type to its sealed
  envelope. It never repairs or replaces returned display/summary. Access,
  history ID and replay flag are operational metadata outside that seal.
- Cache retains that same immutable ApprovedReviewSnapshot beside an owned
  response copy. Finish/replay validate the wire against the sealed body; only
  the replay access flag changes. No semantic/raw-summary reconstruction.
- Opt-in history metadata uses the existing canonical trade/chart helpers and
  visible-safety validation before sealing. Metadata is retained as independent
  JSON text beside the same immutable body snapshot. Only ready/missing_key
  results can approve it; errors and empty results cannot approve/save history.
  Save validates response against that approval and persists existing JSON
  columns, with no schema change. Existing canonical history restoration checks
  A1 wire against its stored body; the no-document legacy adapter is unchanged.
- First route-focused run: new production route 21, existing refund 13,
  history/consent 7, finalization cleanup 2: 43/43 PASS. All four reports have
  unexpected 0, restoration/patch restoration/cleanup true, inventory issues 0.
  Exact sentence and actual basic/advanced strong semantics both pass, including
  opt-in storage/replay. Compatibility, safety, malformed/schema-invalid error
  cases refund exactly once, approve/save no history and replay with no extra
  model/charge/refund/history/consent/preparation calls. Tampered/unsealed content
  fails closed; post-refund cache failure still refunds only once.
- Source inventory: Python 93 modules / 730 direct = 715 baseline
  (35 / 658 / 22) + Stage 1 15, with 18 separate child probes. Node unchanged
  22 entrypoints / 183 direct. Missing/duplicate/expected skips 0; Node
  missing/extra/duplicate 0 and missing source dependencies []. Source counts
  are not a claim of whole-suite execution.
- Remaining contract run passes all production, safety, source, history-store
  and docs modules. One coordinator testcase still expected the prior 694
  baseline while source/manifest correctly report 715 after A3's 21 additions.
  Correct only that expectation and rerun the coordinator; this is an inventory
  expectation failure, with no product-code change. Node selected entries
  (A1 cross-contract 11, canonical React 9, format 7) and coordinator 9 pass.

### A3 final verification, preservation and stop

- Final focused Python: **349/349 PASS in 22 explicit modules**. Route 21,
  refund 13, history/consent 7, finalization cleanup 2, A2 finalizer 18,
  A1 compatibility 14, structured 75, OpenAI client 16, safety 17, source
  contract 32, source admission 23, market admission 26, display 14,
  envelope 26, quality 3, chart provider 1, OpenAI transport 10, review
  access 5, history store 2, Python coordinator 15, storage coordinator 2,
  docs 7. The initial coordinator expectation failure remains in its log;
  the corrected coordinator's passing report replaces it in the final total.
  No product-code changes followed the passing production regression run.
- All 20 guarded reports have unexpected 0. All 22 reports have restoration,
  patch restoration and cleanup true, inventory issues/FAIL/ERROR/SKIP 0.
  Both coordinator reports validate their registered nested evidence instead
  of exposing a top-level unexpected count. The official check_report and
  check_node_report validators accept every final selected report.
- Node: A1 actual frontend cross-contract **11/11**, canonical React **9/9**,
  unchanged format **7/7**, total **27/27 PASS**. Synthetic Node coordinator
  **9/9 PASS** separately. Selected coverage missing/extra/duplicate 0 and
  unexpected 0; restoration/patch restoration/cleanup true. A report-only
  summarizer initially treated the Node reports mapping as a sequence; the
  corrected mapping reader and official validators confirm the saved results.
- Exact production route body fixture: canonical visible text is
  `체결 기록을 확인합니다.`, AST is strong(`체결 기록`) + text(`을 확인합니다.`),
  compatibility wire is `**체결 기록**을 확인합니다.`. Both routes accept/store/
  replay this exact fixture. Real basic/advanced semantic model fixtures also
  preserve that strong sentence within the normal production templates; their
  wire differs from canonical text and equals A1_serializer(sealed body).
- All failed compatibility/safety/malformed/schema-invalid routes have refund
  exactly 1, failed history approval/save 0, and replay model/charge/refund/new
  history 0. Compatibility errors remain bodyless terminal errors; no fallback,
  missing_key or ready promotion. Normal/missing-key fallback history works
  with opt-in; storage-off history preparation is 0. Response/source/metadata/
  history/cache/replay mutations cannot change sealed bytes or other snapshots.
  Bad wire in history is withheld; bad cached wire fails before side effects.
- A1 grammar, shared PASS 10 / FAIL 65 vectors, frontend harness and renderer
  are unchanged. A2 compatibility/safety precedence, Phase 2B source admission,
  DTO sealing/protection, episode/window and compiler contracts all pass.
  Sealed envelope history remains None; only existing route/history storage
  metadata is connected. No schema/version or frontend transition is introduced.
- Preservation: **347 of 363 starting files byte-identical**. All **135 frontend
  files** are unchanged, including production files, test/fixture/harness,
  package/lock and canonical renderer. A3 modifies 16 starting files: two backend
  production files, three docs/plan files, and eleven test/fixture/inventory
  files. One new 21-case production route regression module is added. Existing
  manifest module order is preserved; only two renamed testcase IDs and the
  new module's IDs are changed. Source/market/DTO/body/envelope/A1 implementations
  and existing runner code remain byte-identical. A3-only patch, initial copies,
  verification JSON and H4 logs are retained in the task-owned host temporary
  evidence directory. No other worktree writes occurred.
- Git diff --check and all untracked text whitespace checks pass. Branch
  feature/structured-trade-review, HEAD
  787a9d5683803003fe2c7bfe1e786f5874847462; staged **0**, tracked unstaged **21**,
  untracked **27**. No stage/commit/push/reset/revert/stash or branch/history
  operation. Full TestOnly/BuildChecks and browser/device/live network/private
  DB remain unexecuted by explicit scope. This is isolated direct-route/unit/
  React server-render evidence, not HTTP/browser/device/deployment evidence.
- **Phase 2C-A3 implementation and focused verification complete. Whole Phase
  2C is ready for independent review; approval is pending. Phase 2D HOLD.**
  Report the concrete changes, evidence and limits, then wait for the user.

## Phase 2C-A2 — production finalizer admission — 2026-10-04

### Goal and scope

A1 is independently approved. Connect its unchanged legacy-safe grammar to
production body approval, with summary serialization only from sealed body.
Preserve every basic/advanced semantic value and the four advanced fallback
sections. Only minimal owned template changes, finalizer wiring, focused
regressions, inventory and verification documentation are authorized.

Root/branch/HEAD match the request: this structured-trade-review worktree,
feature/structured-trade-review, 787a9d5683803003fe2c7bfe1e786f5874847462.
Starting state: staged 0 / tracked unstaged 21 / untracked 25. Starting hashes
for 362 files and source copies/diff are in a task-owned host temporary root.
No more specific AGENTS instructions exist. Preserve all unrelated changes.

### Decisions and current status

- [x] Inspect A1 grammar, canonical templates, production finalizer, H4 runner and actual checkout.
- [x] Replace basic parser-dependent section/list syntax with safe paragraphs; retain advanced content and avoid owned whitespace at empty optional sections.
- [x] Validate canonical safety, then A1 compatibility, then seal, then generate summary with A1 serializer from sealed body. Compatibility rejection is terminal: error, no snapshot/summary leak, no fallback retry; real safety_rejected retains precedence.
- [x] Verify normal, fallback, low-confidence, fixed/unavailable and empty paths, P1 inputs, boundary bypasses and all A1 fixtures through production builders/finalizer.
- [x] Run only explicitly selected H4 Python/Node regressions, storage/docs, inventory and diff checks; record actual counts and preservation evidence.

### Verification and remaining work

Use the existing dependency-equipped Python 3.12.14 at
D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe and Node 24.15.0 at
C:\Program Files\nodejs\node.exe, both verified this turn. Source reads and
task-owned temporary evidence are separate from H4 tests; synthetic DB/cache/
environment writes and child processes remain under the H4 boundary, with
providers mocked and network blocked. No full TestOnly/BuildChecks.

The current route still requires summary == canonical visible text. A1 strong
wire deliberately differs; route/refund/replay/history/cache connection and its
verification remain A3. No such production code is changed here. No frontend
production, A1 cross-contract harness, CanonicalReviewRenderer, source/market
admission, DTO protection, objective/window, browser/device/live/private DB,
other worktree or Git mutation. Phase 2D remains HOLD. Report A2 evidence and wait.

Initial verification exposed only expectation conflicts: the A1 mid-word strong
fixture is display-compatible but future-trade guidance, which production
safety must continue to reject; older strong/basic assertions expected plain
wire/reserved labels, and the coordinator baseline count needed A2's 19 added
cases. Preserve the A1 vectors/harness and safety implementation; update only
the corresponding regression expectations/inventory. The docs check initially
failed twice on the inventory count/required literal format; stop the broad
rerun approach, statically match the actual required inventory string and use
the focused docs-only path, which passes. Preservation tooling separately
stopped on a missing client-test starting copy and a byte mismatch in the
attempted reconstruction. Recover that evidence from the saved starting diff
and the recorded HEAD blob; its CRLF starting bytes match the recorded SHA256.
No working file was restored and no product failure was inferred from these
verification tooling errors.

### A2 result, evidence and stop

- Production changes: `review_display_contract.compile_structured_review`
  uses four basic safe paragraphs with all qualitative fields/checks in order;
  basic fallback keeps the full verdict, strength, weakness and three checks.
  Owned labels are now 이번 매매 판단 / 확인된 강점 / 개선할 점 / 다음 매매 점검,
  with no section/list parser dependency. The default basic strength sentence
  uses the same safe wording without changing its meaning. All intermediate
  boundaries are `\n\n`, final boundary empty. Advanced normal retains all
  values and eight sections; only template whitespace for empty optional
  arrays changes. The advanced fallback function itself is unchanged and its
  four sections match both independently fixed A1 open/profit fixtures exactly;
  existing partial-loss/open-position evidence also passes.
- Approval: normalized model body safety precedes compatibility admission,
  so a low-confidence selection cannot hide incompatible model text. Selected
  envelope canonical safety also precedes `validate_legacy_body`, seal and
  result publication. Admission itself generates no wire. The serializer is
  `admit_legacy_body` applied only to `json.loads(snapshot.json_text)["body"]`.
  Ordering spies and post-seal candidate mutation verify this for both types,
  normal/fallback/fixed/empty; old summary producers are forbidden by the tests.
  No semantic/raw-summary reread, trim/replace/normalize/truncate or copied
  frontend regex is added. A1 grammar, rejection codes and admitted wire stay
  unchanged after splitting validation from serialization.
- Rejection: compatibility failure returns `error` / `invalid_structured_output`
  (or preserves prior `safety_rejected`), summary empty, no display/semantic
  exposure, approval snapshot None and history approval None. It never retries
  a fallback/fixed template or becomes missing_key/ready. Both exact P1 inputs
  are tested through both actual builders: ready **0**, seal **0**, serializer
  calls **0**, raw compatibility summary exposure **0**. Missing-key fallback
  whitespace/MA incompatibility is terminal error too.
- Normal basic/advanced, both fallbacks, low-confidence selection, fixed safe/
  unavailable, empty and normal strong `체결 기록` pass through real production
  builders and compilers. Every normal semantic leaf is present in the body.
  Normal strong serializes `**체결 기록**` with unchanged strong AST metadata.
  Literal markup, whitespace edges/internal/newline/tab/NBSP, MA/reserved tokens,
  run cuts and paragraph splits reject at the actual finalizer boundary.
- A1 shared matrix is unchanged: compatibility **10 PASS / 65 FAIL**. The
  finalizer body-boundary matrix preserves all 65 rejections with no ready,
  seal or serializer calls and exact wire for the nine safe PASS documents,
  in both review types. The one display-valid future-recommendation PASS
  (`mid_word_strong`) remains compatibility-valid but production rejects with
  `safety_rejected` and admits its real safe fallback. This is required existing
  safety precedence, not an A1 grammar/fixture change. Actual raw-model P1 tests
  and normal/fallback compiler paths do not inject candidate documents.
- Focused Python final results: **291/291 PASS in 16 explicit modules**:
  legacy 14, production finalizer 18, structured 75, OpenAI client 16,
  safety 17, finalization 2, source contract 32, source admission 23,
  market admission 26, display 14, envelope 26, quality 3, chart provider 1,
  Python coordinator 15, storage coordinator 2, docs 7. All 14 guarded reports
  have unexpected 0; all 16 have restoration/patch restoration/cleanup true,
  no inventory issues and no failed/skipped final direct cases. Both coordinator
  reports retain their nested evidence contracts rather than a top-level
  unexpected count. Earlier failed expectation reports remain in temporary
  logs; only the latest complete passing module reports count toward 291.
- Focused Node: unchanged A1 actual frontend cross-contract **11/11**, canonical
  React **9/9**, format **7/7**, total **27/27 PASS**. Synthetic Node coordinator
  **9/9 PASS** separately. Registered selected entrypoint coverage has missing/
  extra/duplicate 0, unexpected 0 and restoration/patch restoration/cleanup true.
- Actual source inventory: Python **92 modules / 709 direct** = baseline
  **694** (35 / 637 / 22) + Stage 1 **15**, with **18** separate child probes;
  missing/duplicates/expected skip 0. Node **22 entrypoints / 183 direct**, with
  missing/extra/duplicate 0 and missing source dependencies []. Neither full
  inventory is claimed executed as a complete TestOnly run.
- Preservation: **348 of 362 starting files byte-identical**, including all
  **135 frontend files**, A1 fixtures/harness/renderer, main, source/market/DTO
  implementations, envelope compiler/contract, history/cache/replay and runner.
  Only 14 starting files change: four production files, three docs/plan files,
  and seven tests/inventory/registry files. One new production regression module
  is added. Node manifest unchanged; Python manifest changes only the new module,
  one admission-only testcase and two strong-wire regression names. Git diff
  whitespace and untracked whitespace checks pass; no other worktree writes.
- Git: feature/structured-trade-review, HEAD
  787a9d5683803003fe2c7bfe1e786f5874847462, staged **0**, tracked unstaged **21**,
  untracked **26**. No stage/commit/push/reset/revert/stash or other worktree
  change. Evidence logs, initial hashes, recovered source copy, A2-only diff,
  verification and preservation JSON stay in the task-owned host temporary root.
- A2 implementation and focused verification are complete and ready for
  independent review. A3 can follow acceptance of this boundary; the existing
  route's summary == canonical_text assumption must be reconciled with strong
  wire there, alongside refund/replay/history/cache validation. A3 and Phase 2D
  are not implemented. Phase 2D **HOLD**. No full TestOnly/BuildChecks, browser,
  device, live provider/network/private DB, install or deployment. Report and wait.

## Phase 2C-A1 — selected A: Legacy-safe subset — 2026-10-04

The user selects the redesigned legacy-safe subset and authorizes only the
standalone compatibility grammar and actual frontend cross-contract proof.
This supersedes the earlier Phase 2C readiness claim: Phase 2D stays **HOLD**.
No finalizer/route/refund/status/history/cache/replay connection, body-template
change, TradingJournal production edit, or Git mutation is authorized.

- [x] Confirmed root, feature/structured-trade-review, HEAD 787a9d5683803003fe2c7bfe1e786f5874847462, worktrees, staged 0 / tracked unstaged 21 / untracked 20; recorded starting hashes and diff in a task-owned host temporary directory.
- [x] Read actual aiReviewFormat and TradingJournal declarations; identified whitespace, MA, section-token and inline-strong behavior. No more specific AGENTS files exist.
- [x] Implemented pure canonical-body-only admission and deterministic strong wire serialization with explicit rejection, without repairing input or copying a frontend parser.
- [x] Added independently authored shared PASS 10 / FAIL 65 vectors, including both P1 counterexamples and run/paragraph-boundary bypasses.
- [x] Executed actual production parser and JSX declarations through a test-only compiler/load and real React server renderer; consumed actual Python admission output and gated rejected vectors before frontend calls. Asserted ordered paragraphs, visible text and exact strong ranges against independently fixed expectations and canonical AST metadata.
- [x] Ran only new contract/cross-contract, existing display/React, Python/Node coordinator, source inventory and docs regression; audited diff whitespace and preservation. Effects are source reads and synthetic H4-owned temporary files/fixtures, including the existing coordinator's synthetic storage probes. No persistent DB/provider/network/build/device execution occurred.
- [x] Prepared grammar, counts, backend/frontend evidence, inventory, production preservation and Git-state report. A1 prerequisites for A2 pass; report and wait. A2 and Phase 2D are not implemented or authorized here.

### A1 result, evidence and stop

- Grammar: validated review-display.v1 body; paragraph blocks; text/strong runs; only `\n\n` intermediate separators and an empty final separator. Single internal ASCII spaces and ordinary punctuation are retained. Paragraph edge spaces, consecutive spaces, all other whitespace and BOM, strong edge spaces, literal markup delimiters, heading/list/divider structures, arbitrary separators, and reserved MA/basic-section/display tokens reject explicitly. Checks use joined visible paragraphs and the full canonical text so run splitting and paragraph splitting cannot bypass reservations. No trim/replace/normalization or semantic/raw-summary fallback.
- `admit_legacy_body` returns an immutable success/summary or `LegacyCompatibilityContractError` with a stable code and optional block index. Text is verbatim; strong is `**text**`. The normal strong wire `**체결 기록**을 확인합니다.` deliberately differs from canonical visible text `체결 기록을 확인합니다.`. The contract requires the actual visible text, paragraph ordering and exact strong ranges, not wire/canonical byte equality.
- Shared fixed vectors: **10 PASS / 65 FAIL**. Two exact P1 literal cases (`현재는 매**수** 추천합니다. *` and `현재는 매**수** 추천합니다. [참고](url)`) and both corresponding strong-AST bad-suffix variants reject; the actual Python records have no summary. The frontend gate executes zero frontend calls for both P1 cases and all 65 FAIL fixtures. Normal strong passes and React emits one strong element with exact text `체결 기록` at paragraph codepoints `[0,5)`. Multiple/adjacent/mid-word strong, Unicode and both four-paragraph advanced fallback shapes preserve exact order and ranges in basic and advanced display modes.
- A source audit identified tokens spanning paragraph separators (`MA\n\n20`, `잘한\n\n점:` etc.). Full canonical reservations and five fixed failures now cover this bypass. Lexical failures also reject at every text/strong cut tested by the Python matrix.
- Actual cross-contract: a fresh H4 Python child imports only the canonical/legacy contracts, admits the fixed canonical documents and passes actual success/rejection records to Node via an owned temporary JSON. Node directly imports unchanged aiReviewFormat and selects the original three TradingJournal declarations by TypeScript AST. Existing TypeScript 4.2.4 lowers only JSX, then the exact declarations execute with real React 19.2.6 server rendering. DOM inspection retains p nodes, element nesting, visible text and strong start/end offsets. No production export, duplicate parser/renderer, expected generation from production output, or HTML-tag-stripped-only assertion is used. Exact React/TypeScript file allowlists, lock versions and source/dependency hashes are checked before temporary copy; no install/download.
- Focused Python: **51/51 PASS** across five modules: legacy 13, canonical display 14, Python coordinator 15, storage coordinator 2, docs 7. The three guarded reports have unexpected 0; all five have restoration/patch restoration/cleanup true, no inventory issues and no failed/skipped direct cases. The two coordinator reports validate nested evidence rather than exposing a top-level unexpected counter.
- Focused Node: cross-contract **11/11**, canonical React **9/9**, actual format **7/7**, totaling **27/27 PASS**; Node coordinator **9/9 PASS** separately. Registered entrypoints and actual backend handoff have unexpected 0 and restoration/patch restoration true; Node-owned roots are cleaned up. Missing/extra/duplicate selected coverage is 0. These are unit/server-render evidence; browser/CSS/device/external behavior is unverified.
- Source inventory: Python **91 modules / 690 direct** = baseline **35 / 618 / 22** + Stage 1 **15**, with **18** child probes counted separately; Node **22 entrypoints / 183 direct**. Missing/duplicate/extra/source dependencies and expected skips are 0. Counts are recomputed from declarations, not a claim the full inventory ran. Full TestOnly/BuildChecks were not executed.
- Preservation audit: **347 starting files remain byte-identical**, including all existing backend production implementations, body templates/finalizer/status/refund/route/history/cache/replay, aiReviewFormat, TradingJournal and canonical renderer. The only new backend production file is the unconnected pure contract. Existing production behavior changes in A1: **0**. All writes are in this worktree or task-owned host temporary evidence; other worktrees were not modified. Git diff whitespace and a separate untracked whitespace scan pass.
- Final evidence aggregation: two ad hoc audit attempts stopped after an AssertionError (coordinator unexpected is null) and KeyError (an assumed nested-evidence field does not exist). No implementation change resulted. The materially different replacement uses the official H4 `check_report` and `check_node_report` validators on the saved actual reports; all nine focused/refreshed report validations pass with issues 0. The executed product tests had no failures.
- A1 changes **15 files**: new `backend/core/review_legacy_compatibility.py`, `frontend/scripts/fixtures/review-legacy-compatibility-v1.json`, `frontend/scripts/legacy-review-cross-contract.test.js`, `tests/test_review_legacy_compatibility.py`, `tests/review_legacy_handoff.py`; updated `frontend/package.json`, `tests/isolation_inventory.py`, `tests/run_isolated_tests.py`, `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`, `tests/test_quick_verify_docs.py`, `docs/TESTING.md`, `docs/quick_verify.md`, this plan. All pre-existing edits outside these additions are preserved.
- Git: `feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`; staged **0**, tracked unstaged **21**, untracked **25**. No stage/commit/push/reset/revert/stash or other prohibited Git action. **A2 prerequisite proof PASS**, ready for the next separately authorized step; production integration is not validated by this isolated proof. **Phase 2D HOLD**. Report and wait.

## Phase 2C confirmed advanced fallback newline contract — 2026-10-03

The user explicitly supersedes the former single-newline advanced fallback assertion: its three top-level boundaries now use `\n\n`, with the final separator empty. Section wording/spacing, basic fallback, normal basic/advanced, sealed-body-only compatibility serialization and all source/safety/production integration boundaries stay unchanged. The contract conflict recorded below is historical and resolved by this instruction. No Phase 2D or prohibited Git operations.

- [x] Reconfirmed root, branch, HEAD, worktrees and staged 0 / tracked unstaged 21 / untracked 19. Saved all starting file hashes to a task-owned temporary root.
- [x] Changed only canonical advanced fallback top-level separators in production. Fixed literal expected strings explicitly encode the confirmed double-newline contract; no expected data is generated from runtime output.
- [x] Added one shared synthetic fixed JSON contract read by Python builder assertions and the unchanged actual Node frontend parser, with an exact source allowlist/manifest read. Both open-position and closed-profit fallback cases preserve each legacy section character and parse as four paragraphs. No testcase count is added.
- [x] Reran Phase 2C focused H4 Python/Node/React/coordinator/storage/docs and both source inventories; audited whitespace and all untouched starting bytes.
- [x] Prepared independent-review readiness and final Git status report. Independent review remains pending; stop here and do not perform Phase 2D.

### Confirmed-contract result and evidence

- Before: `recent\nrepeated\nloss\nquestions`; after: `recent\n\nrepeated\n\nloss\n\nquestions`. The first three advanced fallback block separators are `\n\n`; the last is empty. The canonical builder's private helper keeps `\n` as its default, so basic fallback is unchanged. The basic body template and normal basic/advanced implementations are untouched.
- Fixed expectations explicitly write double newlines for one-open-fill and closed-profit fallback cases. The shared JSON fixture independently records old exact strings, new exact strings, and four exact section values. Python asserts actual builder output, sealed body flatten, result body, fixed expected and fixture summary equality; its canonical run text per block equals the legacy section value. Node imports the unchanged production `parseAiReviewDocument` and gets exactly four paragraph blocks with all four values in order. No section content or internal spaces are replaced to construct expectations from actual output.
- Python focused: **298/298 PASS across 20 explicit modules**, with the same selected coverage and module counts as the candidate record below. All 18 guarded reports have unexpected violations 0 and restoration/patch restoration/cleanup true. Python and storage coordinators pass with restoration/patch restoration/cleanup true and passing nested evidence contracts.
- Node: actual parser **7/7**, Phase 1 React renderer **9/9**, synthetic coordinator **9/9 PASS**. Registered entrypoints have unexpected violations 0 and restoration/patch restoration/cleanup true. Strong source text with leading/trailing spaces and an internal newline stays exact in canonical and compatibility output; existing `매**수**` rejection and source/candidate/result mutation cases still pass.
- Inventory unchanged: Python **90 modules / 676 direct** (35 / 605 / 22 baseline + 14 Stage 1), **18** separate child probes; Node **21 entrypoints / 172 direct**. Missing/duplicate/extra/dependency and expected-skip findings 0. One existing Node case was revised to the explicitly confirmed contract, with no new testcase IDs/counts; its source hash and exact fixture read allowlist were updated.
- This follow-up changes **10 files**: `backend/core/review_body_compiler.py`; `tests/test_ai_review_openai_client.py`, `tests/test_trade_review_structured.py`; `frontend/scripts/ai-review-format.test.js`, new `frontend/scripts/fixtures/review-compatibility-v1.json`; `tests/isolation_inventory.py`, `tests/test_inventory.json`; `docs/TESTING.md`, `docs/quick_verify.md`, this plan. Nine existing files differ from this follow-up's baseline plus one new synthetic fixture. Reconstructing only the three separator-related code edits in memory matches the starting compiler hash, including its original CRLF line endings; there is no other production change.
- Sealed-body serializer/finalizer/envelope compiler/display contract, source DTO/projection/admission/market producer code and tests, all frontend production files, main, runner and all other starting files are byte-identical to this follow-up's baseline. No route/history/cache/replay integration, other-worktree writes or prohibited Git actions.
- Branch/HEAD remain `feature/structured-trade-review` / `787a9d5683803003fe2c7bfe1e786f5874847462`. Final staged 0 / tracked unstaged 21 / untracked 20. Standard `git diff --check` and separate untracked whitespace checks pass. Source inventory was recomputed; counts were not increased. H4 synthetic/temp-only effects, Python 3.12.14 and Node 24.15.0 execution paths remain as documented below. Full TestOnly/BuildChecks, live provider/network, browser/CSS/device remain unrun.
- **Phase 2C is ready for independent review.** The previous newline conflict is resolved by the user's explicit contract decision. This is implementation/verification evidence, not independent approval. Phase 2D was not started. Report and wait.

## Canonical Display Phase 2C — 2026-10-03

### Scope and decisions

The user reports independent Phase 2B approval and authorizes compatibility serialization only in this worktree at `feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`. Initial staged 0, tracked unstaged 20, untracked 18. This supersedes historical approval holds below. Preserve source admission, DTOs, market data, routes, history/cache/replay and frontend production bytes. No Phase 2D or Git mutations.

- Compatibility serializer accepts only a canonical body document and emits its validated run text and owned separators exactly. It never reads semantics, raw output or legacy summary, interprets Markdown, trims, replaces or truncates text.
- Fallback display templates belong to the canonical body compiler, use admitted source facts and precede the same envelope safety/validation/sealing boundary. Semantic coverage and raw/decode/normalized safety checks remain before body approval. Returned summary and display body derive from the sealed bytes.
- Advanced normal sections use explicit blank-line boundaries because the existing frontend parser joins adjacent nonempty lines. Existing advanced fallback has single newlines: preserving its byte-exact legacy contract conflicts with separating its paragraphs under the unchanged parser. User clarification is pending; no existing exact-string expectation will be rewritten to bless a new output.

### Progress and verification plan

- [x] Confirmed actual root, branch, HEAD, worktrees and complete status; snapshotted all starting tracked/untracked file hashes in a task-owned temporary directory.
- [x] Read current implementations, plan, testing/inventory and actual frontend parser. Found fallback compiler substitution loses legacy headings/facts; the dormant advanced helper also references an undefined `summary` variable.
- [x] Implemented canonical templates and deterministic serializer, including fixed legacy exact regressions and strong/whitespace/mutation/safety counterexamples. The final advanced fallback paragraph-separation decision remains pending.
- [x] Ran only selected H4 OpenAI client, display/envelope, structured, safety/finalization, source/admission/market, React Phase 1, Python/Node coordinator, storage/docs tests and inventories. DB/cache/env writes must remain in test-owned temporary roots, provider/network mocked or blocked. No full TestOnly/BuildChecks.
- [x] Audited scope/hash preservation, inventory, Git status and diff whitespace; report results and Phase 2D readiness, then wait.


### Phase 2C candidate result and stop

- Cause: Phase 2B selected the general structured body for every fallback, losing the established recent-pattern/repeated-problem/loss-management/reflection template and its facts. Each advanced normal section used one newline, which the actual frontend parser joins into a paragraph. The unused advanced fallback helper additionally had an undefined `summary` reference; the canonical template now uses admitted objective win rate.
- Authority: `review_body_compiler` owns canonical template selection before approval. Both semantic coverage safety and the actual canonical envelope safety run before sealing. `serialize_compatibility_summary(document)` only calls body document validation/flattening: no semantic re-read, raw-summary fallback, Markdown reinterpretation, trimming/replacing/truncation or separate safety exception. Returned body and summary use the sealed snapshot's body.
- Basic normal: four sections with single newlines, legacy basic section/checklist parser preserved. Advanced normal: eight sections with explicit double newlines, parsed as eight paragraphs. Basic/advanced fallback: legacy facts, labels and original single-newline strings restored and frozen as literal expectations. The client safety fallback case now checks the original legacy literal rather than self-comparison with a substituted structured template. No old exact-string expectation was changed to a new output. Strong source text is compiled into canonical runs once; the compatibility output is their plain visible text.
- Results: Python 298/298 PASS in 20 explicitly selected modules; OpenAI client 16, display 14, envelope 26, structured 75, quality 3, source 32, admission 23, market 26, safety 17, finalization 2, transport 10, chart provider 1, journal chart 4, refund 13, history-consent 7, access 5, access concurrency 1, Python coordinator 14, storage coordinator 2, docs 7. All 18 guarded reports have unexpected violations 0 and restoration/patch restoration/cleanup true. Coordinators have restoration/patch restoration/cleanup true and passing nested evidence contracts.
- Node: React renderer 9/9, actual legacy parser 7/7, coordinator 9/9 PASS. Registered Node entrypoints report unexpected violations 0 and restoration/patch restoration/cleanup true. The new parser diagnostic intentionally demonstrates both the original fallback's one-paragraph merge and the four-paragraph double-newline alternative; it does not approve the merged UI.
- Earlier candidate checks exposed obsolete fallback-versus-generic-template assertions; those were replaced by fixed original fallback expectations and approved-body checks while retaining independent semantic coverage/safety assertions. A new loss/open fixture initially selected a different episode after a fresh buy; a partial exit now exercises loss and open facts within the existing episode policy. An intermediate coordinator run overlapped addition of one testcase before manifest synchronization and failed inventory validation; the final source/manifest and coordinator checks pass. These were different assertion/fixture/inventory causes, not a product source-admission failure.
- Actual inventory: Python 90 modules / 676 direct = baseline 35 / 605 / 22 + Stage 1 14; 18 child probes counted separately, not a claim all were executed. Node 21 entrypoints / 172 direct. Missing/duplicate/extra, missing dependencies and expected skips 0.
- Changed in this phase: production existing `backend/core/ai_review_v2.py`, `backend/core/review_display_contract.py`, `backend/core/review_envelope_compiler.py`, new `backend/core/review_body_compiler.py`; tests `tests/test_ai_review_openai_client.py`, `tests/test_review_display_contract.py`, `tests/test_trade_review_structured.py`, `tests/test_trade_review_refund.py`, `frontend/scripts/ai-review-format.test.js`; inventory/coordinator/docs `tests/isolation_inventory.py`, `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`, `tests/test_quick_verify_docs.py`, `docs/TESTING.md`, `docs/quick_verify.md`, this plan. Starting hashes show 15 existing files changed plus one new file. All other starting files are byte-identical; frontend production, source DTO/projection, market producers, main and runner are unchanged.
- Git: same branch/HEAD, staged 0, tracked unstaged 21, untracked 19. No staging/commit/push/reset/revert/stash, other-worktree write, route/response-envelope/history/cache/replay production connection or Phase 2D occurred. Tests use Python 3.12.14 (`D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`) and Node 24.15.0 (`C:\Program Files\nodejs\node.exe`); temporary logs/hash snapshots are task-owned. Full TestOnly/BuildChecks, live providers, browser/CSS/device remain unrun.
- **Stop / not complete:** the original advanced fallback exact string has single newlines, and the unchanged frontend parser necessarily merges them. A canonical double-newline fallback would break that exact contract. User clarification was requested and is still pending. Keep current original exact-string preservation as a provisional candidate; do not claim all Phase 2C goals met or Phase 2D ready. Independent review of the final chosen contract also remains required. Report and wait.

## Canonical Display Phase 2B-3 — 2026-10-03

### Approval and scope

Phase 2B-2 received independent approval. The prior stop at the end of its P1 correction record was the pre-approval handoff state; the user's explicit Phase 2B-3 authorization supersedes it. This step only fixes the Phase 2B source-admission/typed-compiler regression matrix and records source-based H4 evidence. It does not perform Phase 2C or connect a canonical envelope to routes/responses, history/cache/replay to production, frontend production surfaces, or renderer structure.

### Source-derived regression matrix

- Existing source/structured tests already cover normal, empty, explicit unavailable and fallback outcomes; invalid complete chart with otherwise valid model output; context unknown fields; partial/all `Close` NaN; low-confidence safety before fallback; objective injection; 20/21/200 episode windows; immutable DTO ownership after source mutation; candidate/snapshot mutation isolation; raw compiler input rejection; no prompt-payload raw recovery; provider fallback only for transport failure or genuine absence; and failure to reuse a prior strict provider result.
- Added three missing production-path regressions: invalid chart admission while both OpenAI API-key variables are empty remains terminal `error/none`; after a `ready` snapshot, a later invalid admission replaces that snapshot with the fixed terminal snapshot; a provider frame with the entire `Close` column missing is terminal for both daily and context builders.
- Existing market regressions keep normal FDR and single-symbol yfinance inputs `ready`, reject unknown columns and invalid/non-numeric provider values before projection/coercion, reject partial/all missing `Close` rows, and assert zero provider retry/fallback and zero model calls after admission failure. Context unknown-column and missing-close-row cases remain explicit.
- Typed compiler regressions retain the single `ValidatedReviewSource` parameter, reject raw/uninitialized inputs, assert DTO-owned inputs after prompt mutation, and verify sealed candidate/snapshot bytes remain unchanged after caller mutation. Source-to-envelope tests verify exact fixed error/unavailable output rather than raw recovery or a ready promotion.

### Focused verification and inventory

- Python source inventory, recomputed after the three added direct cases: **90 modules, 662 direct = baseline 35 / 591 / 22 + Stage 1 14; 18 child probes separate**. Missing/duplicate/expected skips: 0. Node inventory: **21 entrypoints / 169 direct**; missing/duplicate/extra/source-dependency findings: 0.
- Focused Python: **276/276 PASS across 20 explicit modules**: source contract/admission, envelope/display, structured review, market admission, journal chart detail, chart provider, quality, OpenAI client, safety/finalization, refund, history/consent and history storage boundaries, access regressions, Python coordinator, storage coordinator and docs regression. The 18 guarded module reports had unexpected violations 0 and restoration, patch restoration and cleanup true; storage coordinator nested fixture evidence was 4/4 PASS with restoration/cleanup true.
- Node coordinator regression: **9/9 PASS**. Registered `test:canonical-review-renderer`: **9/9 PASS** with cleanup/restoration/patch restoration true and unexpected violations 0.
- `git diff --check` and a separate trailing-whitespace scan of the touched untracked execution plan passed. No full TestOnly/BuildChecks, live provider/network, device or private/persistent DB check ran. Provider/model interactions were synthetic or mocked and H4-owned temporary state was cleaned.

### Changes and handoff

- This step changed only regression tests, source-derived inventory assertions/manifest and the testing/plan documents. No backend or frontend production file was changed in this step.
- Worktree remains `feature/structured-trade-review` at `787a9d5683803003fe2c7bfe1e786f5874847462`, staged 0. Existing changes are preserved; no other worktree or prohibited Git operation was involved.
- The source-shape HOLD can now be independently re-reviewed against the 2B-1 DTO contract, 2B-2 production admission/compiler path, the focused source matrix and current H4 reports. Phase 2B is ready for a complete independent review; this is not itself that review or a Phase 2C authorization.

## Phase 2B-2 P1 market admission-order correction — 2026-10-03

### Scope and current evidence

Independent verification found that daily/context admission followed the shared fetcher's lossy cleanup and sanitized TTL cache. The previous Phase 2B-2 readiness statement below is superseded by this finding. Correct only this P1 in the same worktree/branch/HEAD; no Phase 2B-3 work, other-worktree writes or prohibited Git operations.

- [x] Reconfirmed branch `feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`, staged 0, tracked unstaged 19 and untracked 17. Snapshotted the 36 existing working files plus the shared fetcher in a task-owned host temporary directory.
- [x] Traced daily and context inputs through shared `get_stock_ohlcv` cleanup/cache. Other callers keep that API and its existing behavior.
- [x] Add an uncached AI-only fetch boundary: admit every provider result before column projection, row deletion, coercion, date normalization or provider fallback. Source errors must escape provider transport-error handling.
- [x] Connect daily and context producers, preserve the approved DTO/compiler/finalizer and existing objective/window/safety/refund policies, and test invalid/valid sources plus sanitized-cache counterexamples.
- [x] Recompute Python inventory from source, run only explicit H4 focused modules/coordinator/inventory and `git diff --check`, verify preservation against this correction's starting bytes, report and wait. No live provider/device, full TestOnly or BuildChecks.

### Correction result and evidence

- Production boundary: `data_fetcher.get_review_stock_ohlcv` receives each FDR/yfinance raw return and invokes `_admit_review_ohlcv` outside the transport-exception fallback handler. Complete column/symbol/index/numeric/OHLC checks run before `copy`, column projection and daily index normalization. Invalid rows are never dropped or coerced. Source rejection propagates immediately; only transport errors or a genuinely empty admitted sample may select another provider.
- Both AI daily `_daily_data(review_source=True)` and `_contexts_for_trades` call this strict fetch; ordinary journal/stock callers retain the original cached `get_stock_ohlcv`. The AI intraday branch also reuses the same raw validator before flattening/renaming columns. All raw frame values are checked, including rows later excluded by chart/prompt windows. FDR's explicit optional numeric Change metadata permits its documented first pct_change NaN; yfinance's exact single-requested-symbol MultiIndex is validated before projection. Unknown metadata/columns remain terminal.
- Strict cache policy: no application OHLCV cache reads or writes and no strict-result cache. Counterexamples populate the ordinary TTL cache with a frame sanitized from an unknown provider column, confirm a legacy cache hit, then show both strict daily/context paths still fetch and reject the raw source. A prior successful strict result cannot hide a later invalid one. The ordinary cached function, including its decorator, is AST-identical to this correction's baseline.
- New market tests 25/25 plus existing admission tests 21/21 PASS through both production basic/advanced builders and sealed snapshots. Unknown columns and partial/all Close NaN: first FDR call 1, later provider fallback/retry 0, model calls 0 for each invocation. If a valid empty FDR sample precedes invalid yfinance, only KS is called once; KQ/retry/model remain 0 after that failure. Invalid input reaches the existing sticky fixed `error`/`none` unavailable snapshot, with no market/objective/trade/chart promotion. Normal FDR OHLCV, declared Change metadata and single-symbol yfinance remain `ready`/`openai`; genuine absence and transport fallback preserve prior behavior.
- Focused H4 latest direct results: 271/271 across 19 explicit modules. Market admission 25; source admission 21; source contract 32; display 9; envelope 26; structured/objective/fallback 66; quality 3; OpenAI client 16; journal 4; chart provider 1; refund 13; safety 17; safety finalization 2; history-consent compatibility 7; access 5; access concurrency 1; Python coordinator 14; storage coordinator 2; docs 7. The 17 guarded children have unexpected violations 0 and restoration/patch restoration/cleanup true. Both coordinators passed their nested-evidence contracts with restoration/cleanup true; their top-level report has no unexpected counter. No full TestOnly/BuildChecks, live-provider/device or Node execution ran.
- Recomputed source inventory: 90 Python modules, 659 direct = baseline 35 / 588 / 22 plus Stage 1 14; 18 separate child probes are inventory, not an assertion that all probes executed. Python missing/duplicates/expected skips 0. Read-only Node inventory remains 21 entrypoints / 169 direct; missing/duplicates/extra 0.
- Approved source contract, all 28 DTO protections, compiler, projection, contract tests, main and frontend remain byte-identical to this correction's starting files. Existing full-episode objective, 20-trade prompt/display, raw/decode/normalized safety and refund/billing policy tests pass. No DTO/compiler/finalizer redesign, route/history/cache/replay envelope integration or Phase 2B-3 work occurred.
- Correction changes exactly 13 files: production `backend/core/data_fetcher.py`, `backend/core/journal_chart.py`, `backend/core/ai_review_v2.py`; tests new `tests/test_review_market_source_admission.py`, existing `tests/test_review_source_admission.py`, `tests/test_ai_review_chart_provider.py`; inventory/coordinator `tests/isolation_inventory.py`, `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`; docs `docs/TESTING.md`, `docs/quick_verify.md`, this plan. Other 25 baseline files remain byte-identical. Git remains staged 0, tracked unstaged 20, untracked 18 at the requested branch/HEAD. No other worktree was modified and no prohibited Git action ran.
- Verification uses the previously approved absolute Python 3.12.14 runtime with `-I -X utf8 -B tests/run_isolated_tests.py` and explicit focused modules / `--inventory-only` / `--node-inventory-only`. Synthetic provider/model calls are patched; database/cache/environment writes stay under H4-owned temporary roots, cleanup verified. Logs and starting byte snapshots live in a task-owned host temporary directory. Standard `git diff --check` passed; all 18 untracked source/test/document files passed the separate whitespace scan. Starting-byte preservation audit passed: exactly the 12 existing correction files changed, with the new market test as file 13; the other 25 baseline files are unchanged.

### Stop / remaining

Only the reported P1 correction and focused verification are complete. Independent revalidation is pending. Do not proceed to Phase 2B-3; report the correction and wait for the user. Full TestOnly/BuildChecks and live provider/device checks remain unexecuted by explicit scope.

## Canonical Display Phase 2B-2 — 2026-10-02

### Goal and scope

Connect the approved 2B-1 source DTOs to production AI review inputs, objective/quality/fallback/structured producers and the finalizer. The compiler accepts one admitted DTO only. Worktree, branch and HEAD match the user's request (`feature/structured-trade-review`, `787a9d5683803003fe2c7bfe1e786f5874847462`). Preserve all initial 16 tracked unstaged and 14 untracked files; staged 0. The user's independent approval supersedes the 2B-1 review gate for that contract.

### Decisions

- Admit the complete trade input before episode selection and prompt/display windows. Admit complete journal charts and contexts before any lossy selection or quality/fallback substitution.
- Preserve full-episode objective calculations, the existing 20-trade prompt/display window and chart window policy. Keep raw/decoded/normalized semantic safety decisions before low-confidence replacement.
- Source rejection is terminal: no model/provider retry and only a fixed error/unavailable DTO may reach the snapshot. Empty, unavailable chart and model-fallback have explicit variants.
- Keep the approved 28 DTO protections. No route envelope, history/cache/replay, frontend production, refund/billing policy or other-worktree changes.

### Current status and verification

- [x] Verified repository identity and full initial status; read the current contracts, producers, finalizer, H4 coordinator and prior plan. Saved initial file bytes/hashes in a task-owned host temporary directory for preservation checks.
- [x] Both builders admit every raw trade before target/episode selection and the 20-trade prompt window. Objective calculation consumes the full admitted episode, admits its calculated result and supplies quality, fallback, structured and compiler producers through a single `ValidatedReviewSource`.
- [x] AI journal charts require admitted trades. The AI-only market preparation rejects incomplete/unknown columns, invalid numeric rows and invalid time indexes before local coercion/dropna/resampling. Intraday source failures propagate without trying the alternate exchange or daily provider. Every full journal chart/candle/marker/fill/observation is admitted before first-chart selection, compact field projection or candle windowing. Context producer results are admitted before quality/prompt use; raw context tuples are rejected while tuples of admitted DTOs are supported.
- [x] Compiler signature is `compile_review_envelope(source: ValidatedReviewSource)`. It builds body and named display surfaces from DTO attributes, with no raw source recovery, field defaults, arbitrary source-dictionary walk or incomplete-candle filtering. Unsaved/name-only trade display eligibility is applied only after full admission; unavailable chart/objective are explicit variants.
- [x] Source failure skips model parsing and both default semantic producers and reaches only the fixed `error`/`none` unavailable DTO, with neutral objective and no rejected text/charts/trades. Model safety or invalid model semantics remains an error through typed fallback. Empty is `empty`/`none`; missing-key and model-output/provider failure use admitted basic/advanced semantics with `missing_key` or `error`/`chart-rules`. Valid fallback-model output keeps the existing `ready`/`openai` behavior.
- [x] Added 21 H4 admission cases, including late/idless/name-only trades, fields/candles lost by the old compact transform, second charts, marker fill metadata, context producer output, market coercion, no source retry, default bypass, compiler admission, payload mutation isolation, explicit variants and real synthetic DataFrame chart/context producers. Updated old shorthand test fixtures only in tests. The old OpenAI client comparison to an independently assembled fallback summary now checks the actual canonical structured document; client 16/16 passes.
- [x] All 28 DTO class definitions are AST-identical to the initial 2B-1 source. Original source contract tests remain byte-identical and pass 32/32, including construction/state-restore/pickle protection.
- [x] Recomputed inventory: Python 634 direct = baseline 35 / 563 / 22 plus Stage 1 14, 18 child probes (inventory only); 89 Python modules. Node 21 entrypoints / 169 direct. Missing/duplicate/extra entries and unexpected skips 0.
- [x] Focused latest results: 246/246 Python direct across 18 selected modules. Source 32, display 9, envelope 26, admission 21, structured 66, quality 3, OpenAI client 16, journal chart 4, refund 13, chart provider 1, safety finalization 2, safety 17, history-consent compatibility 7, review access 5, concurrency 1, Python coordinator 14, storage coordinator 2, docs 7. Node coordinator regressions 9/9 and existing React renderer 9/9. Guarded direct children report unexpected violations 0, successful restoration/patch restoration/cleanup; coordinator nested evidence contracts pass. This is not a full TestOnly or a claim that all 18 inventory probes were run.
- [x] Standard `git diff --check` passes, including separate whitespace checks of untracked source/test/plan files. A transient check with autocrlf disabled misclassified CRLF as trailing whitespace; the standard configured check is authoritative and no Git config was changed. New normal-market fixture initially expected the full 30 candles; source inspection confirmed the unchanged last-marker window is the preceding 25 plus the marker (26), and the corrected policy check passes.
- [x] Initial 30 working files were byte-snapshotted; 15 outside the step's changes remain byte-identical, including main, all frontend files, both approved display/envelope contracts, source contract tests and the Python runner. Final Git status is staged 0, tracked unstaged 19, untracked 17, same branch/HEAD. No other worktree was modified and no prohibited Git action was performed.

### Verification commands and effects

Run in this worktree on 2026-10-02 with `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe` 3.12.14 and `C:\Program Files\nodejs\node.exe` 24.15.0. Python invocations use `-I -X utf8 -B tests/run_isolated_tests.py` with explicit selected modules, `--inventory-only`, `--node-inventory-only`, `--node-regressions --node-executable <node>` and `--node-entrypoint test:canonical-review-renderer --node-executable <node>`. These were source reads or H4 synthetic checks; DB/cache/environment/process writes were confined to test-owned temporary roots, external requests mocked, cleanup verified. Logs and baseline copies are task-owned host temporary files. No install, full `--all`/`--node-all`, TestOnly, BuildChecks, device or live-provider execution occurred.

### Files changed in this step (21)

- Production (5): `backend/core/ai_review_v2.py`, `backend/core/journal_chart.py`, `backend/core/review_source_contract.py`, `backend/core/review_envelope_compiler.py`, new `backend/core/review_source_projection.py`.
- Tests (9): new `tests/review_source_fixtures.py`, new `tests/test_review_source_admission.py`, `tests/test_ai_review_chart_provider.py`, `tests/test_ai_review_openai_client.py`, `tests/test_ai_review_quality.py`, `tests/test_ai_review_safety_finalization.py`, `tests/test_main_ai_review_history_consent.py`, `tests/test_trade_review_structured.py`, `tests/test_trade_review_refund.py`.
- Inventory/coordinator (4): `tests/isolation_inventory.py`, `tests/test_inventory.json`, `tests/test_full_test_entrypoint.py`, `tests/test_storage_fixture_runner.py`.
- Documents (3): `docs/TESTING.md`, `docs/quick_verify.md`, this plan.

### Remaining / unverified and next step

Phase 2B-2 implementation and focused validation are complete; it is ready to enter Phase 2B-3 independent verification, which was not performed in this step. Independent approval remains pending. Full TestOnly/BuildChecks, production/network providers, device, route/history/cache/replay and frontend production integration are outside scope. Stop here and await the user's next instruction.

## Canonical Display Phase 2B-1 — 2026-09-29

### Goal and scope

Establish strict, immutable source admission before the future compiler receives trade, objective, chart, context, or semantic values. This is a contract and H4 unit-test step in the existing `structured-trade-review` worktree at `feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`. The prior 2B HOLD and all pre-existing working changes remain. Do not connect production builders, finalizer, compiler, route, history/cache/replay, or frontend in this step.

### Decisions

- `review_source_contract.py` exposes factory-only frozen DTOs. Full episode trades and complete chart and semantic lists are admitted before later display selection or the existing semantic array limits. Raw objects/lists require exact builtin `dict`/`list` types and exact declared key sets. Numbers are finite and retain their type; nullable values require present keys with `None`.
- Trade variants are basic, identified, and stored; ticker identity is either a six-digit KRX code or explicit `name_only` DTO state. Objective has exact symbol/period/full-result objects plus an explicit `no_trades` variant. Compact chart has eight exact fields plus an explicit unavailable variant; candle, marker buy/sell tooltip, technical metrics, and data-unavailable observation shapes are distinct. Analysis context normal/error DTOs remain analysis input only.
- Semantic admission checks the complete raw model/fallback shape, applies only existing `trade_review_schema` trim, bound, and label mapping, validates the normalized schema again, and constructs the same basic/advanced DTOs for both sources. It does not change the production finalizer.
- The current producer's `{}` chart absence and empty-candle legacy source are *not* accepted as available charts. Phase 2B-2 must emit an explicit unavailable variant and connect these factories before compiler projection. This preserves the structural HOLD until the producer/connection work is reviewed.

### Current status and verification

- [x] Confirmed root, branch, HEAD, worktree list, staged 0, tracked unstaged 16, and untracked 12 before edits. Read the prior plan and current source producers/contracts. The new narrower 2B-1 request supersedes the prior plan's production connection goal for this step.
- [x] Added source contract/factories and 32 direct unit cases. DTO discovery starts from every `_FactoryOnly` subclass before checking dataclass protection; a synthetic undecorated subclass proves it cannot escape coverage. `candles=""`, numeric observation/semantic title/detail, invalid ID-less trade after the display window, metrics subsets, and source mutation counterexamples fail admission. Valid trade/chart/marker/semantic/unavailable variants pass.
- [x] H4 targeted runs: new source 32/32, Phase 1 display 9/9, Phase 2A envelope 26/26, Python coordinator 14/14, storage coordinator 2/2, docs 7/7, actual React renderer 9/9, and Node coordinator regressions 9/9. Initial coordinator/docs run exposed stale inventory numbers; both current docs and the coordinator's source-count assertion were corrected and rerun successfully. Guarded direct children reported zero unexpected violations and cleanup/restoration true.
- [x] Source inventory recomputed: Python 613 direct = baseline 35 / 542 / 22 plus Stage 1 14, child probes 18; Node 21 entrypoints / 169 direct. Missing, duplicate, and extra inventory entries 0.
- [x] Independent finding fixed: every module-local dataclass DTO is created through one `_source_dto` decorator that replaces the generated `__setstate__` with a rejecting method. A source-enumerated regression covers all 28 DTOs, direct constructors, uninitialized `__new__` instances, and crafted pickle BUILD state. Factory-created DTOs and source-mutation isolation still pass.
- [x] `git diff --check` passed; the new untracked source, tests, and plan have no trailing whitespace. Staged files remain 0, branch/HEAD remain unchanged, and no other worktree was modified.

### Remaining / unverified

No full TestOnly/BuildChecks, provider/network, persistent DB, device, or external validation ran. The current production 2B candidate remains HOLD, including its source-shape bypass and the separate 15/16 OpenAI client compatibility regression. Phase 2B-2 may start with producer adaptation and a single compiler admission boundary, then must repeat targeted H4 checks and obtain the independent review required for production connection. Phase 2C remains on hold.

### Next step

In a separately authorized Phase 2B-2, make producers emit these exact source variants, change the compiler to accept `ValidatedReviewSource` only, and connect both builders/finalizer without changing route/refund contracts. Review the complete source-to-envelope path and its H4 evidence before approval.

## Canonical Display Phase 2B — 2026-09-29

### Goal and scope

Connect both production `ai_review_v2` builders and their shared finalizer to the closed `review-envelope.v1` compiler, validator, and `ApprovedReviewSnapshot`. Preserve the existing route response/refund status contract without connecting the sealed snapshot to route, history, cache, or frontend consumers. Work only in `structured-trade-review` on `feature/structured-trade-review` at HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`; initial staged 0 and all prior Stage A/Phase 1/Phase 2 HOLD/Phase 2A changes unstaged or untracked. Do not change another worktree or Git history.

### Decisions

- Compile ordered `trade-review.v1` body through the approved Phase 1 compiler. Project only declared chart display sinks and typed objective/chart/trade fields into the Phase 2A envelope; internal chart contexts have no outbound surface.
- Keep raw/decoded/normalized semantic safety before low-confidence substitution and keep safety rejection sticky. Every result path, including missing key, malformed output, fallback, and empty input, must pass one envelope validator and sealed snapshot construction.
- The snapshot remains an internal finalizer artifact in this phase. The current legacy route/history/cache/frontend consumers are not switched to it. Old Phase 2 HOLD frontend projection and arbitrary response-dict safety checks must not serve as approval.

### Current status

- [x] Confirmed root, branch, HEAD, all worktrees, and full initial status; request matches checkout. Read the Phase 2A contract and Phase 2 HOLD plan; the latter's route/history scope is superseded by the narrower 2B request.
- [x] Attempted the finalizer/builder connection, including empty and fallback paths. The current candidate is **HOLD**, not approved production behavior.
- [x] Added production-builder regressions and recalculated source inventory: Python 581 direct = baseline 35 / 510 / 22 plus Stage 1 14, child probes 18; Node 21 entrypoints / 169 direct. Inventory missing/duplicate/extra 0.
- [x] Ran targeted H4 and static checks listed below. Full TestOnly/BuildChecks were not run.

### Verification and HOLD — 2026-09-29

- H4 targeted PASS: Phase 1 display 9/9, Phase 2A envelope 26/26, structured/finalizer 66/66 (before a testcase-only rename), refund 13/13, history/consent 7/7, safety finalization 2/2, safety 17/17, Python coordinator 14/14, storage coordinator 2/2, docs 7/7. Guarded children reported violations/unexpected 0 and restoration/cleanup true. React renderer 9/9 and Node coordinator regressions 9/9 passed; Node inventory is 21/169.
- OpenAI client H4 target had 15/16 pass and the already documented Phase 2 HOLD fallback-summary equality failure. Compatibility summary newline work is excluded from Phase 2B.
- `git diff --check` passed. `backend/main.py` and the React renderer file hashes match their initial values. Staged files remain 0; branch and HEAD did not change; other worktrees were not modified.
- **New structural HOLD:** `review_envelope_compiler.py` uses truthiness to replace source values such as `metrics=""`, `candles=""`, `trade_markers=""`, or `rule_based_observations=""` with empty dict/list values (lines 100, 191, 195–196). It also formats a non-string chart title/detail into a string before the display validator sees its source type (line 106). Therefore unknown/unmapped source strings and types can avoid rejection even though the final envelope schema is closed. This was found by static review after the passing H4 cases; no dynamic reproduction or correction was made. Per the user's structural stop rule, no field-by-field exceptions were added.
- The attempted 2B finalizer leaves `history_state["approved"]` unset. Route/history/cache/frontend production code was not changed, but current route calls would defer history saving; the focused tests now state this temporary boundary. This is not approval to deploy the candidate.

### Remaining / unverified

The source-shape bypass must be resolved with a single strict source validation design and independently reviewed before Phase 2B can be approved. Full TestOnly, browser/CSS, device/external validation, route/history/cache/frontend migration, compatibility summary newline work, and billing policy are outside this phase.

### Next step

Hold Phase 2C. Review and redesign the compiler's source-shape admission atomically, then repeat the targeted H4 checks and obtain independent review in a separately authorized continuation.

## Canonical Display Phase 2A — 2026-09-28

### Goal and scope

Build only the closed `review-display.v1` surface set, strict `review-envelope.v1` outbound schema/validator, and sealed `ApprovedReviewSnapshot`. Keep the existing Phase 2 production finalizer, route, history, cache, React renderer, and chart UI untouched. This follows the Phase 2 HOLD below; its production findings remain unresolved by this foundation alone. Worktree `structured-trade-review`, branch `feature/structured-trade-review`, HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`; start status staged 0 with prior Stage A/Phase 1/Phase 2 tracked and untracked changes. No other worktree or Git history changes.

### Decisions

- Actual current review output sinks require `body`, `chart_card`, `chart_header`, `chart_tab`, `marker_label`, `marker_tooltip`, `history_title`, `trade_name`, and `notice`. `trade_memo` is an input field in the current UI, not a review output sink, so the envelope has no raw memo slot.
- Phase 1 body validation remains the default. The envelope names the expected surface at each position and rejects an otherwise valid document placed elsewhere.
- The new envelope has explicit top-level and nested objects for body, typed objective values, chart cards and metrics, chart candles and markers, trades, history, and notice. It permits no `structured_review`, raw summary, chart title/detail, or arbitrary context text. Card metrics require all five named keys, with null for unavailable values. Codes are six-digit KRX tickers; dates are calendar checked; datetime values include an explicit offset with hour 0–23 and minute 0–59; IDs are positive safe integers; all numbers are finite.
- Snapshot construction validates source, serializes to sorted UTF-8 JSON with `allow_nan=False`, validates the independent parsed JSON again, and retains only independent immutable bytes. The digest is computed from those validated bytes. State restoration and pickling reject; no mutable content accessor or `approved` flag grants admission.

### Current status and verification

- [x] Reconciled the current worktree and Phase 2 HOLD; read current UI sinks and H4 boundaries.
- [x] Added the Phase 2A contract module and independent fixed contract fixtures; registered 14 initial and 12 independent-finding regression H4 Python cases.
- [x] Current source inventory: Python 571 direct = baseline 35 / 500 / 22 plus Stage 1 14, child probes 18; Node 21 entrypoints / 169 direct. Missing and duplicate counts zero.
- [x] Initial focused H4 runs: 14/14 new envelope cases, 9/9 Phase 1 Python display cases, 9/9 actual React renderer cases. Python coordinator regression 14/14, storage fixture coordinator 2/2, documentation cases 7/7, and Node coordinator regression 9/9 passed. Test children reported restoration and cleanup true; guarded contract children reported zero unexpected violations.
- [x] Final focused rerun after serialization race and default-body hardening: envelope 14/14 and Phase 1 Python 9/9 passed. `git diff --check` exited 0; new untracked source had no trailing whitespace. Final status audit retained the original staged/unstaged classification.
- [x] Independent-finding correction rerun: envelope 26/26, Phase 1 Python display 9/9, real React renderer 9/9, Python coordinator 14/14, storage coordinator 2/2, documentation 7/7, Node coordinator 9/9. H4 contract children reported zero unexpected violations and successful restoration/cleanup. `git diff --check` exited 0, untracked correction files had no trailing whitespace, and the final status remained staged 0 on the original branch/HEAD.

### Remaining / next step

Phase 2B may connect a builder only after the current Phase 2 production HOLD paths are addressed using this closed envelope. No full TestOnly, BuildChecks, browser/CSS, device, external service, or production integration was part of Phase 2A.

## Canonical Display Phase 2 — 2026-09-28

### Goal and scope

Connect the production backend review finalizer to `review-display.v1`. Approve one canonical body and canonical chart/context text before returning, saving history, or caching a response. Preserve the existing frontend production path and all Stage A/Phase 1 work. Work only in this worktree on `feature/structured-trade-review` at HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`; initial status is staged 0, tracked unstaged 15, untracked 9. No staging, commit, push, reset, revert, stash, external provider, persistent DB, or other-worktree change.

### Decisions

- Use the Phase 1 closed document contract for the body and every newly prepared chart/context text surface. `summary` is the body's exact `canonical_text` for Phase 3 compatibility.
- Explicit template paths cover every `trade-review.v1` semantic field. Unmapped display fields fail closed. User-supplied labels and memo stay literal.
- Decide raw, decoded, and normalized semantic safety before low-confidence substitution; a safety rejection remains `error` through fallback and route refund.
- Build response and history candidates, then validate their leaves, canonical text, exact flatten, shape, and envelope before approving deep copies. The route may append access and history ID metadata only.
- Adapt old history in memory on read; retain the original DB and show a fixed unavailable representation for unsafe records.

### Current status

- [x] Confirmed root, branch, HEAD, all worktrees, and initial full status; request matches the checkout.
- [x] Inspected finalizer, route, history storage, chart payload, Phase 1 contract, H4 instructions, and existing regressions.
- [x] Implemented an attempted compiler/finalizer connection, chart/context surfaces, history adapter, and removal of frontend projection code. This implementation is **not approved** because of the HOLD findings below.
- [x] Added production builder/route regressions and updated Python H4 inventory and docs. Current inventory: 545 direct Python cases and 18 child probes; 21 Node entrypoints and 169 cases; no inventory gaps or duplicates.
- [x] Ran focused Python H4 checks and full Node H4 (169/169 passed). Full Python H4 passed 544/545 direct cases and 18/18 probes; one old `test_ai_review_openai_client` assertion still expects the previous independently assembled fallback summary. H4 reported zero unexpected violations and successful restoration, patch restoration, and cleanup.
- [x] Independent read-only review returned **HOLD**: unknown nested chart/context/trade text can remain in a ready response outside a canonical document, and a legacy history record with a valid body snapshot can return split unsafe chart title/detail without canonical composition. The current advanced summary also collapses section lines in the old frontend parser. These are static findings; no dynamic reproduction was run for them.

### Remaining / next step

Stop implementation under the user's Phase 2 structural stop rule and report the HOLD. Phase 3 is blocked. No implementation changes were made after the independent review findings. Browser/CSS and frontend production integration remain separate gates.

## Canonical Display Phase 1 — 2026-09-28

Scope: define a closed `review-display.v1` representation, compile and validate it in a pure backend module, and run the actual new React renderer against fixed shared vectors inside H4. This phase does not connect production AI, journal, chart, or route display paths. All Stage A changes below remain in place.

### Contract and decisions

- Document keys are exactly `schema_version`, `surface`, `blocks`, `canonical_text`; version is `review-display.v1` and this phase accepts only `body`.
- Each block has exactly `type`, `runs`, `separator_after`. Types are `heading`, `paragraph`, `list_item`, `divider`. Each run has exactly `type` and `text`; types are `text` and `strong`. A divider has one visible text run. List numbering, punctuation, and other visible content are explicit runs. The separator is explicit space/tab/newline text, including any trailing newline.
- Limits: 1–64 blocks, 1–64 runs per block, at most 512 runs and 16,384 visible Unicode code points total; each run is at most 4,096 code points and each separator at most 16. The structure has fixed depth (document → blocks → runs). Unknown fields/types/versions, control characters, lone surrogates, and canonical mismatches reject.
- Inline parsing accepts only nonnested `**text**` pairs with nonempty content and no edge whitespace. Unclosed, nested, single-asterisk, link, code, or underscore markup leaves the entire input literal. The compiler never trims or normalizes Unicode.
- The frontend component uses React `createElement` in `.js` so the same production component can be imported directly by native Node H4 without a JSX transpiler. It renders runs in order, wraps only strong text in `<strong>`, and returns a fixed unavailable message for invalid documents. Its `pre-wrap` container preserves explicit whitespace. No production display caller imports it yet.
- The Node coordinator verifies hashes of the component, shared JSON vector, and the nine required installed React 19.2.6 files against the inventory and lockfile. It copies those bytes from the local installation into the H4-owned temporary tree; the guarded child has no read access to the main checkout. No install or network request is needed.

### Progress and evidence

- [x] Fixed shared vectors cover mid-word and normal bold, plain text, multiple strong spans, incomplete and unsupported markup, whitespace/newlines, block order and explicit separators, HTML-like text, unknown version/block/run/field, and canonical mismatch.
- [x] New pure backend compiler, exact flatten/validation, and nine H4 Python tests.
- [x] New actual React component and nine H4 Node server-render tests that extract the logical text sequence and strong elements from React output.
- [x] Python source inventory 536 direct (baseline 522 = 35 foundation, 465 migrated, 22 OUT; Stage 1 14), 18 probes, zero missing/duplicate/skip. Node source inventory 21 entrypoints / 169 direct, zero missing/duplicate/extra/source dependency.
- [x] Initial target runs: backend contract 9/9 PASS and actual React renderer 9/9 PASS; H4 restoration, patch restoration, and cleanup true. Node coordinator regression 9/9, documentation test 7/7, storage fixture coordinator 2/2 PASS.
- [x] Final rerun: Python contract 9/9, actual React renderer 9/9, Python coordinator 14/14 PASS. H4 restoration, patch restoration, and cleanup true; target children reported zero unexpected violations. Python and Node inventory reruns remained 536 and 21/169 with no missing/duplicate/extra cases. `git diff --check` PASS; untracked Phase 1 source files had no trailing whitespace.

The first Python coordinator run had one stale expected baseline count (513 versus the new 522 after adding nine contract cases). That assertion was updated; the final 14/14 rerun passed. The Node H4 coordinator regression passed 9/9 with tampered vector, component, and React snapshot hashes rejected before launch. No files were staged or committed, and no other worktree was modified.

React server rendering checks element order and exact logical text, including `<strong>`. A real browser DOM, CSS cascade/layout, and device behavior are not exercised by this phase; there is no installed browser test harness in the frontend package. Full TestOnly and BuildChecks remain unrun by request.

Phase 2 may start as a separate authorized implementation scope using this contract foundation. No production path was switched during Phase 1.

## Stage A record (historical)

## Stage A Goal

Add the `trade-review.v1` backend contract and isolated Python/H4 coverage while preserving legacy summary and safety fallback behavior.

## Stage A Scope

- Worktree: `D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`; branch `feature/structured-trade-review`; starting HEAD `787a9d5683803003fe2c7bfe1e786f5874847462`.
- Stage A changes cover the backend schema/review path, the minimum route history boundary, relevant Python/H4 regressions, and this plan. Frontend and Node remain read-only/out of scope.
- Read `D:\Project\Vibe\StockBoda-broker-import` only for the requested implementation. Do not access `backend/data` or `event_log.sqlite3` contents.

## Decisions

- AI output supplies qualitative fields only. The backend owns objective trade calculations and data confidence.
- Strict JSON Schema requests remain inside the existing Responses API call and safety boundary.
- Invalid or unsafe model output uses deterministic structured content and the existing legacy fallback summary. Failed model output reports `error` for the existing refund path; absent API key remains `missing_key`.
- A common finalizer owns raw/decoded safety, normalized structured tree validation, canonical display composition, the actual legacy summary, and the ready/error decision for both builders.
- The current main test module declares 16 testcases, despite the request's reference to six. Keep all 16.
- This plan follows the explicit requested path, although the repository plan guide normally uses `docs/exec-plans/active/`.

## Current Status

- [x] Confirmed worktree root, branch, HEAD, linked worktrees, and initially clean Git status.
- [x] Inspected current implementation, H4 inventory, and only relevant reference files/diff.
- [x] Implemented backend contract and scoped tests; preserved all 16 existing OpenAI client cases.
- [x] Registered the current structured (33) and refund (10) cases under the existing H4 migrated classification and storage module import gate.
- [x] Ran targeted H4, inventory, transport, and coordinator regression checks.
- [x] Resolved the four 2026-09-27 independent review HOLD findings with focused backend changes and H4 regressions.
- [x] Resolved the second revalidation's composed-summary safety and stale-plan findings; its historical Python direct inventory was 490.
- [x] Implemented the shared finalization boundary and focused root-cause regressions; current Python direct inventory is 507.
- [x] Implemented the 2026-09-28 full-response-envelope boundary, pre-default normalized semantic decision, preapproved history snapshot, and legacy read-time compatibility validation; current Python direct inventory is 527.

## Independent Review HOLD History

2026-09-27 independent Stage A review identified four findings against the uncommitted Stage A diff:

1. P1: Raw JSON safety filtering can miss a prohibited phrase encoded with `\u` escapes after JSON parsing.
2. P1: The prompt's last-20-trade window is reused for backend objective calculations, omitting earlier fills in a longer episode.
3. P1: Malformed or schema-invalid AI output returns a degraded fallback with `missing_key`, so the route's existing `status == "error"` refund path does not run.
4. P2: A valid advanced structured output loses detailed analysis, lesson, and playbook content when converted to the legacy summary string.

These findings put the Stage A result on HOLD until focused fixes and H4 regressions pass. The 2026-09-26 results below remain historical evidence for the earlier diff, not verification of the fixes.

The 2026-09-27 correction keeps raw-response filtering and scans decoded JSON string values before normalization. It computes objective data from the full selected episode while sending at most 20 trades in either prompt trade list. An AI response that fails safety or structural validation returns the established `error` status, so the route's existing single refund path runs; a missing key keeps `missing_key`. The advanced legacy summary now includes the structured entry, risk, exit, detailed analysis, playbook, lesson, and reflection content. No `main.py` change was required.

The second 2026-09-27 Stage A revalidation found that two individually safe fields could form prohibited advice after legacy summary composition, and that this plan still described two test modules and nine new cases as current. The correction checks the final composed summary with the existing safety policy. A rejection discards model semantics, rebuilds deterministic structured fallback, returns the existing fallback summary with `error` and `safety_rejected`, and uses the unchanged route refund path. The older HOLD findings and verification records below remain historical evidence.

The subsequent root-cause diagnosis identified the missing common authority between intermediate checks and the final returned representations. Both builders now return the result of one finalizer without later model-content rewriting. It retains raw and decoded checks, validates every model text leaf in the normalized and defaulted final structured tree with bounded traversal, checks canonical card/assessment/list/section/document compositions, and checks the exact legacy summary returned by the API. Unsupported structure or traversal limits reject ready. Unsafe output discards all model semantics and uses the existing fallback; an unsafe fallback terminates with a fixed model-free safe response. Refund remains exclusively in the route's existing single-refund path. Earlier HOLD findings and their dated results remain history.

The 2026-09-28 independent diagnosis found that low-confidence substitution could hide unsafe normalized semantics, response extras were merged after final safety, and history generated fresh chart content after finalization. This round checks normalized semantics before substitution, then validates the assembled response and optional history candidate as a single user-visible envelope. Chart/context/provider/trade strings and the current UI text projections are inspected; objective numeric data is excluded from text filtering. Rejection remains an error even when fallback text is safe. Storage opt-in is checked before history chart construction; the finalizer approves a deep-copied history candidate, and the save helper only persists that approval. Existing history is checked at read time without a DB migration or row mutation. The earlier HOLD findings and their dated evidence remain historical records below.

## Verification

2026-09-28, full-response-envelope correction against the same uncommitted Stage A worktree:

- Source inventory: OpenAI client 16, structured review 48, refund route 13, history/consent 6; Python direct 527 = baseline 513 (35 A1/foundation/helper, 456 migrated, 22 OUT) + Stage 1 14. This round added 20 direct cases (structured 15, refund 3, history/consent 2). Manifest missing/duplicate/extra 0, child probes 18, expected skips 0.
- H4 PASS: OpenAI client 16/16, structured 48/48, refund 13/13, history/consent 6/6, safety finalization 2/2, AI safety 17/17, OpenAI transport 10/10, chart provider 1/1, review access 5/5, access persistence 4/4, review history store 2/2, data routes 3/3, journal query limits 5/5, full-test entrypoint coordinator 14/14, storage fixture coordinator 2/2. Guarded modules reported violations/unexpected 0, and all reported restoration, patch restoration, and cleanup true. Coordinators passed with restoration and cleanup true.
- Low-confidence basic and advanced outputs with advice created only by normalization/truncation returned `error/safety_rejected`, with no unsafe text in the safe fallback. Safe low-confidence output retained the existing default-semantic policy. Existing Unicode/mixed escapes, split fields, 20/21/200 fill objective, schema-invalid/malformed fallback, and detailed legacy summary cases remained passing.
- Earlier, middle, and last unsafe chart observations; malformed AI plus unsafe chart; nested context trade text; a summary-only final sink; an extra chart-review field; unsafe user-supplied symbol names; and advice revealed by the current UI label-removal projection all rejected the whole envelope. Safe chart observations remained `ready`. No unsafe text survived in the returned fixed fallback; its symbol and period text are cleared while numeric objective values remain backend-owned.
- Storage-on route generated the history chart once before finalization, saved only an approved safe snapshot, and preserved summary/structured values across response/history/cache. Mutating the original chart/trade data or the returned result did not change the approved history or cached replay. Unsafe history-only chart content caused one refund and no saved row. Read-time validation preserved safe legacy history and redacted unsafe legacy detail, list, and export results without altering the stored row. Storage-off history behavior remained unchanged.
- Purchased-credit route cases confirmed normal ready charge with no refund; malformed/schema-invalid/semantic/chart/history safety failures refunded once; replay caused no extra model call, charge, or refund. Finalization exception tests kept their refund and cleanup behavior. Provider/chart/network were mocked or H4 blocked, and all DB access used H4-owned temporary paths. Full TestOnly/BuildChecks remain unrun.
- The first focused run exposed an old object-identity assertion after route deep copying; it was updated to assert value equality and ownership. Later safety/review-access regressions exposed a legacy string subclass copy order and mock signature mismatch; both were corrected and their H4 reruns passed. These were distinct compatibility errors, not repeated failures of the full-envelope approach.
- `git diff --check`: PASS. Branch/HEAD remained unchanged, staged files 0, and no frontend, Node, protected README, or other-worktree file was changed.

2026-09-27, final fallback confidence-reason coverage after the common finalizer validation below:

- Added one structured regression for an unsafe server-owned `data_confidence.reasons` string in fallback. The model text leaf audit still excludes server-owned metadata, while final user-visible safety checks inspect that metadata separately. Unsafe confidence text produced the fixed model-free fallback with empty chart context.
- Current source inventory: OpenAI client 16, structured review 33, refund 10; Python direct 507 = baseline 493 (35 A1/foundation/helper, 436 migrated, 22 OUT) + Stage 1 14. Manifest missing/duplicate/extra 0, child probes 18, expected skips 0. This root-cause round added 17 direct cases to the prior 490 total.
- H4 PASS: OpenAI client 16/16, structured review 33/33, refund route 10/10, AI safety 17/17, safety finalization 2/2, route history/consent 4/4, transport 10/10, access control persistence 4/4, `test_full_test_entrypoint` 14/14, and `test_storage_fixture_runner` 2/2. Guarded modules reported violations/unexpected 0; all reported restoration, patch restoration, and cleanup true. No live OpenAI/network or private/persistent DB access; full TestOnly/BuildChecks remain unrun.

2026-09-27, initial common finalization boundary validation before the fallback confidence-reason extension:

- Added 16 direct cases: 12 structured safety/finalization cases and 4 route/refund cases. Current OpenAI client 16, structured review 32, refund 10. Source inventory: Python direct 506 = baseline 492 (35 A1/foundation/helper, 435 migrated, 22 OUT) + Stage 1 14. Manifest missing/duplicate/extra 0, child probes 18, expected skips 0.
- H4 PASS: OpenAI client 16/16, structured review 32/32, refund route 10/10, AI safety 17/17, safety finalization 2/2, route history/consent 4/4, transport 10/10, access control persistence 4/4. Each guarded module reported violations/unexpected 0 and restoration, patch restoration, cleanup true. Coordinators `test_full_test_entrypoint` 14/14 and `test_storage_fixture_runner` 2/2 passed with restoration and cleanup true.
- Both builders returned the exact finalizer result object for safe model output. The route preserved the finalizer's legacy summary and structured tree while adding access metadata. A schema-derived path audit covered every current model text path in leaf and canonical composition checks; the canonical set includes cards, assessments, checklist/playbook items, lesson, evidence, uncertainty, questions, sections, and the whole document.
- Raw/plain, Unicode escaped, mixed escape, nested/list, basic good-point/improvement, advanced detail, and cross-item advice were rejected. Truncation-created unsafe suffixes at 160 and 900 characters were rejected after normalization; the 40-character label path normalized to a safe allowed label. Unsupported or over-limit final trees never became ready. Unique unrelated model text was discarded with unsafe semantics.
- Safe structured examples had no false-positive rejection. Every returned model text leaf, canonical unit, and legacy summary checked in the regression was safe. An unsafe fallback chart observation produced the fixed safe fallback with chart text removed. Basic and advanced safety failures refunded once; composed, normalized, and final-tree rejection refunded once; replay added no model call or refund. Normal, malformed, schema-invalid, and missing-key policies remained intact.
- Existing 20/21/200-fill objective and prompt-window tests, objective injection protection, and detailed legacy summary tests remained passing. AI/network/chart calls were mocked, storage was H4-owned temporary SQLite, and no private/persistent DB was accessed. No `main.py` or frontend change; full TestOnly/BuildChecks remain unrun.

2026-09-27, second revalidation correction in the same uncommitted worktree:

- Added three direct cases: two structured checks for unsafe and safe composed title/detail text, plus one purchased-credit route refund check. Current module counts: OpenAI client 16, structured review 20, refund 6. Actual source inventory: Python direct 490 = baseline 476 (35 A1/foundation/helper, 419 migrated, 22 OUT) + Stage 1 14; manifest missing/duplicate/extra 0, child probes 18, expected skips 0.
- H4 PASS: OpenAI client 16/16, structured review 20/20, refund route 6/6, AI safety 17/17, safety finalization 2/2, route history/consent 4/4, OpenAI transport 10/10, and access control persistence 4/4. Each guarded module reported violations/unexpected 0 and restoration, patch restoration, cleanup true. Coordinators `test_full_test_entrypoint` 14/14 and `test_storage_fixture_runner` 2/2 passed with restoration and cleanup true.
- The split-field counterexample (`title="목표가"`, `detail="80,000원입니다."`) passed raw and per-field checks, then was rejected after summary composition. The response contained no composed unsafe phrase in either fallback summary or structured fallback. A safe title/detail pair remained visible in the legacy summary. The route refunded the purchased advanced review exactly once, including idempotent replay.
- Earlier decoded safety, full episode objective, malformed/schema-invalid refund, and legacy summary regressions remained passing. All AI responses and chart data in these tests were mocked; storage used only H4-owned temporary paths, with no live OpenAI/network or private/persistent database access. Full TestOnly and BuildChecks remain unrun.
- `git diff --check`: PASS. Branch/HEAD remained unchanged, staged files 0, and no out-of-scope worktree files were edited.

2026-09-27, corrections in the same uncommitted Stage A worktree:

- `-I -X utf8 -B tests/run_isolated_tests.py --inventory-only`: PASS. Actual source inventory: 487 Python direct = baseline 473 (35 A1/foundation/helper, 416 migrated, 22 OUT) + Stage 1 14. The corrections add 14 cases: 9 to the structured module and 5 route/refund cases. Existing OpenAI client IDs remain 16/16. Manifest missing/duplicate/extra 0; child probes 18, expected skips 0.
- H4 targeted PASS: structured review 18/18, route/refund 5/5, OpenAI client 16/16, OpenAI transport 10/10, AI safety 17/17, safety finalization 2/2, route history/consent 4/4, and access control persistence 4/4. Each guarded module reported zero violations/unexpected, with restoration, patch restoration, and cleanup true. `test_full_test_entrypoint` 14/14 and `test_storage_fixture_runner` 2/2 also passed, with restoration and cleanup true.
- Decoded safety: plain, fully `\u`-escaped, and mixed escaped/plain prohibited phrases all produced `safety_rejected` fallback; valid escaped structured content passed. No prohibited decoded text reached the fallback summary or structured review.
- Full episode objective: 20 fills remained aligned with a 20-fill prompt; 21 buys produced `trade_count=21` and `open_quantity=21` while prompts contained only fills 2–21. A 21st sell produced `trade_count=21`, `open_quantity=19`, and realized P&L `102` versus `100` from the truncated window. A 200-fill episode produced `trade_count=200` and `open_quantity=200` with only fills 181–200 in either prompt list.
- Purchased advanced review route: valid structured output consumed one ticket; malformed JSON, schema-invalid JSON, and safety rejection each returned fallback plus exactly one refund; missing-key fallback retained its existing non-refund status. Idempotent replay did not invoke the model or refund again. Only mocked AI and H4-owned temporary SQLite paths were used; no live OpenAI, network, private, or persistent DB access.
- Advanced legacy summary regression confirmed detailed analysis, all playbook phases, lesson/application, original core headings, and reflection questions. Basic and advanced malformed fallbacks retained their original summary functions.
- `git diff --check`: PASS after corrections. HEAD/branch remained unchanged; no staging, commit, push, or out-of-scope file edits. Full TestOnly/BuildChecks were not run.

2026-09-26, this worktree at starting HEAD `787a9d5683803003fe2c7bfe1e786f5874847462` plus the Stage A working diff:

- `-I -X utf8 -B tests/run_isolated_tests.py --inventory-only`: PASS. Python direct 473 = baseline 459 (35 A1/foundation/helper, 402 migrated, 22 OUT) + Stage 1 14; child probes 18. Source/manifest missing, duplicate, extra 0; expected skips 0.
- H4 targeted runs with `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe` (3.12.14): `tests.test_ai_review_openai_client` 16/16 PASS, `tests.test_trade_review_structured` 9/9 PASS. Both reported violations/unexpected 0 and `restored`, `patches_restored`, `cleanup` true. The structured history test used only an H4-owned temporary SQLite database.
- H4 regression runs with that interpreter: `tests.test_ai_review_openai_transport` 10/10 PASS; `tests.test_full_test_entrypoint` 14/14 PASS; `tests.test_storage_fixture_runner` 2/2 PASS. Each coordinator reported cleanup and restoration true; the transport module reported zero violations/unexpected.
- Initial attempts with the bundled workspace Python reached no testcases: both targeted modules failed during H4 bootstrap with `ModuleNotFoundError` in `install_network_patches` because its runtime lacked `requests`. Both reported restoration and cleanup true. The approach was stopped and the existing dependency-equipped `.venv` interpreter used instead; no package installation or external request was made.
- OpenAI documentation was checked for Responses `text.format` with strict `json_schema` and supported array/string bounds. The HTTP request shape was tested with a mocked transport; no live OpenAI call was made.
- `git diff --check`: PASS. New untracked files also had no trailing whitespace in a separate scan. Final status has six modified tracked files and three new untracked files; staged files 0, HEAD unchanged.

## Remaining / Unverified

- Live OpenAI response behavior and device/frontend rendering remain unverified and outside Stage A.
- Full TestOnly and BuildChecks were not run as requested.

## Stage A Next Step (historical)

The prior HOLD findings and the full-response-envelope boundary are addressed and ready for independent Stage A revalidation. Begin Stage B only under a separate authorized scope.

## Stage A Out of Scope (historical)

Frontend, Node tests, PDF linkage, OAuth, debug preview, other worktrees, deployment, Git staging/commit/push, and full TestOnly/BuildChecks.
