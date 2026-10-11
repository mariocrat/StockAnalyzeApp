# Basic result to advanced review

## Goal

Live basic result -> advanced action -> the exact original request trades, through
the existing consent/entitlement/canonical execution path, without re-entry.

## Scope

Worktree D:/Project/Vibe/StockBoda.worktrees/broker-import-ux-main, branch
integration/broker-import-ux-main, starting HEAD
3925c408f1fd69f1eb82abcd5b07a54583898441, clean 0/0/0/0.
Earlier memory-input and depth-selection units were independently approved and
committed as e648328 and 3925c408 (user confirmation, verified Git).
Protect original feature's 0/9/10 and main's existing Play README modification.
The user has independently approved this unit (Blocker/Major/Minor 0) and explicitly
authorized one local commit containing only the nine listed files. No push/merge/
rebase or writes outside this worktree and allowlist.

## Decisions

- Use current review-display.v1 / CanonicalReviewRenderer, not old structured or
  Debug preview code. Do not alter response/schema/prompt/backend/policies.
- Retain a separate memory-only, immutable copy of the actual request input before
  awaiting I/O, linked by response identity. Never derive input from AI output,
  current selection, displayed chart, or a history fallback.
- CTA requires a valid live basic result and its original source. Hide on advanced,
  malformed/fail-closed/internal/error results, missing source or mismatched response.
- Preserve all request values/order, numeric persisted IDs and absent/null IDs for
  nonpersisted input. Reject preview/local identifiers as persisted source IDs.
- CTA disabled while busy or consent is absent; handler rechecks admission and
  delegates to existing advanced handler. Known zero tickets use the existing
  dialog; unknown tickets and HTTP 402 remain server-authoritative.
- History CTA deferred: backend stores trades[-10:] and reopening can regroup or
  fall back to one trade; it does not guarantee the full original request. Keep
  existing archive/restore behavior, without migration or reconstruction.
- Place a compact normal-flow CTA below the basic result; advanced replaces the
  current result, with an explicit basic/advanced result label.

## Current Status

- [x] Read instructions/plans, verify clean branch/HEAD and protected baselines.
- [x] Inspect live canonical result, original inputs, history and execution gates.
- [x] Implement isolated live-source retention and advanced CTA.
- [x] Run official targeted H4/inventory, lint/build and whitespace checks.
- [x] Record UI evidence, remaining limits and independent-review handoff.
- [x] Independent approval (user-reported: Blocker 0 / Major 0 / Minor 0).
- [ ] Real Android/WebView verification.

## Verification

2026-10-12: read-only inspection. JournalTradeIn uses optional numeric ID; prepared
broker input has no backend ID. loadAiReview currently receives the selected trades
but retains only the AI response. startAdvancedReview checks known-zero tickets;
loadAiReview enforces consent and existing server/402 handling. History stores at
most 10 trades and uses a separate archive renderer and regrouping restore path.
Testing is limited to official H4-owned synthetic I/O, local lint/build outputs and
process environment; no service/model/production calls or env-file edits.

### Implementation and verification (2026-10-12)

- Add basicReviewInput.js: copy the original JSON request trades before I/O, freeze
  the flat JournalTradeIn rows/array and target metadata, and admit only numeric
  persisted IDs or absent/null IDs. No field calculation, regrouping, truncation,
  AI-output conversion, storage or I/O. Failed capture removes only the optional CTA.
- TradingJournal links that source to the exact live response object. Render uses
  aiReviewSource state; the event handler rechecks source identity through a ref.
  New requests and account workspace resets invalidate old source; an old response
  cannot republish CTA provenance after reset. Result type comes from the response,
  not the input choice. Body and present chart snapshots must pass current canonical
  admission. Missing_key fallback remains eligible only with valid canonical data.
- startAdvancedReview accepts optional explicit original input/target; defaults
  still use selectedReviewTrades/selectedReviewGroup. The existing consent, known
  zero-ticket dialog, idempotency/display headers, server admission, HTTP 402 and
  wallet refresh paths are unchanged. No ad/entitlement token is copied from basic.
  The CTA itself does not locally consume/grant tickets. Successful advanced replaces
  aiReview and shows the explicit advanced-result label; no appended basic output.
- Real original AST/VM handlers and JSX test six new registered cases: direct and
  prepared broker reuse with full date/time/side/price/quantity/fees/memo/source/ID;
  no pre-click service calls and duplicate-tap suppression; invalid/absent/mismatched
  provenance and canonical fail-closed; consent/busy/zero/unknown-402 admission;
  selection/trade mutation during I/O and all 12 rows retained; account reset;
  optional time and rejection of local/string IDs. Existing pending/prepared/direct,
  mixed-side time, draft, canonical and history contracts remain tested.

Official command prefix, in the integration worktree:
`D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -I -X utf8 -B tests/run_isolated_tests.py`.
Node path: `C:/Program Files/nodejs/node.exe`.

1. `--node-entrypoint test:journal-mobile-ux --node-executable <Node>`:
   exit 0, 35/35 PASS, FAIL/SKIP 0, first run.
2. `--node-entrypoint test:broker-import --node-entrypoint test:review-selection
   --node-entrypoint test:app-navigation --node-entrypoint test:canonical-review-renderer
   --node-entrypoint test:ai-chart-source --node-entrypoint test:legacy-review-cross-contract
   --node-executable <Node>`: exit 0, 93/93 PASS (19/5/5/10/43/11).
3. First lint failed once: react-hooks/refs at render admission. Separate React
   render state from the existing event/request ref; no lint suppression or rule
   change. Final `npm.cmd run lint`: exit 0. Only affected mobile/live/history AST
   entrypoints rerun with `--node-entrypoint test:journal-mobile-ux
   --node-entrypoint test:ai-chart-source --node-entrypoint test:legacy-review-cross-contract
   --node-executable <Node>`: exit 0, 89/89 PASS (35/43/11). No targeted test failure.
   All three runs: coverage missing/extra/duplicate 0, guard violations/unexpected 0,
   errors/issues/stderr empty, restoration/patch restoration/cleanup true. Every H4
   task root was confirmed absent afterwards. Final unique related cases: 128.
4. Final `--node-inventory-only`: exit 0, 23 entrypoints / 243 direct tests,
   missing/extra/duplicate 0, missing_source_dependencies empty. Only the six new
   mobile IDs, two exact reads of the new frontend helper, test SHA and existing
   component SHA pins change. Python inventory and coordinator/guards unchanged.
5. Final `npm.cmd run build`: exit 0, Vite 8.0.16 / 1863 modules. Process-only flags
   VITE_ALPHAMATE_ENV=production, VITE_API_BASE=http://127.0.0.1:8002,
   VITE_ENABLE_DEV_TOOLS=false, VITE_APP_NAME=StockBoda. No env-file edit, app/server/
   API/model/DB/Capacitor/Android execution; ignored dist only.
6. Supplemental browser (not TestOnly/full-app/device evidence): original live
   result AST JSX, actual canonical renderer/helper and CSS, React server render,
   existing Playwright/headless Edge 155.0.4283.45, no server/all page requests
   aborted. Task-owned temp stockboda-basic-advanced-34647ff60ecb4d93b2a1d55ad8e400a9/
   layout.cjs run with the above Node path: exit 0, 320/360px x basic/advanced 4/4
   PASS, overflow/clipped children 0, CTA 42px and normal-flow, CTA absent on advanced,
   synthetic 64px banner nonoverlap, page requests/errors 0, browser closed. The 320px
   basic screenshot was inspected. Actual WebView and native ads are unverified.
7. `git diff --check` and `git diff --cached --check`: exit 0. Original feature's
   HEAD/status/index mapping and all 19 dirty-file hashes, and main's HEAD/status/
   index mapping/existing README hash match the starting read-only baselines.
   Integration stays on 3925c408, staged 0 / modified 7 / untracked 2 / unmerged 0.
   Modified: component/CSS, mobile/chart test harnesses, inventory and two previous
   plan handoff records. Untracked: this plan and basicReviewInput.js. No Git writes
   or other worktree edits. Prior plan approval/commit statuses reconciled with
   user confirmation and current Git, without rewriting historical verification.

## Remaining / Unverified

History CTA (full original-request provenance not guaranteed); real Android/WebView,
native banner layout, live advanced execution and actual ticket/consent experience.

## Next Step

The user-authorized single local commit for this independently approved unit is the
current step. After verifying and reporting it, wait for the next instruction; do
not push or integrate.

## Out of Scope

Fixed-card redesign, schema/model/prompt/backend, legacy migration, Debug fixture,
ads/OAuth/entitlement policy, production/network/DB, Android/APK, push, merge, rebase,
force push, branch switching, and all other changes outside this allowlisted commit.
