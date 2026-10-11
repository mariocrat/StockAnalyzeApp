# Broker import → review input

## Goal

Prepare selected domestic PDF transactions for the existing basic/advanced review
actions, without saving trades, uploading documents, or executing AI on preparation.

## Scope

Worktree: `D:/Project/Vibe/StockBoda.worktrees/broker-import-ux-main`.
Branch: `integration/broker-import-ux-main`.
Base: fetched `origin/main`, `f779e252b823bbd724c8be277c54d494d3b93f89`.
Initial staged/unstaged/untracked: 0/0/0 (verified outside the restricted sandbox).
The original `feature/broker-import` at `609163e9` remains read-only, with
0 staged / 9 modified / 10 untracked; its index and file hashes are recorded.

## Decisions

- Preserve the current canonical display, consent, entitlement, OAuth and history contracts.
- Keep preview IDs/timeUnknown in an in-memory view model; send only JournalTradeIn fields.
- A preview string ID is not a persisted numeric ID. Imported review groups have no target ID.
- Require missing times for same-date, same-symbol mixed BUY/SELL only; never invent times.
- Group selected import rows by symbol for review selection, not by inferred positions/episodes.
- Keep every row independent, including identical rows; no pairing, merging or FIFO/LIFO.
- Preparation has zero API/storage/ad/model effects. Existing review execution owns AI calls.
- Do not copy old renderer, backend, Debug tools, fixtures or generated files.
- The assigned legacy plans are historical evidence; their old renderer/fallback and Git
  status statements do not supersede the current main contracts or this scoped task.

## Current Status

- [x] Read instructions/plans, fetch, inspect and create a clean latest-main worktree.
- [x] Inspect parser, API admission and review selection boundaries.
- [x] Implement the minimal adapter and preparation action.
- [x] Complete H4 targeted regression with a different VM/AST-expression harness.
- [x] Fix independently reported Major: pending import must not block direct-mode review.
- [x] Revalidate the Major fix through targeted H4, inventory, lint and frontend build.
- [x] Independent re-review of the Major fix: approved; Blocker 0 / Major 0 / Minor 0.
- [x] Final preservation/whitespace audit and confirm the scoped commit allowlist.

## Verification

2026-10-11, this worktree/base, current uncommitted implementation:

- Git fetch and linked worktree creation only; no stage/commit/push/merge/rebase.
- Restricted-sandbox status initially failed; elevated read-only inspection confirmed
  the new checkout is non-bare, on the expected branch/HEAD and clean.
- Existing ignored dependencies were copied read-only from the original install into
  this new worktree. No install/download or other checkout write.
- H4 Node inventory-only initially failed during dependency preparation. Fresh Windows
  checkout raw CRLF bytes differed from several source/vector pins; the committed
  JournalTradeChart source hash also differed from its manifest pin even after LF
  normalization. Re-pin metadata only after confirming unchanged sources match index
  text. External billing provenance remains 1345 bytes and its original exact SHA.
  Coordinator/guard/allowlist algorithms are unchanged. Inventory then passed:
  23 entrypoints / 233 direct, missing/extra/duplicate/dependency issues 0.
- Official Python command prefix:
  `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -I -X utf8 -B tests/run_isolated_tests.py`.
  Node executable: `C:/Program Files/nodejs/node.exe`.
- First H4 selection: `--node-entrypoint` for broker-import, app-navigation,
  review-selection, journal-mobile-ux, canonical-review-renderer, oauth-app-return,
  oauth-initial-state, oauth-logout, ai-idempotency, legacy-review-cross-contract,
  ai-chart-source (each prefixed `test:`), with `--node-executable`. Exit 1:
  133 PASS / 2 FAIL / 0 SKIP, expected/observed 135, coverage issues 0.
- Failures: broker CTA matrix used parser output without the actual UI's initial
  time state; mobile AST harness retained its previous prepareImportedTrades binding
  when recompiling that declaration. Corrected only those test preparations/hashes.
- Second official selection: broker-import and journal-mobile-ux only. Exit 1:
  broker 19/19 PASS, mobile 24 PASS / 1 FAIL, 0 SKIP, expected/observed 44.
  Same failed mobile ID: saved journal entry does not reveal stock details until a
  review is selected or completed. Both runs: unexpected/violations 0,
  restoration/patch restoration/cleanup true. No third invocation.
- Static diagnosis: mobile bindings also carry a loadAiReview mock into compilation
  of the original const loadAiReview declaration. This duplicates a Function parameter
  and a const name. The existing H4 reporter omits failure stacks, so the actual runtime
  exception text is not captured; do not claim a passed import-AI execution regression.
- `npm.cmd run lint`: exit 0. `npm.cmd run build`: exit 0, Vite 8.0.16 / 1862 modules.
  Build used process-only production flags, dev tools false, StockBoda name and
  `VITE_API_BASE=http://127.0.0.1:8002`; no env-file edit, server/request, Capacitor/APK.
  Product bytes did not change after these lint/build checks; final two edits are test-only.
- Final audit: staged 0 / tracked modified 4 / untracked 2. Unmodified renderer/chart/
  vector files have no content diff; external billing fixture keeps 1345 bytes and
  SHA-256 177796cb397239621bbefcff7638a37d4c74c5e64fbb241f28e20a94f2b056d0.
  Original worktree HEAD, full status, index hash and all 19 dirty file hashes are
  unchanged. No main/other-worktree source writes. `git diff --check` has no errors.

### Harness-only follow-up (2026-10-11)

- Re-read instructions/this plan and reconcile the actual integration branch/HEAD.
  Starting status matches the prior stop: 0 staged / 4 modified / 2 untracked.
- The old harness made every mock key a `new Function` parameter while compiling
  entire original `const` statements. Its retained prepareImportedTrades binding
  and, subsequently, its loadAiReview mock collide with those declarations.
  This is a harness binding defect, not evidence of a product defect. Prior failure
  stacks were unavailable; the identifier collisions are confirmed from source.
- Existing official H4 OAuth logout/initial-state tests use node:vm contexts for
  real handlers. Reuse that pattern, with AST-extracted arrow initializers and JSX
  expressions only. No same-name Function parameters, injected mock declarations,
  or repeated declaration filtering. Separate preparation/review contexts contain
  explicit synthetic dependencies; dynamic string/Wasm code generation is disabled.
- Statically check all preparation-handler calls against the pure adapter/local
  setter/preview-cleanup list, then execute the real button and handler. Verify
  missing-time rejection, memory-only conversion, selected symbol, local identity
  exclusion from API rows, preserved saved trades and return to direct input.
  Explicit basic/advanced execution uses the unchanged real AI handler, synthetic
  HTTP responses, existing consent/display headers and a null imported target ID.
  No real API, model, storage or entitlement service is invoked.
- Preserve a caught harness error's full stack on stderr before rethrowing, so the
  official reporter cannot hide the original exception on a future failure.
- Modified only journal-mobile-ux.test.js, its existing inventory SHA, and this
  plan during this follow-up. Product files and broker-import.test.js retain their
  starting bytes; no coordinator/guard/read allowlist or case IDs were changed.
- Official H4 command prefix and Node path are the same approved paths above:
  1. `--node-entrypoint test:journal-mobile-ux --node-executable <Node>`:
     exit 0, 25/25 PASS, 0 FAIL/SKIP. New harness executed once; no failed rerun.
  2. `--node-entrypoint test:broker-import --node-entrypoint test:app-navigation
     --node-entrypoint test:review-selection --node-executable <Node>`:
     exit 0, 29/29 PASS (19 + 5 + 5), 0 FAIL/SKIP.
     Both runs: coverage missing/extra/duplicate 0, violations/unexpected 0,
     restoration/patch restoration/cleanup true; stderr/errors/issues empty.
  3. `--node-inventory-only`: exit 0, 23 entrypoints / 233 direct,
     missing/extra/duplicate 0, missing source dependencies empty.
- `npm.cmd run lint` in frontend: exit 0. `git diff --check` and
  `git diff --cached --check`: exit 0. No new build: product bytes are unchanged
  from the previously recorded build; that build is historical, not rerun here.
- Final Git state remains 0 staged / 4 modified / 2 untracked / 0 unmerged,
  branch integration/broker-import-ux-main, HEAD f779e252b823bbd724c8be277c54d494d3b93f89.
  Original feature HEAD, full status (-uall: 0/9/10) and all 19 dirty file hashes
  match the starting snapshot. Raw index file hashes differ on reinspection, but
  staged content diffs remain empty; do not claim byte-identical index metadata.
  No stage/commit/push/merge/rebase or main/other-worktree source edits.

### Independent Major: pending import / direct selection (2026-10-11)

- Independent review withheld approval: select PDF rows without preparing them,
  switch to direct input, then select saved trades. selectedReviewTrades stayed
  empty, so both normal basic/advanced actions remained disabled.
- Root cause: the selector applied `importedTrades.length ? [] : ...` regardless
  of journalInputMode. The direct-mode handler intentionally cleared only the
  prepared overlay, leaving pending rows available for returning to broker mode.
- Minimal product fix: require `journalInputMode === 'broker'` as well as pending
  importedTrades before blocking selection. No change to either mode-switch handler,
  the adapter, pending PDF rows, prepared input, saved trades or unsaved direct form.
  Preview-local IDs and numeric saved IDs remain separate. Consent, entitlement,
  canonical display and preparation's zero-I/O contract are unchanged.
- New inventory case: `pending PDF selection blocks review only in broker mode
  and survives direct input round trips`. It uses the existing VM harness to execute
  actual selector initializers, chooseReviewGroup and mode-button JSX, then inspect
  the real basic/advanced button disabled props (no provider or model invocation).
  Checks: pending import -> direct -> saved selection with numeric target 42;
  broker return preserves the identical pending array and blocks review/preparation;
  stale invalid preparation cannot proceed; valid timed preparation selects imported
  rows with no numeric target; prepared -> direct restores saved selection; direct-only
  selection works; unsaved form and saved trade arrays are preserved throughout.
- Updated only the journal-mobile-ux case list/test SHA and the three existing
  TradingJournal component SHA pins in inventory. No new reads or guard/coordinator
  changes; broker adapter and parser tests are unchanged.
- First official targeted run (same approved Python/Node paths): journal-mobile-ux,
  broker-import, review-selection and app-navigation, exit 1, 54 PASS / 1 FAIL,
  0 SKIP, coverage 55/55. New VM setup omitted validateTradeTimesForReview.
  Full stderr stack captured: `ReferenceError: validateTradeTimesForReview is not
  defined`, at the actual importedTimeValidation initializer/useMemo in
  recalculateSelection. This was a test dependency omission, not a product failure.
  Added that existing pure dependency only; no repeated named-binding injection.
- Second official targeted run: the same four selectors, exit 0, 55/55 PASS:
  journal-mobile-ux 26, broker-import 19, review-selection 5, app-navigation 5.
  The prior prepared-import case still passes. Broker tests preserve BUY-only /
  SELL-only optional time and mixed same-day/symbol required time contracts.
  Both runs: missing/extra/duplicate 0, violation/unexpected 0, restoration,
  patch restoration and cleanup true. No third targeted invocation.
- `--node-inventory-only`: exit 0, 23 entrypoints / 234 direct, missing/extra/
  duplicate 0, missing source dependencies empty. `npm.cmd run lint`: exit 0.
  `npm.cmd run build`: exit 0, Vite 8.0.16, 1862 modules. Build flags were process-only
  VITE_ALPHAMATE_ENV=production, VITE_API_BASE=http://127.0.0.1:8002,
  VITE_ENABLE_DEV_TOOLS=false, VITE_APP_NAME=StockBoda. No env-file edit, running
  application/API call, Capacitor/Android build, DB/provider/model/config change.
- Final `git diff --check` / `git diff --cached --check`: exit 0. Integration
  remains staged 0 / modified 4 / untracked 2 / unmerged 0 on the same branch/HEAD.
  Hash reconstruction confirms the sole product change in this follow-up is the
  selector's input-mode condition. Original feature HEAD/status (0/9/10), all 19
  dirty file hashes and index entry/blob mapping are unchanged; no other worktree
  source writes. Both targeted runs' H4 temp roots are absent after cleanup.

### Independent approval and scoped commit (2026-10-11)

- User reported independent approval of the current broker-import review-input
  connection: Blocker 0 / Major 0 / Minor 0.
- Commit authorization is limited to these six feature files: the memory-input
  adapter, TradingJournal connection, broker-import and mobile regression tests,
  H4 inventory pins, and this execution plan. No other current change is in scope.
- Prepare one commit with message `feat: connect broker imports to trade review input`
  after confirming the cached file list and complete cached diff match this allowlist.
  Do not push or integrate this branch. After commit, report the SHA and wait.

## Remaining / Unverified

The previous harness HOLD is resolved by the VM-expression verification above.
The independent Major has been fixed and re-reviewed with an approved result.
Actual Android/
provider/device behavior and live imported AI execution are not verified and are
not part of this step. Older OpenAI/device/test records are not fresh verification.

## Next Step

Create the authorized six-file commit, report its SHA and final worktree state,
then wait. Do not push or extend product scope.

## Out of Scope

Original dirty files, other worktree writes, commits/push/merge/rebase, production/API
calls, schema/model/configuration changes, fixed-card UI, depth-selection redesign,
general→advanced CTA, Debug preview and APK/Capacitor builds.
