# Broker / direct review depth selection

## Goal

Trade input/preparation -> selected trade confirmation -> descriptive basic/advanced
selection -> explicit execution through the existing canonical review path.

## Scope

Worktree D:/Project/Vibe/StockBoda.worktrees/broker-import-ux-main; branch
integration/broker-import-ux-main; HEAD e648328c15ca8f70e990c491d6fc8c5d12c71771.
Starting staged/unstaged/untracked/unmerged: 0/0/0/0. This follows the approved
six-file broker memory-input commit; its previous plan's commit Next Step is historical.
Protect original feature worktree (0 staged / 9 modified / 10 untracked) and main's
existing Play README change. No staging, commit, push, integration or other worktree writes.

## Decisions

- Reuse selectedReviewTrades for direct and prepared broker input. No cards before ready input.
- Reuse the existing symbol/date/buy/sell-count confirmation; no additional numeric calculation.
- Reuse aiReviewType (basic default). Selection changes type only, never trades or stored results.
- Execute basic via loadAiReview; advanced via the unchanged startAdvancedReview entitlement gate.
- Consent remains mandatory for execution. Unknown entitlement remains server-authoritative;
  zero advanced tickets open the existing dialog. Rewarded basic policy is unchanged.
- Preserve pending/direct round trips, import time rules, local/numeric IDs, unsaved drafts,
  canonical source/body/display separation, fail-closed rendering, history and auth contracts.
- Use native radios, compact dark-theme cards and normal document flow; no new fixed/sticky layer.

## Current Status

- [x] Reconcile actual branch/HEAD/clean status and protected worktree baselines.
- [x] Inspect common selection, consent, entitlement, canonical API and existing H4 VM/AST harness.
- [x] Implement the pre-execution selection unit only.
- [x] Run targeted H4, inventory, lint/build and whitespace checks.
- [x] Record mobile evidence limits and independent review readiness.
- [ ] Independent approval of this unit (not performed by this implementation run).

## Verification

2026-10-11: read-only source investigation. Current CTAs choose and execute in the
same click; loadAiReview checks consent and calls /api/journal/ai-review-once with
existing canonical display headers. startAdvancedReview checks known-zero tickets
before that call; unknown availability defers to server verification. Existing
selectedReviewTrades scopes pending imports to broker mode. No live service/model calls.
Validation effects will be limited to H4-owned synthetic temp data and mocked I/O,
local lint/build outputs (ignored dist), and process-only environment. No env-file edit.

### Implementation and verification (2026-10-11)

- TradingJournal adds native radio description cards only when selectedReviewTrades
  is nonempty. Existing confirmation now also uses ready selection, preventing an
  old saved-group summary from appearing as ready during pending broker input.
  Reuse aiReviewType and add startSelectedReview: consent/busy/empty guards, then
  existing basic loadAiReview or unchanged advanced startAdvancedReview. Neither
  card selection nor import preparation calls API/storage/AI/entitlement/ad services.
- Keep the existing explicitly labeled rewarded-basic alternative, its disabled
  conditions, handler and ad policy unchanged. No new entitlement acquisition or
  consumption; advanced selection is allowed, execution retains known-zero dialog
  and unknown-wallet server gate. Result/history/canonical rendering is untouched.
- App.css: existing colors/borders, native radio/focus indication, responsive minmax
  columns (one column <=480px), wrapping and normal document flow. No fixed/sticky
  controls, new objective calculation, result CTA or Debug tool.
- Existing official mobile VM harness now extracts real selection JSX, radio inputs
  and execution handler; three registered cases cover ready gating, identical input
  paths/data preservation, actual basic/advanced API payload and consent/busy/entitlement.
  The existing pending/prepared/direct round-trip regression also asserts cards
  stay absent while mixed-side time validation/preparation is incomplete.
- Command prefix (in this worktree):
  `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -I -X utf8 -B tests/run_isolated_tests.py`.
  Node: `C:/Program Files/nodejs/node.exe`.
  1. `--node-entrypoint test:journal-mobile-ux --node-executable <Node>`:
     exit 0, 29/29 PASS, FAIL/SKIP 0 (first run).
  2. `--node-entrypoint test:broker-import --node-entrypoint test:review-selection
     --node-entrypoint test:app-navigation --node-entrypoint test:canonical-review-renderer
     --node-entrypoint test:ai-chart-source --node-entrypoint test:legacy-review-cross-contract
     --node-executable <Node>`: exit 0, 93/93 PASS (19/5/5/10/43/11), FAIL/SKIP 0.
     Actual synthetic Python chart/admission handoffs pass; no external/model calls.
     Both runs: coverage missing/extra/duplicate 0, guard/unexpected 0, restoration,
     patch restoration and cleanup true; stderr/errors/issues empty.
  3. `--node-inventory-only`: exit 0, 23 entrypoints / 237 direct,
     missing/extra/duplicate 0, missing source dependencies empty. Only three new
     case IDs, mobile test SHA and three existing component pins change; no reads,
     guard/coordinator/Python inventory changes.
  4. In frontend: `npm.cmd run lint` exit 0; `npm.cmd run build` exit 0,
     Vite 8.0.16 / 1862 modules. Process-only flags VITE_ALPHAMATE_ENV=production,
     VITE_API_BASE=http://127.0.0.1:8002, VITE_ENABLE_DEV_TOOLS=false,
     VITE_APP_NAME=StockBoda; no .env change, app/server/API/Capacitor/APK execution.
  5. `git diff --check` and `git diff --cached --check`: exit 0.
- Supplemental browser evidence uses the prior F4 pattern: AST-extracted original
  confirmation/selection/consent JSX and App.css, real React server rendering,
  existing Playwright and headless Edge, with all page requests aborted, no server.
  Task-owned temp harness: stockboda-review-selection-71aef2d40dce4d638b7151aa8f7c6679/layout.cjs.
  Command: `C:/Program Files/nodejs/node.exe <temp>/layout.cjs`.
  First run failed before DOM checks because its isolated context omitted the actual
  dateTimeText helper (ReferenceError). Add only that original AST declaration;
  second run exit 0. No product change or third attempt. Edge 155.0.4283.45:
  320/360px x basic/advanced = 4/4 PASS, horizontal overflow/clipped children 0,
  each card 113px high, execution CTA 42px high. Selected badge and Korean wrapping
  visually inspected at 320px. Synthetic 64px banner reservation remains below CTA;
  page requests/errors 0 and browser/context closure succeeds. This is static DOM/CSS
  evidence, not a full-app React/device/native-ad claim. No repository browser fixture added.
- Final preservation audit: branch/HEAD unchanged; 0 staged / 5 tracked modified /
  1 untracked plan / 0 unmerged. Original feature HEAD/status/index entries and all
  19 dirty-file hashes are unchanged; main HEAD/status/index entries and its existing
  README hash are unchanged. No other worktree writes or stage/commit/push/merge/rebase.

## Remaining / Unverified

Independent review of this new UX unit remains pending. Real input -> review on
Android/WebView at 320/360px, native banner/ad behavior, and live execution are not
verified. Supplemental browser evidence is not a device or real entitlement test.
Actual Android/WebView and native banner/ad behavior require separate device evidence.

## Next Step

Independent review of this pre-execution selection unit, then wait for authorization.
Only after approval, propose the next single UX unit: a basic-result -> advanced
action using the same original trade input and existing entitlement/canonical path.
Do not implement that result CTA, commit or push in this step.

## Out of Scope

Result redesign, basic-to-advanced result CTA, old StructuredAiReview/validator transplant,
Debug fixtures, backend/model/schema/prompt, OAuth/session, policy, production/network/DB,
Capacitor/APK, original dirty files, main and Git mutations.
