# Broker import input accuracy — Slices 1, 2 and 3

## Goal and scope

Fix explicit trade-side mapping and preserve PDF fee/tax meaning through the existing
memory preparation and canonical review request. Worktree `broker-import-input-accuracy`,
branch `fix/broker-import-input-accuracy`, base `e1629217858d948ce821c9e31241711dc613c64e`.
The new worktree was created clean. Main's existing Play README and the original
feature worktree (0 staged / 9 modified / 10 untracked) remain protected.

Slice 2 starts clean at `f0ca1e72bad88b04d16a26d3fbf8cd4125bdfa23` on the same branch.
Its goal is complete recognition of supported Toss rows, explicit rejection of partial
imports, and real local PDF.js binary extraction regression. It adds no broker or AI call.

Slice 2 was independently approved and committed as
`f4189a2b7210a353e8f310409ee1ffa3c749edbd`. Slice 3 starts clean at that commit and
finishes confirmation UX: live date/time sorting, early preparation-blocker guidance,
selection behavior and accurate support wording. Parser/completeness remain unchanged.

## Decisions

- Recognize only explicit standalone 매수/구매/buy and 매도/판매/sell; reject ambiguous sides.
- Read Toss 수수료 as fee, and sum the separate 거래세 + 제세금 cells as tax only when both
  are valid. Explicit zero stays zero; absent/malformed values remain null. Do not infer
  costs from transaction/settlement totals or absent columns.
- JournalTradeIn defaults omitted costs to zero; normalize_trade also coerces null to zero.
  Keep that shared backend contract unchanged. The broker adapter therefore refuses any
  unknown/non-numeric/non-finite/negative cost before publishing prepared review input.
  Its existing caller displays the fee/tax confirmation error, with no API/storage/AI effect.
- Keep independent rows, time rules, local PDF handling, consent/entitlements and display
  activation unchanged. No cost editing UI or default estimates in this slice.
- Slice 1 used synthetic coordinate fixtures. Slice 2 adds synthetic PDF bytes generated
  in H4-owned memory and completeness checks; no real customer PDF or new dependency.
  Manual-time sorting was excluded from Slices 1/2 and is included only in Slice 3's
  confirmation view. Field editing, rollout and other worktree writes remain excluded.

## Current status

- [x] Confirm exact base and create the requested clean isolated worktree.
- [x] Trace parser → candidate → adapter → actual review handler → numeric backend contract.
- [x] Implement and verify side/cost regressions through official H4 selectors.
- [x] Run focused backend/Node regression, inventory and lint/build.
- [x] Complete final preservation/whitespace audit.
- [x] Slice 1 independent review approved (Blocker/Major/Minor 0); committed as
  `f0ca1e72bad88b04d16a26d3fbf8cd4125bdfa23` with exactly the approved eight files.
- [x] Slice 2 completeness and real PDF.js binary regression implementation/verification.
- [x] Slice 2 independent review Minor 1 (footer/prose false positives) corrected and focused re-verification passed.
- [x] Slice 2 re-review Major 1 (headerless missing/malformed amounts silently omitted) corrected and focused re-verification passed.
- [x] Slice 2 remaining Minor 1 (split-item purchase/sale instructions misidentified as transactions) corrected and focused re-verification passed.
- [x] Replace incremental exact-x recognition with normalized cell runs, semantic header grammar and inferred column bands.
- [x] Structural coordinate-item matrix and existing broker regressions pass.
- [x] Structural binary split-header fixture boundary clarified after extraction diagnosis; approved replacement integration verified.
- [x] Parser geometry and actual PDF.js binary integration responsibilities explicitly separated.
- [x] Latest Major A/B addressed by normalized row shape -> tri-state classification -> parse, with official shared damage matrix.
- [x] Final tri-state review Minor (non-side label in an occupied side slot) corrected by a separate transaction identity requirement; focused re-verification passed.
- [x] Slice 2 independent final re-verification: Blocker/Major/Minor 0; committed as
  `f4189a2b7210a353e8f310409ee1ffa3c749edbd` (16 files). Final Broker/PDF H4 35/35,
  Node inventory 24/276 and cached whitespace check passed after removing two temporary
  stack loggers and updating the PDF test source hash.
- [x] Slice 3 confirmation sorting, shared preparation guidance and support wording implemented.
- [x] Slice 3 focused H4/inventory, lint/build and preservation audit.
- [ ] Slice 3 independent review; no commit/push/merge authorized.

## Verification

Tests use H4-owned synthetic data and denied external I/O. Build/lint use only existing
approved dependencies and local ignored outputs; no env-file or production changes.
Earlier Slice 2 correction and structural HOLD results below are historical. The tri-state
section records its verified support limits; Slice 2 final review and commit are complete.
### Slice 1 historical implementation evidence (before its approved commit)

2026-10-16 implementation and verification:

- Root causes: generic detection accepted 구매 but the BUY branch omitted it; Toss
  candidates discarded all cost columns and the adapter used Number(value ?? 0).
- Products changed only brokerImport.js and brokerReviewInput.js. The side helper is
  shared by generic and Toss parsing; standalone accepted labels are closed, and
  multiple/unsupported direction labels are rejected. Independent rows remain unchanged.
- Fee/tax provenance is cost cell text → finite nonnegative number or null → candidate
  unchanged by time selection → adapter type/finite/nonnegative check → numeric request
  row → unchanged loadAiReview payload. Explicit zero remains zero. Missing tax components
  never become a partial tax total, and settlement/cash balances never supply costs.
- Unknown costs throw the specific Korean confirmation message before the adapter can
  publish input. The actual existing prepareImportedTrades handler retains pending rows,
  displays that error and has zero API/AI/storage effects. Known fee/tax values reach
  both actual basic and advanced request handlers unchanged, with no preview IDs.
- Synthetic Toss fixture now explicitly supplies the separate SELL transaction tax (15)
  matching its existing text/settlement example; BUY remains fee 1 / tax 0. Four new
  registered cases cover exact side labels, nonzero/explicit-zero costs, all missing/
  malformed cost columns and adapter coercion rejection. Existing time/independence/
  privacy and actual VM direct/broker/basic-to-advanced regressions remain in place.

Official Python prefix:

`D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -I -X utf8 -B tests/run_isolated_tests.py`

Node executable: `C:/Program Files/nodejs/node.exe`.

1. `--node-entrypoint test:broker-import --node-executable <Node>`: exit 0, 23/23 PASS.
2. `--node-entrypoint test:journal-mobile-ux --node-entrypoint test:review-selection
   --node-entrypoint test:app-navigation --node-executable <Node>`: exit 0, 45/45 PASS
   (35/5/5). Combined distinct Node coverage: 68/68, FAIL/SKIP 0; missing/extra/duplicate
   0, guard/unexpected access 0, restoration/patch restoration/cleanup true.
3. `tests.test_journal_batch_limits tests.test_review_source_contract`: exit 0,
   45/45 PASS (13/32), FAIL/ERROR/SKIP 0, violations/unexpected 0, inventory issues empty
   and restoration/patch restoration/cleanup true. Shared backend numeric/admission code
   is unchanged; providers/model/network/storage are isolated by the existing H4 path.
4. `--node-inventory-only`: exit 0, 23 entrypoints / 263 direct, missing/extra/duplicate
   0, missing source dependencies empty. Only four broker IDs and the two modified test
   hashes change; no new reads or coordinator/guard changes. Current-count docs updated.
5. `--inventory-only`: exit 0, Python unchanged at 108 modules / 1,079 direct; baseline
   36/1005/22 plus 16, registered child probes 18, missing/duplicates/expected skips 0.
6. In frontend, `npm.cmd run lint` and `npm.cmd run build`: both exit 0. Vite 8.0.16,
   1,865 modules. Build process only: VITE_ALPHAMATE_ENV=production,
   VITE_API_BASE=http://127.0.0.1:8002, VITE_ENABLE_DEV_TOOLS=false, VITE_APP_NAME=StockBoda.
   No server/app/API execution or env-file change. Reused existing installed dependencies
   via a read-only copy into this worktree's ignored node_modules; no install/lock change.
7. Final diff audit: product changes are limited to the two broker utilities; no backend,
   TradingJournal, extractor, Android, env, lockfile or activation changes. Git shows
   staged 0 / modified 7 / untracked plan 1 / unmerged 0 at the exact base. Whitespace
   check passes. Main has only its protected README change and its SHA-256 remains
   5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328. The original feature
   worktree's 19 dirty-file hashes match the initial snapshot; no other worktree content
   was changed. No staging/commit/push/merge/rebase or production/model call.

### Slice 2 design and verified results — 2026-10-16

- The real extractor returns ordered `pages[{pageNumber, lines, items[{str,x,y}]}]`,
  `pageCount`, joined text and text item count. The parser keeps those page boundaries.
  An observed table row needs execution structure before the two-anchor completeness
  check: header-defined direction/instrument cells and financial fields, or the explicit
  headerless execution/text prototype shape described in the Minor correction below. Anchors
  are date, explicit side, instrument code and positive quantity/price pair. These are
  observed row counts, never an estimated broker total. Explicit summary/balance labels
  in the date/side cells are excluded; ordinary notes and summary-only pages are not trades.
- `completeness.recognizedRows/parsedRows` tracks all identified rows. A required date,
  side, instrument, quantity or price failure yields `toss-incomplete`, no exposed trades
  and a specific Korean alert. Text-only Toss prototype fallback also checks completeness,
  including missing dates and unsupported sides. No generic fallback rescues a broken layout.
- Each page independently establishes its header/columns. Repeated headers are supported;
  headerless transaction continuations are explicitly rejected, never mapped with prior-page
  coordinates. Missing/empty/scanned pages, invalid coordinates and page-number/count gaps
  fail closed. Returned trades sort by descending date, retaining independent source IDs
  and source order for equal timestamps; no matching/merging or time inference was added.
- Toss's exact `name(A######)` cell boundary supports KODEX 200/TIGER 200. Generic numeric
  multi-token names remain unsupported because that prototype lacks this boundary. Required
  date and positive number cells must parse exactly, including valid thousands separators.
  Slice 1 explicit-zero/null costs and its unknown-cost preparation blocker remain intact.
- New `test:broker-pdf-extraction` generates small sanitized PDF bytes in memory: Unicode
  CMap table pages, image-only content and an encrypted input. Actual `File.arrayBuffer()`
  enters the unchanged production `extractPdfText`, real PDF.js and parser. Tests cover
  repeated pages, numeric names/costs, malformed/headerless/empty pages, mixed domestic/FX,
  invalid bytes, no OCR trades, password rejection and recovery. No PDF is persisted/uploaded.
- H4 verifies exactly PDF.js 6.2.108 package/parser/minified-worker files against lock
  version, exact allowlist and raw SHA, then copies them to its owned root. No guard,
  filesystem/network permission or timeout was broadened. A Node resolver only adapts
  Vite's `?url` import to the same local worker URI; the actual worker module load is asserted.
  Canvas is unavailable and render-only platform sentinels reject rendering. This proves
  real Node text extraction/fake-worker behavior, not browser Worker or WebView rendering.
- The existing VM harness executes the actual file-change handler: 25 MiB is admitted,
  limit+1 is blocked before file reading/extraction (synthetic size metadata); incomplete
  results render the actual alert with no transfer CTA. No prepare/AI/history call is added.

Official H4 uses the Python and Node executables recorded above:

1. `--node-entrypoint test:broker-import --node-entrypoint test:broker-pdf-extraction
   --node-entrypoint test:journal-mobile-ux --node-entrypoint test:review-selection
   --node-entrypoint test:app-navigation --node-executable <Node>`: final **79/79 PASS**
   (29/4/36/5/5), FAIL/SKIP 0, missing/extra/duplicate 0, guard/unexpected access 0,
   restoration/patch restoration/cleanup true. Slice 1 cost/time/identity regressions pass.
2. `tests.test_journal_batch_limits tests.test_review_source_contract
   tests.test_quick_verify_docs`: final **52/52 PASS** (13/32/7), FAIL/ERROR/SKIP 0,
   guard/unexpected access 0 and full restoration/cleanup. `tests.test_full_test_entrypoint`
   separately passed **16/16**, with expected negative child protocols preserved.
   Combined distinct Python direct coverage is **68/68**; no full suite was run.
3. `--node-regressions --node-executable <Node>`: **10/10 PASS**, including new missing/
   changed/extra/wrong-version PDF.js snapshot rejection before launch and unchanged private
   filesystem/network/subprocess guards. These nested checks are not new direct inventory IDs.
4. `--node-inventory-only`: **24 entrypoints / 274 direct**, missing/extra/duplicate 0,
   missing dependencies empty. `--inventory-only`: Python unchanged at **108 modules /
   1,079 direct / 18 registered child probes**, missing/duplicate 0. Probe registration
   alone is not probe execution. Current count docs and both old 23/259 count assertions
   now match source; Python manifest IDs are unchanged.
5. `npm.cmd run lint` and `npm.cmd run build`: final exit 0; Vite 8.0.16, 1,865 modules.
   Process-only build settings match Slice 1's local API build; no env file/server/app/API
   execution or Capacitor/Android step. Built `pdf.worker.min-CLrFZWeq.mjs` is 1,312,452 bytes,
   raw SHA-256 `bc0d1b88ea0b66196b1d36a58ac243c6d92adfe725624e2a9fdd381bdf8ef434`,
   byte-identical to installed worker and referenced by the built BrokerImport chunk.
6. First lint run rejected implicit `Buffer`; fixed with explicit Node builtin import.
   The first docs regression rejected stale 23/259; only its expected count was updated.
   The wrapper already uses `--node-all`, so it needed no change. Both rechecks pass.
   Expected PDF.js warnings concern unavailable optional canvas and intentionally invalid
   PDF bytes; positive extraction and all H4 lifecycle checks pass.
7. Final audit at Slice 1 HEAD: staged 0 / modified 13 / untracked 1 / unmerged 0;
   `git diff --check` passes. Product edits are limited to brokerImport.js and BrokerImport.jsx;
   pdfTextExtractor.js and brokerReviewInput.js are unchanged. Main remains at e1629217
   with only its protected README change and the same recorded SHA-256. All 19 original
   feature dirty-file hashes still match the preserved baseline. Other worktree contents
   were not modified; no stage/commit/push/merge/rebase or production action occurred.

### Independent review Minor 1 correction — 2026-10-16

- Cause: the old two-anchor rule counted date + quantity/price footer values, or a date
  + parenthesized code inside prose, as an execution. The otherwise valid document then
  reported recognized 2 / parsed 1 and failed closed unnecessarily.
- Product correction is confined to `isTossTransactionRow`. With a header, require a
  known direction/instrument cell, or both populated identity cells plus quantity/price
  for the existing multiply damaged-row case. Without a readable financial field, both
  direction and instrument must still be known. This excludes numeric-only footers and
  explanatory table-cell text while keeping all existing required-field mutation cases.
- At the Minor correction stage, headerless recognition required an execution prefix plus value fields, an instrument-code
  suffix consisting of numeric columns, or existing explicit-unit prototype evidence.
  The numeric part of a stock name is not financial evidence: use fields after its code.
  Major 1 below adds exact identity-cell recognition without numeric evidence.
  Date/code mentions alone never suffice. Identifiable headerless transactions remain
  unsupported/fail-closed; no previous-page columns or new broker parser are introduced.
- Exact regressions use one valid row plus (1) date + two separate numbers at quantity/
  price positions, and (2) headerless `2026.09.02 기준 KODEX 200(A069500) 안내입니다.`.
  Both now return READY with recognized 1 / parsed 1 and unchanged trade/cost values.
  Segmented prose, prose beneath a header and a purchase instruction with `KODEX 200`
  are also covered. Real generated PDF bytes pass through the unchanged local extractor
  for both findings. Headerless malformed-side and existing mandatory-field failures
  still reject the whole import. No existing testcase was removed or weakened.
- Final official H4: broker **29/29**, real PDF.js **4/4**, mobile **36/36**, selection
  **5/5**, navigation **5/5** = **79/79 PASS**, FAIL/SKIP 0, missing/extra/duplicate 0,
  guard/unexpected access 0 and restoration/patch restoration/cleanup true. Commands
  are the same five-entrypoint H4 selector and executables recorded in Slice 2 above.
- `--node-inventory-only`: **24 / 274**, missing/extra/duplicate 0; Python inventory
  remains **108 modules / 1079 direct / 18 registered probes**, missing/duplicate 0.
  Added subcases keep direct IDs/counts unchanged; inventory changes only the two test
  content hashes, with no new reads/guard/runner permission. Earlier Python 68/68 and
  coordinator 10/10 are historical Slice 2 evidence, not newly rerun for this frontend fix.
- `npm.cmd run lint`, the same process-only local-API `npm.cmd run build`, and
  `git diff --check`: PASS. No dependency, env, UI or backend changes were needed.
  Slice 1 BUY/SELL, null cost preservation and unknown-cost preparation rejection pass
  unchanged; brokerReviewInput.js has no content diff from the Slice 1 commit.
- This follow-up touches five existing pending paths only: brokerImport.js, its broker
  test, the pending PDF.js test, the two inventory hashes and this plan. The overall
  pending Slice 2 remains staged 0 / modified 13 / untracked 1 / unmerged 0 at f0ca1e72.

### Independent re-review Major 1 correction — 2026-10-17

- Cause: headerless recognition required a readable financial field before checking
  identity anchors. A real row with missing/malformed quantity and price was therefore
  omitted from recognizedRows, allowing the remaining valid page to become partial READY.
- The correction only adds an identity-cell candidate path in `isTossTransactionRow`:
  exact valid calendar-date item, exact allowed direction item and the existing explicit
  coded-instrument structure. This initial correction was further constrained by the
  observed header/cell geometry in the remaining Minor correction below. This path does
  not require any readable amount and does not use direction substrings inside prose.
  Candidate recognition is separate from successful parsing; no new headerless column
  inference is introduced. A recognized page without its own header remains fail-closed.
- Both exact findings (2026.09.03 / 판매 / KODEX 200(A069500), with no amounts or with
  불명 / 불명) now return `toss-incomplete`, empty trades and recognized 2 / parsed 1.
  Each is asserted in coordinate text-item tests and real in-memory synthetic PDF bytes
  through File/ArrayBuffer, unchanged local PDF.js extraction and the actual parser.
  Previous dated numeric footer, headerless prose, segmented prose and purchase-instruction
  regressions remain READY 1 / 1. Existing malformed rows, repeated headers, KODEX/TIGER,
  BUY/SELL, null costs and unknown-cost preparation rejection are unchanged and pass.
- Official H4 selectors: broker + PDF.js **33/33 PASS** (29/4), then mobile + selection
  + navigation **46/46 PASS** (36/5/5); distinct total **79/79**, FAIL/SKIP 0,
  missing/extra/duplicate 0, guard/unexpected access 0; restoration, patch restoration
  and cleanup true. Same approved Python/Node executables and selector options as above.
- Node inventory **24 entrypoints / 274 direct**, missing/extra/duplicate 0 and no missing
  dependencies. Python inventory unchanged: **108 modules / 1079 direct / 18 registered
  probes**, missing/duplicate 0. Only existing broker/PDF test subcases and their content
  hashes changed; no runner, guard, reads or direct inventory IDs changed for this fix.
- `npm.cmd run lint` and the same process-only local-API `npm.cmd run build`: exit 0
  (Vite 8.0.16, 1865 modules). No env file, backend, adapter, UI or dependency change.
  Earlier Python/coordinator test PASS counts remain historical, not rerun for this fix.
- Final `git diff --check`: PASS. Pending Slice 2 remains staged 0 / modified 13 /
  untracked 1 / unmerged 0 at f0ca1e72. Main still has only its protected README change
  with the recorded SHA; all 19 original feature dirty-file hashes match the baseline.
  No other worktree content, index, commit, push, merge or production state was changed.

### Independent re-review remaining Minor 1 — 2026-10-17

- Cause: the Major correction joined every item after the direction into an instrument
  prefix. In a split instruction it admitted `시 KODEX 200(A069500)` as the instrument,
  despite the intervening item not occupying the transaction's instrument-column start.
- Evidence: the existing coordinate fixture aligns date/side/instrument with its header
  at x = 57 / 107.9 / 173.1. The real synthetic PDF table uses 40 / 100 / 165. Existing
  `assignLayoutCells` uses nearest observed header columns; no fixed broker x constants,
  language blacklist, phrase heuristic or invented coordinate tolerance is introduced.
- Headerless identity-only recognition now requires the first date, side and instrument
  items to start at those exact observed header column x values, then validates the
  complete assigned cells using existing date/side/instrument helpers. Text between
  side and instrument cannot be silently prepended to the instrument anymore. Header
  geometry is retained solely for candidate completeness recognition, never for parsing
  a headerless page. Each page still needs its own header to produce actual trades.
- Both split instructions (구매 / 판매, with the exact 40/100/135/165/330 x positions)
  return READY, recognized 1 / parsed 1 and one unchanged trade in coordinate-items and
  real synthetic PDF File/ArrayBuffer extraction. The coordinate fixture's first-page
  identity header and row positions are remapped together to match the reproduction.
  Misaligned side-start and instrument-start cases also remain non-transactions in both
  extraction paths. No specific Korean instruction word is special-cased.
- Previous headerless missing and malformed amount cases still return `toss-incomplete`,
  empty trades and recognized 2 / parsed 1 in both paths. Existing normal BUY/SELL,
  repeated headers, KODEX/TIGER numeric names, dated numeric footer, single-item/segmented
  notes, mandatory-field corruption and Slice 1 fee/tax semantics all pass unchanged.
- Official H4: broker/PDF.js **33/33 PASS** (29/4), related mobile/selection/navigation
  **46/46 PASS** (36/5/5), total **79/79**. FAIL/SKIP 0, missing/extra/duplicate 0,
  guard/unexpected access 0; restoration, patch restoration and cleanup all true.
  Commands use the same five existing Node selectors and approved executables above.
- Node inventory remains **24 entrypoints / 274 direct**, missing/extra/duplicate 0 and
  no missing dependencies. Python inventory remains **108 modules / 1079 direct /
  18 registered probes**, missing/duplicate 0. Existing test IDs are unchanged; only
  broker/PDF test SHA entries change. Earlier Python/coordinator runs remain historical.
- `npm.cmd run lint` and the same process-only local-API `npm.cmd run build`: exit 0
  (Vite 8.0.16, 1865 modules). `git diff --check`: PASS. This fix touches only the parser,
  its two existing pending tests, their inventory hashes and this plan. No adapter,
  extractor, UI, backend, dependency, env or activation change; no actual AI call.
- Final preservation audit: staged 0 / modified 13 / untracked 1 / unmerged 0 at the
  unchanged Slice 1 HEAD. Only the five paths above differ from this task's starting
  hashes. Main retains only the protected README change and its recorded hash; all 19
  original feature dirty-file hashes still match. No staging, commit, push or merge.

### Structural row/column redesign — 2026-10-17 (historical HOLD)

- Previous exact-x rules conflated item boundaries with column identity: 0.25 px drift
  dropped real candidates, substring/whole-row joining absorbed prose into stock names,
  and single-item header matching missed PDF.js label fragments. Those coordinate rules
  and the layout string-anchor fallback have been removed, not extended with exceptions.
- Existing extractor/parser row grouping retains the observed 3 px y threshold. Fixtures
  separate trade rows by 25.2 px; synthetic header/trade baselines differ by 30 px. The
  new matrix includes +/-0.25 px y drift within one row. Extractor now retains PDF.js
  width in memory, alongside x/y/text; no upload or persistence is added.
- Header recognition consumes adjacent same-row fragments only while they form an exact
  prefix of a registered column label. Every item must belong to that closed grammar,
  with unique roles and all five required roles. Thus 종목명 + (종목코드), and other
  label splits, do not require natural-language inference. Normalized header role starts
  define half-open column bands using adjacent midpoints, with half-spacing outer bounds.
  No fixed broker x values, exact-x checks or oversized tolerance is used.
- Items are assigned to bands; date/side/instrument require complete single semantic
  text runs. PDF fragments join only within one observed previous-character advance
  (width / character count); distant fragments remain separate and cannot be prepended
  to a coded instrument. Fixtures without width retain explicit item-run boundaries.
  Numeric quantity/price evidence preserves damaged identity rows for completeness;
  valid identity roles need no numeric fields. Text-only prototype recognition remains
  separate from the coordinate model, preserving its existing contract.
- Headerless pages use the last observed model solely for candidate classification;
  they still cannot produce trades without their own header. Recognized but unparsed
  rows force whole import rejection. Costs, time rules, independence and review adapter
  are unchanged. No new broker, UI or production request behavior is introduced.
- Coordinate corpus passes: both sides x missing/malformed amounts x nine offset vectors
  (36 combinations, including every requested +0.25 variant, negative/all-axis variants,
  and in-band 120/185 starts), split instrument/all-label repeated headers, split prose
  with fragments in side/instrument bands and truly out-of-band identity placements.
  Old tests treating 120/185 as inherently non-transactional were corrected: those starts
  lie within the observed bands and must remain candidates, rather than recreating exact-x.
  Existing numeric names, footer/summary exclusions and Slice 1 semantics also pass.
- First official H4 broker + PDF.js selector: **32 PASS / 1 FAIL**, exit 1, exact direct
  coverage 33 with missing/extra/duplicate 0. Broker **29/29 PASS**. PDF.js **3/4 PASS**:
  all 36 headerless floating/malformed binary combinations, image/invalid/password paths
  pass. The positive/split-header testcase failed before reaching its new split-prose
  and split-stock-name subcases; those binary checks are NOT RUN in this redesign.
- A test-local catch logs the sanitized exception stack without changing H4 reporter,
  guard or runner. The second official PDF-only diagnostic again returned **3/4**, exit 1:
  `AssertionError [ERR_ASSERTION]: PDF.js retained the split instrument header`, at
  `frontend/scripts/broker-pdf-extraction.test.js:118`. The fixture did not establish
  the exact separate item required by its assertion. PDF.js coalescing or item-string
  normalization is plausible, but the actual extracted item array was not captured,
  so the precise cause remains unconfirmed. This is a binary fixture assertion failure,
  not evidence of a production parser defect;
  binary split-header success is nevertheless NOT verified. No third retry or conditional
  product patch was made. H4 guard/unexpected access 0; restoration/cleanup passed in both.
- Unaffected official mobile/selection/navigation selectors: **46/46 PASS** (36/5/5).
  Node inventory **24 / 274**, missing/extra/duplicate 0, dependencies complete. Python
  inventory **108 modules / 1079 direct / 18 registered probes**, missing/duplicate 0;
  Python direct tests and full suites were not rerun. Lint and the same process-only
  local-API build passed (Vite 8.0.16 / 1865 modules). No env file or dependency change.
- Final diff check passes. Git: staged 0 / modified 14 / untracked 1 / unmerged 0;
  same branch/HEAD. Six paths changed from this task's starting hashes: parser,
  extractor width, two tests, inventory hashes and plan. Main's protected README hash
  is unchanged; all 19 original feature dirty-file hashes match. Other worktrees were
  not modified. No stage/commit/push/merge/rebase or third failed-PDF execution.

### Approved PDF.js fixture/test boundary — 2026-10-17

- The separate extraction diagnosis confirmed that the original adjacent drawing fragments
  become one `종목명(종목코드)` PDF.js item (x 165 / y 500 / width 22.5 / raw height 5).
  Separate BT/ET objects alone did not establish separate items. A 12 px inter-fragment
  gap and a larger baseline difference each preserved two items in three diagnostic
  repetitions. This evidence concerns pinned local PDF.js 6.2.108, not a universal
  segmentation guarantee. The diagnosis changed no product or regression expectation.
- This authorized correction changes only the PDF test, its inventory hash and this plan.
  `brokerImport.js`, the production extractor, UI, adapter and existing coordinate unit
  tests are unchanged from this task's starting hashes. Parser-unit corpus already
  explicitly covers split instrument/all-role headers, floating +/-0.25 identities,
  split purchase/sale prose, malformed headerless rejection, footer/summary and costs.
- Ordinary binary fixtures now require extracted header text, pages and expected final
  parser results, without fixing how PDF.js segments their source drawing fragments.
  The original merged instrument header and adjacent-fragment/repeated-header fixtures
  remain, with unchanged trade/cost expectations. No parser condition was relaxed.
- A distinct deliberately split-header fixture uses the diagnosed 12 px gap after the
  three-character fragment's width in the generator's fixed 5 pt / 500-unit font.
  It first asserts the two actual extracted fragment strings, then READY, complete
  2/2 rows and exact symbol/BUY/SELL/price/quantity/fee/tax results. Both unshifted and
  whole-document x+23 variants pass, demonstrating independence from fixed parser x.
- First official H4 broker/PDF selector: **33/33 PASS** (29/4), exit 0. The binary test
  now reaches and passes every previously blocked subcase: merged/deliberately split
  repeated headers, split KODEX name, purchase/sale explanations, numeric footer and
  mixed FX rejection. Its other cases preserve all 36 floating/missing/malformed
  headerless combinations (whole reject), image-only/no OCR, invalid/encrypted rejection
  and recovery. No test PDF is written/uploaded, and the real File -> ArrayBuffer ->
  unchanged production extractor -> bundled local PDF.js/worker -> parser path runs.
- Official mobile/selection/navigation selectors: **46/46 PASS** (36/5/5), exit 0.
  Distinct related Node total **79/79**, FAIL/SKIP 0, missing/extra/duplicate 0;
  guard/unexpected access 0, restoration/patch restoration/cleanup all true. The five
  existing official H4 selectors and approved executable paths above are unchanged.
- All representative binary subcases live in the already registered
  `test:broker-pdf-extraction` entrypoint, not only independent probes. No direct IDs,
  reads, guard or runner changes: its content SHA alone is refreshed in inventory.
  Node inventory **24 / 274**, missing/extra/duplicate 0, dependencies complete;
  Python inventory **108 modules / 1079 direct / 18 registered probes**, missing/duplicate
  0. Python direct tests and full suites were not rerun for this test-only correction.
- `npm.cmd run lint` and the same process-only local-API `npm.cmd run build`: exit 0
  (Vite 8.0.16 / 1865 modules). No env file, dependency, production setting or actual AI
  call changed. Expected PDF.js warnings remain limited to optional canvas and intentionally
  invalid input. This new fixture approach passed on its first verification execution.
- Final preservation/diff audit: only PDF test, its inventory hash and this plan changed
  from the task's starting hashes. All production files and parser-unit tests are byte
  identical to that starting state. Main's protected README hash and all 19 original
  feature dirty-file hashes are unchanged. Staged 0 / modified 14 / untracked 1 /
  unmerged 0 at the same branch/HEAD; `git diff --check` passes. No stage/commit/push/merge.

### Tri-state completeness classification — 2026-10-17

- Latest Major cause: the boolean gate required a complete identity triple or two
  successfully parsed amounts. Compound missing/invalid fields therefore bypassed
  recognition before parsing could reject them. In particular side/instrument/quantity
  with no date/price (A), and date/side/price with invalid code and no quantity (B), were
  silently dropped. The previous boolean function has been removed.
- Normalize each row into existing column bands, coherent cell text/runs and independent
  occupied required roles. Shape admission precedes parsing: a dense five-role footprint,
  a strong three-identity footprint, or a partial grid with at least three independent
  roles, numeric-looking financial occupancy and execution/date context. Numeric-looking
  is lexical geometry evidence, not a successful numeric parse. Stock-name digits outside
  financial bands never count as quantity/price. No new word blacklist or exact-x rule.
- `classifyTossLayoutRow` returns exactly `transaction` (a fully parsed trade),
  `incomplete_transaction` (admitted row shape but missing/invalid required values), or
  `non_transaction`. The collector explicitly consumes these states: the first two
  increment recognizedRows; incomplete sets whole-import failure; only transaction can
  publish a trade. Any incomplete row exposes an empty trade list. The public response
  shape, cost null/zero meaning, preparation blocker, IDs and independence are unchanged.
- Headerless handling remains stricter: strong identity roles, or a dense footprint with
  two identity roles and financial slots, can identify an incomplete continuation using
  prior geometry. It never invokes trade parsing or publishes a headerless transaction.
  Sparse compound headerless rows outside that evidence remain unsupported, not newly
  parsed. Existing floating/malformed-side/headerless regressions continue to pass.
- Explicit safe boundary: date + quantity/price without side/instrument cannot be
  distinguished from a dated numeric footer. Instrument + quantity/price without date/
  side cannot be distinguished from holdings. Empty rows, lone role cells, no trusted
  geometry and other unidentifiable shapes are not guessed as trades. These limitations
  mean this does not certify recovery/completeness for arbitrarily destroyed statements.
  A sentence observationally identical to a table-shaped record also cannot be resolved
  semantically without further source evidence. The tested split prose has separate
  runs/role mismatch and remains non-transactional.
- New shared sanitized `frontend/scripts/fixtures/broker-row-damage.js` supplies 39
  rows to both official geometry and actual binary tests: 10 single missing/invalid,
  20 pair missing/invalid, 6 named Major/mixed combinations, one valid transaction and
  two severely unidentifiable shapes. Expected classification totals are transaction 1,
  incomplete 34, non-transaction 4; the latter includes the two ambiguous missing pairs
  above, not failed trades claimed as detected. All 34 detectable damaged rows, mixed
  with one valid trade, yield `toss-incomplete`, recognized/parsed 2/1 and empty trades.
  The same matrix includes subpixel row grouping and +0.25 x drift in its fixtures.
- Latest A/B and representative single/double damage pass File -> ArrayBuffer ->
  unchanged production pdfTextExtractor -> bundled local PDF.js -> production parser.
  No PDF is persisted/uploaded and no network/CDN is used. The existing merged/split
  repeated header, numeric instrument names, split purchase/sale prose, footer/summary,
  all 36 headerless floating cases and Slice 1 cost/side/time regressions also pass.
- Official H4 broker/PDF: **35/35 PASS** (30/5), first implementation verification.
  Related mobile/selection/navigation: **46/46 PASS** (36/5/5). Distinct Node total
  **81/81**, FAIL/SKIP 0, missing/extra/duplicate 0, guard/unexpected access 0;
  restoration/patch restoration/cleanup all true. No failure-driven condition patch.
- Python official H4 `tests.test_full_test_entrypoint tests.test_quick_verify_docs`:
  **23/23 PASS** (16/7), failures/errors/skips 0, inventory issues empty and lifecycle
  restoration/cleanup true. The trusted coordinator's top-level access counters are
  null, not claimed as numeric zero; its nested isolation contracts pass. Full suites
  and unrelated backend modules were not rerun.
- Two new direct IDs and the exact shared fixture read are registered in existing
  broker/PDF entries; no guard/runner permission changes. Node inventory **24 / 276**,
  missing/extra/duplicate 0, dependencies complete. Python remains **108 modules /
  1079 direct / 18 registered probes**, missing/duplicate 0. Current count docs and the
  two existing coordinator/docs assertions are synchronized; historical evidence stays.
- `npm.cmd run lint`, the same process-only local-API `npm.cmd run build` (Vite 8.0.16 /
  1865 modules) and `git diff --check`: PASS. No model/provider/production/environment/
  entitlement, review-display or actual AI change. The extractor and UI were not edited.
- Final audit: staged 0 / modified 14 / untracked 2 / unmerged 0 at unchanged f0ca1e72.
  This task changes nine existing paths plus the new shared fixture. Existing unrelated
  hunks/files remain; extractor/UI/H4 runner/isolation guard hashes match task start.
  Main retains only its protected README change and recorded SHA; all 19 original feature
  dirty-file hashes match the preserved baseline. Final diff check passes. Current-count
  docs now carry the actual 2026-10-17 date; docs H4 was rechecked 7/7 after that edit,
  not added again to the distinct Python 23 count. No stage/commit/push/merge/rebase.

### Final tri-state review Minor: occupancy is not identity — 2026-10-17

- Cause: the partial-grid shape admitted a date, occupied side slot and two numeric slots
  without requiring a transaction identity. A summary/balance/arbitrary label therefore
  counted as an incomplete trade. No phrase blacklist is an adequate structural fix.
- On header-bearing pages, shape classification now separately requires at least one
  existing identity anchor: exact supported side vocabulary or a valid Toss instrument
  cell. Only then are the unchanged table shapes and required-field parser consulted.
  Occupancy never supplies that authority. Headerless handling, column/run geometry,
  costs, preparation, time rules, UI and extractor are unchanged by this correction.
- The original 39-case matrix remains exercised in both paths. Its invalid side AND
  invalid instrument pair deliberately changes to non-transaction: no trusted identity
  survives. The older both-identity-destroyed assertion is likewise explicit about READY
  1/1, not silently removed. This follows the approved non-inference boundary, rather
  than claiming arbitrary destruction is detectable. Single-anchor damage still rejects.
- Six shared official subcases cover summary labels `합계`, `잔고`, an arbitrary non-side
  label, a dense five-slot row with neither identity, malformed side with valid instrument,
  and valid side with malformed instrument. Combined corpus: 45 rows (transaction 1,
  incomplete 35, non-transaction 9). Label cases preserve READY, recognized/parsed 1/1;
  either surviving identity preserves incomplete, recognized/parsed 2/1 and empty trades.
  Major A/B and side+quantity / price+quantity damage remain whole rejects.
- Both production-parser geometry tests and real File -> ArrayBuffer -> production
  extractor -> local PDF.js -> parser execute the shared cases. New binary identity
  cases sit below the same recognized header as the good row, including exact
  x=40/100/340/430 label reproductions; original floating matrix remains unchanged.
  No PDF persistence/upload, CDN/network, new parser or actual AI request is introduced.
- Official H4 broker/PDF selectors: **35/35 PASS** (30/5); related mobile/selection/
  navigation selectors: **46/46 PASS** (36/5/5). Distinct Node **81/81**, FAIL/SKIP 0,
  coverage missing/extra/duplicate 0, guard/unexpected access 0; restoration, patch
  restoration and cleanup true. All passed on this correction's first test execution.
- Official Python `tests.test_full_test_entrypoint tests.test_quick_verify_docs`:
  **23/23 PASS** (16/7), FAIL/ERROR/SKIP 0, inventory issues empty and all lifecycle
  restoration/cleanup true. Trusted coordinator counters are null, not numeric-zero
  access claims; guarded docs counters are zero. No full suite was run.
- Official inventories: Node **24 entrypoints / 276 direct**, missing/extra/duplicate 0,
  dependencies complete; Python **108 modules / 1079 direct / 18 registered probes**,
  missing/duplicates/expected skips 0. No new direct IDs/reads/guard/runner permissions;
  only the two changed test source hashes are refreshed. Lint and process-only local-API
  frontend build pass (Vite 8.0.16 / 1865 modules); no env file or configuration change.
- Initial sandboxed Git status failed with `this operation must be run in a work tree`;
  read-only elevated inspection confirmed the correct branch/HEAD and preserved dirty
  state. No Git configuration, worktree metadata or content workaround was applied.
- Final preservation audit: staged 0 / modified 14 / untracked 2 / unmerged 0 at the
  unchanged Slice 1 HEAD. Only parser, shared fixture, two tests, their inventory hashes
  and this plan differ from this correction's start. All other pending files are byte
  identical; main's protected README SHA and the original feature's 19 dirty-file
  hashes/status are unchanged. `git diff --check` passes; no Git mutation or other
  worktree changes occurred. Independent re-verification remains required.

## Slice 3 confirmation UX — 2026-10-17

- The previous list used the initial parser order while manual time changes lived in a
  separate ID-keyed map. Confirmation now overlays current times and uses the existing
  canonical descending date/time/source-order helper; blank/unknown times normalize to
  null for ordering. Source rows, sourceIndex, IDs and selection Set are never reindexed.
- The adapter's existing single-row checks are shared with confirmation. Six-digit code
  and nonblank name are already mandatory downstream; generic name-only candidates
  actually have null symbols. Unknown/non-finite/negative fee or tax already blocks
  preparation. No new admission restriction or zero substitution is introduced.
- Rows show the preparation issue and explicit unknown cost labels. Only selected
  invalid rows disable transfer; removing them permits the remaining valid selection.
  The actual handler repeats the guard. Mixed-side required times keep their existing
  selected-group validator; BUY-only/SELL-only time remains optional.
- Both embedded and standalone views describe Toss domestic support, limited generic
  text recognition, unsupported foreign/FX/scanned/encrypted PDFs and local-only original
  PDF handling. Broker confirmation and the existing journal preview no longer promise
  a reason/memo entry UI that only the direct-input form has. TradingJournal changes
  only that sentence. No issuer expansion or editable trade/cost fields were added.
- Existing VM harness renders the actual BrokerImport component and invokes original
  handlers with synthetic state, without API/storage/AI bindings. Four registered direct
  cases cover shared adapter parity, sorting/identity, blockers/deselection and mixed-side
  times/select-all. Results are recorded below.

### Slice 3 verification

- Official H4 Node selectors `test:broker-import`, `test:broker-pdf-extraction`,
  `test:journal-mobile-ux`, `test:review-selection`, `test:app-navigation`,
  `test:legacy-review-cross-contract`, `test:ai-chart-source`: **142/142 PASS**
  (31/5/39/5/5/11/46), FAIL/SKIP 0. Expected/observed 142; missing/extra/duplicate 0.
  All guarded entrypoints report violations/unexpected access 0 and successful
  restoration/patch restoration/cleanup. Actual PDF binary and canonical review/chart
  regressions remain intact; no live AI/provider or production request was made.
- Official Python H4 `tests.test_full_test_entrypoint tests.test_quick_verify_docs`:
  **23/23 PASS** (16/7), FAIL/ERROR/SKIP 0, inventory issues empty and lifecycle cleanup
  successful. Coordinator-owned top-level access counters are null; its nested guard
  contracts pass. Guarded docs report violations/unexpected 0.
- Official `--node-inventory-only`: **24 entrypoints / 280 direct**, missing/extra/
  duplicate 0, missing source dependencies empty. Four new Node IDs are registered;
  affected test and TradingJournal snapshot hashes are refreshed without new reads or
  guard permissions. `--inventory-only`: unchanged **108 Python modules / 1079 direct /
  18 registered child probes**, missing/duplicates/expected skips 0.
- Initial Node run was 84/85 because the existing user-copy policy rejects the literal
  technical term OCR. Korean unsupported scanned/photo wording resolved it, followed by
  85/85 PASS. The later journal copy change required exact raw source snapshot refresh
  for the three existing chart/legacy/mobile entries. A verification batch stopped at
  that hash guard before the final successful rerun; no guard was relaxed.
- Lint initially found two no-useless-catch errors in the already committed Slice 2 PDF
  test (confirmed unchanged against HEAD). Removed only its redundant rethrow wrappers
  and adjusted indentation; assertions and rejection propagation remain unchanged.
  Its five official binary cases pass, and its manifest source hash is refreshed.
- `npm.cmd run lint` and `npm.cmd run build`: **PASS**. Build uses the existing approved
  process-only local API settings recorded above, Vite 8.0.16 / 1865 modules; only ignored
  dist output is generated. No env-file, installed dependency or Android sync change.
  `git diff --check`: **PASS**.
- Preservation audit: main retains only its existing Play README change and unchanged
  SHA-256; the original feature worktree retains HEAD, 9 modified / 10 untracked and
  all 19 file hashes. Target remains at `f4189a2b7210a353e8f310409ee1ffa3c749edbd` with
  staged 0 / modified 13 / untracked 0 / unmerged 0. Parser, extractor, shared damage
  fixtures, backend and environment sources have no diff. No stage/commit/push/merge.

## Remaining / Next step

Obtain independent review of Slice 3's confirmation UX and shared adapter validation
before commit or any further slice. Do not modify parser/completeness or other worktrees.
Unknown-cost statements (including generic rows with no costs) remain blocked until
explicit costs are available; do not bypass this using zero. Cost editing is not added.
Headerless transaction continuations, generic multi-token numeric names, OCR and password
PDFs remain unsupported. Completeness covers recognizable supported table/text rows,
not recovery of arbitrary unrecognized layouts or content that yielded no text.
Real Toss PDF corpus/browser Worker/Android device checks, field and
memo editing remain separate follow-ups. No rollout/activation or actual AI call occurred.
