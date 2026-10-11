# Canonical Display Phase 5 integration regression — 2026-10-05

Result: **HOLD / stopped on a confirmed P2 production defect.** No production
behavior was changed. The user requires an immediate stop on a production
defect, so the remaining browser cases and additional regression work were not
executed. This report does not mark Phase 5 complete or approve Phase 6.

Worktree: `D:\Project\Vibe\StockBoda.worktrees\structured-trade-review`.
Branch: `feature/structured-trade-review`.
HEAD: `787a9d5683803003fe2c7bfe1e786f5874847462`.
Starting Git state: staged 0 / tracked unstaged 29 / untracked 36.
The user's independent approval of Phase 2D-4 supersedes historical HOLD
statements in earlier plan sections.

## Confirmed P2: production Axios error decoration loses the client gate code

Affected boundary: production HTTP error response → shared Axios interceptor →
`reviewDisplayFailureMessage` → execute/history/export user notice.

Exact reproduction already executed in the real browser:

1. Build the existing production frontend with dev tools disabled and a local
   synthetic API endpoint. Open `dist/index.html?view=journal` in isolated Edge.
   Use a synthetic stored session, synthetic trades, select a trade group and
   accept AI consent; no real login/provider/DB is involved.
2. Submit the normal AI review button. The synthetic HTTP fixture returns the
   exact backend client-gate status and shape:

   ```json
   {
     "detail": {
       "code": "unsupported_review_display_client",
       "message": "AI 복기를 표시하려면 앱을 업데이트해 주세요."
     }
   }
   ```

   Status is 426. The fixture omits optional request-ID/retry headers, which
   must not prevent the gate notice from being shown.
3. The real `frontend/src/main.jsx:10` installs
   `installAxiosRequestIdMessages(axios)`. In
   `frontend/src/utils/apiErrorRequestId.js:57`, its no-request-ID branch assigns
   `appendRetryAfterToMessage(detail, null)` back to `detail`. That function
   starts with `String(message || '')`, changing the object to `[object Object]`.
   The request-ID branch at lines 52–55 also converts the object into a string.
4. `frontend/src/utils/reviewDisplayContract.js:12` can no longer see
   `detail.code`. The actual browser renders the generic body status
   `AI 복기 분석을 불러오지 못했습니다.`; the required update message never
   becomes visible during the 30-second wait.

The DOM assertion for the generic body succeeds, then the exact update-notice
assertion times out. The final browser report has no JavaScript page errors or
external requests. The previous Node test for the fixed update notice supplies
an Axios stub and runs the production handler without this globally installed
interceptor, explaining the missing integration coverage.

Severity is P2: the backend gate remains fail-closed, but the supported
frontend error path loses the machine-readable code and required user action.
All four AI display requests use the same helper and Axios singleton; only
execute was reproduced in the actual browser before the stop. The other notice
surfaces are affected by the same source path, not separately browser-verified.

Next smallest correction, **not applied**: preserve structured `detail` objects
in the common Axios interceptor. Keep existing string-message request-ID/retry
decoration intact. Verify the actual installed interceptor plus display helper
with and without request-ID/retry headers and the real production entrypoint.
Do not weaken the gate, add raw summary fallback or replace the fixed notice.

## Full official verification

Existing absolute executables were checked: Python 3.12.14 at
`D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`; Node 24.15.0 at
`C:\Program Files\nodejs\node.exe`.

```powershell
& .\scripts\verify_project.ps1 -Mode TestOnly `
  -PythonPath 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' `
  -NodePath 'C:\Program Files\nodejs\node.exe'

& .\scripts\verify_project.ps1 -Mode BuildChecks `
  -PythonPath 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' `
  -NodePath 'C:\Program Files\nodejs\node.exe'
```

| Check | Executed result | Limit / failure |
| --- | --- | --- |
| Official full TestOnly | exit 2 | Python passes; Node has two failed cases |
| Full Python | 790 PASS / 0 FAIL / 0 ERROR / 0 SKIP | All registered direct cases executed |
| Python child probe contracts | 18 matched / 0 contract mismatch | Counted separately from direct tests |
| Full Node | 221 PASS / 2 FAIL / 0 SKIP | All 223 registered cases executed |
| Official BuildChecks | exit 2 | Stops at secret scan after compile |
| Backend compile | PASS | Bytecode generated; no backend import/runtime DB operation |
| Tracked secret scan | FAIL, exit 1 | Existing M2: `docs/release_preparation_checklist.md:205`, service-account JSON example |
| Frontend lint, supplemental same command | FAIL, exit 1 | Four errors, listed below |
| Frontend production build, supplemental same command | PASS, exit 0 | Existing installed dependencies only; local API and production flags |

The official BuildChecks wrapper did not reach lint/build after the scan
failure. The supplemental commands are `npm.cmd run lint` and `npm.cmd run build`
using the approved Node's adjacent npm. They do not convert the official
BuildChecks failure into a pass, and no checker exclusion was added.

Unchanged Node failures in `scripts/journal-mobile-ux.test.js`:

- `successful AI review is not replaced by a failed follow-up refresh` requires
  the removed `AiReviewSummary` production connection.
- `review output removes internal evidence labels and hides consumed one-time
  trial balances` requires the removed frontend evidence-label replacement.

These are stale source assertions relative to the approved canonical transition.
They were preserved byte-for-byte; expectations were not weakened or rewritten.
Their failed status remains part of the official result.

Lint errors, also preserved:

- `frontend/scripts/client-event-log.test.js:152`, `no-useless-escape`.
- `frontend/scripts/legacy-review-cross-contract.test.js:156` and `:168`, unused
  `summary` bindings.
- `frontend/src/components/TradingJournal.jsx:1894`, `react-hooks/refs` diagnostic
  on the history-detail event callback. This is a lint diagnostic; a runtime
  ref-read defect was not independently established by it.

Initial frontend build preparation lacked `pdfjs-dist` in the main checkout's
installed tree. Its first build failed resolution of the declared PDF import.
An existing 6.2.108 installation in the broker-import checkout matches this
worktree's package-lock version; only that package was copied into this
worktree's newly created, ignored `frontend/node_modules`. The next build
passed. The main dependency tree was likewise copied read-only into the current
worktree. No install/download command or write to either other checkout was used.

## Final source and execution inventory

| Inventory | Source | Actual execution | Missing / duplicate / extra / skip |
| --- | --- | --- | --- |
| Python direct | 790, 95 total manifest modules including probes | 790 | 0 / 0 / 0 / 0 |
| Python child probes | 18 | 18 | 0 / 0 / 0 / 0 |
| Node | 23 entrypoints, 223 direct | 23 entrypoints, 223 direct | 0 / 0 / 0 / 0 |

Python classification: baseline 35 A1/foundation/helper + 718 migrated + 22 OUT
= 775; Stage 1 adds 15, yielding 790 direct. Expected skips are 0.
Both inventories were re-read source-only at closeout and remained unchanged.
Node missing source dependencies are 0. The supplemental `.mjs` browser harness
is explicitly outside the official direct Node inventory; its 17 completed
DOM checks are reported separately and are not added to 223.

## Prior finding regression matrix

Every listed module below passed in the **full** official execution. Browser
coverage is only the partial real-DOM coverage stated separately.

| Required family | Executed regression evidence | Result |
| --- | --- | --- |
| Unicode / mixed escapes | `test_trade_review_structured` 75, `test_ai_review_safety` 17, `test_review_display_contract` 14 | PASS |
| `매**수**` / legacy Markdown reinterpretation | display contract 14, legacy compatibility 14; Node canonical renderer 10, legacy cross-contract 11, parser 7 | PASS |
| Split field / split run | structured 75, envelope contract 26, source admission 23, adapter 44 | PASS |
| Truncation / composition | structured 75, source contract 32, finalizer compatibility 18, refund 13 | PASS |
| Low-confidence sticky rejection | structured 75, source admission 23, finalizer compatibility 18 | PASS |
| Malformed / schema-invalid | structured 75, source contract 32, route compatibility 26, refund 13 | PASS |
| Chart / context / tooltip safety | source admission 23, market admission 26, envelope 26, adapter 44; Node chart-source 39 | PASS; actual tooltip CSS unrun |
| Unknown nested string | source contract 32, source admission 23, display 14, envelope 26, adapter 44 | PASS |
| DTO immutability / pickle / copy / restore | source contract 32, envelope 26, structured 75 | PASS |
| Source admission | source contract 32, source admission 23 | PASS |
| Market-data admission | market admission 26; existing chart/provider regressions in full suite | PASS |
| Full objective episode / 20 display window | source admission and structured named 20/21/200-episode cases | PASS |
| Compatibility legacy-safe subset | legacy compatibility 14, finalizer compatibility 18, route compatibility 26; Node cross-contract 11 | PASS |
| Response / history / cache / replay identity | route compatibility 26, adapter 44; Node chart-source 39 | PASS; browser live/replay identity only |
| Legacy whole-record adapter | adapter 44; Node cross-contract 11 / chart-source 39 | PASS |
| Client version gate | actual ASGI gate 11; Node production request tests in chart-source 39 | PASS backend; browser update notice P2 |
| Stale / corrupt cache fail-closed | route compatibility 26 and actual ASGI gate 11 | PASS |
| Refund once / replay effects 0 | refund 13, route compatibility 26, gate 11 | PASS |
| Old / no-snapshot client fallback forbidden | gate 11; Node chart-source 39 and renderer 10; desktop snapshotless DOM | PASS for covered paths |

No existing testcase, expected value, source inventory declaration or production
validation/admission rule was changed during Phase 5.

## Actual browser / DOM / CSS evidence

Existing bundled Playwright 1.62.1 drove installed **Edge 154.0.4258.53**, headless.
The actual successful production build was served by a read-only loopback HTTP
server, through its original `main.jsx` entrypoint, App, TradingJournal,
CanonicalReviewRenderer, JournalTradeChart and compiled production CSS.
No production component, parser or renderer was replaced. Browser contexts and
profiles were fresh and task-owned; external page requests were blocked, service
workers disabled and external hostname resolution blocked. API responses were
intercepted synthetic fixtures, not a live provider or private server.

The required fixtures for ordinary basic/advanced/plain/strong and failure
content came from the existing H4 helper executing real production generation,
sealing, routes, synthetic history/cache, read adapter and replay. The whitespace
case additionally uses the existing shared canonical vector in the actual
frontend; it is renderer/CSS evidence rather than a new backend route approval.

Desktop **1440 × 960** completed **17 checks**:

- Basic, advanced, strong and whitespace live bodies: each logical textContent
  and browser visible innerText equals canonical_text exactly. Strong ranges,
  block/paragraph order and counts match. The normal strong body is `[0,5)` for
  `체결 기록`. Repeated spaces, newline and tab in the shared vector survive.
- Basic/advanced/strong/whitespace/replay chart cards and active chart headers
  match their exact canonical documents.
- Invalid-output fallback body has exact canonical text and paragraph sequence.
- Replay renders the same canonical content as immediate response.
- Snapshotless response shows the fixed unavailable status, with 0 chart/card
  outputs and 0 visible raw summary/structured-review decoy strings.
- Completed text checks use computed white-space, text range rectangles and
  ancestor visibility/clipping/line-clamp checks. No clipping or hidden text was
  observed in those completed surfaces; expected white-space is pre-wrap.

The next desktop case is the **failed unsupported-client notice** described
above. Browser page errors 0; external page requests 0. Browser and server were
closed. No Android/device or external-system result is claimed.

Unexecuted because of the immediate production-defect stop:

- All **390px mobile-width** cases.
- Actual history detail/unavailable DOM/CSS cases.
- Actual lightweight-charts marker hover/tooltip DOM/CSS, including the
  desktop/mobile tooltip text and layout checks.
- Successful required update notice through the full production entrypoint.

Screenshots for desktop basic and strong are saved with the raw evidence. The
failed notice is documented by the successful generic-status DOM assertion and
the exact required-notice timeout; its context closes on failure, so a screenshot
of that failed context was not produced.

## Snapshot identity, billing, replay and persistence

Backend real-route and Node production regressions pass:

- Basic and advanced plain/strong/default approved snapshots keep exact content
  across immediate result, sealed cache, synthetic history save/detail/export,
  replay and actual production JSX/renderer tests. Operational access,
  review_history_id and replay metadata do not change display content.
- Ready routes charge once. Safety, malformed/schema-invalid and compatibility
  terminal errors refund exactly once. Replay adds 0 charge/refund/model/provider/
  market/history/charts-once effects. Unsupported ASGI clients have 0 business
  effects. Corrupt or unsealed old cache fails closed without model re-execution,
  recharge or raw/legacy reconstruction.
- Adapter tests compare original synthetic legacy DB rows and whole-file bytes
  after safe/unsafe/unknown history list/detail/export reads. Bytes remain equal;
  only the read-time whole-record adapter is used. Unsafe raw legacy content is
  withheld. No migration, backfill or private/persistent production DB access.

Actual browser identity is established for immediate/basic/advanced/strong and
replay rendering. Actual browser history CSS identity is **unverified**, even
though the backend and Node/React history chain passed.

## H4, restoration, cleanup and preservation

- Python direct unexpected 0. Guarded violations total 60, all intentional and
  acknowledged: runtime environment 22, socketpair isolation 30, history adapter
  negative boundaries 8. The probe contracts acknowledge 6 expected negative raw
  unexpected attempts; contract mismatches 0. These are blocked negative tests,
  not successful provider/persistent writes.
- All Python direct/probe reports and all 23 Node entry reports have restoration,
  patch restoration and cleanup true. Node unexpected and boundary violations 0,
  including the two failing source-assertion cases.
- Browser/server closed; browser-process temporary profile directory is empty.
  The helper's exact task-owned synthetic chart-backend runtime was removed
  after preserving JSON evidence; its resolved path was checked inside the owned
  temporary root and checked for reparse points before cleanup.
- All 373 starting non-ignored files were hashed. Only the authorized existing
  execution plan changes; other **372/373** starting files remain byte-identical.
  Original staged/unstaged/untracked work is preserved. Other two worktree Git
  statuses match the read-only starting snapshots, and no write was directed to
  either checkout. Read-only Git status used command-local safe.directory where
  needed; no global Git configuration was changed.
- Generated local `frontend/node_modules`, `frontend/dist` and backend bytecode
  remain ignored in this worktree. They are build/dependency artifacts, not staged
  source changes. No package installation, Git mutation, deploy/Play, provider
  request, migration/backfill or production repair was performed.

Task-owned raw logs, parsed full Python/Node reports, fixture handoff, screenshots,
browser report, baseline hashes and verified summary:

`C:\Users\mario\AppData\Local\Temp\stockboda-phase5-13d1929c5957487e85e1840785dcd260`.

Useful files there: `testonly.log`, `full-python.json`, `full-node.json`,
`buildchecks.log`, `frontend-lint.log`, `frontend-build-existing-deps.log`,
`browser-edge-final.log`, `browser-evidence/browser-report.json`,
`browser-evidence/live-basic-1440.png`, `browser-evidence/live-strong-1440.png`,
`baseline.json`, `verified-summary.json`.

Preparation issues are distinct from the P2: initial fixture parent directory
absence, PowerShell JSON handling of an empty package-lock key, missing installed
PDF dependency, Chrome temporary-profile startup restriction and the first
browser harness observing the loading status before the final error status.
Only task preparation/measurement changed; original regression expectations and
production behavior did not. The final browser wait identifies the production
code-loss finding, and no further browser/test work followed that finding.

Phase 5 changes only:

- Existing `docs/exec-plans/structured-trade-review.md`, progress/evidence.
- New `docs/exec-plans/structured-trade-review-phase5-results.md`, this report.
- New `frontend/scripts/review-display-browser-harness.mjs`, supplemental actual
  production browser reproduction and DOM/CSS checks.

Final Git state: same branch/HEAD; staged **0**, tracked unstaged **29**,
untracked **38**. Production behavior changes in Phase 5: **0**.
Phase 6 final independent safety approval: **HOLD**. Finding review can proceed;
Phase 5 needs the P2 handled, official gates resolved without weakened assertions,
and remaining browser/mobile/history/tooltip evidence completed before a final
Phase 6 safety approval. Await the user's next instruction.
