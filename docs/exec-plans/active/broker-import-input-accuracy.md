# Broker import input accuracy — Slice 1

## Goal and scope

Fix explicit trade-side mapping and preserve PDF fee/tax meaning through the existing
memory preparation and canonical review request. Worktree `broker-import-input-accuracy`,
branch `fix/broker-import-input-accuracy`, base `e1629217858d948ce821c9e31241711dc613c64e`.
The new worktree was created clean. Main's existing Play README and the original
feature worktree (0 staged / 9 modified / 10 untracked) remain protected.

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
- Use synthetic coordinate fixtures only. No real PDF, new binary fixture, completeness,
  manual-time sorting, field editing, rollout, commit/push/merge or other worktree writes.

## Current status

- [x] Confirm exact base and create the requested clean isolated worktree.
- [x] Trace parser → candidate → adapter → actual review handler → numeric backend contract.
- [x] Implement and verify side/cost regressions through official H4 selectors.
- [x] Run focused backend/Node regression, inventory and lint/build.
- [x] Complete final preservation/whitespace audit.
- [ ] Independent review.

## Verification

Tests use H4-owned synthetic data and denied external I/O. Build/lint use only existing
approved dependencies and local ignored outputs; no env-file or production changes.
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

## Remaining / Next step

Implementation and focused verification are complete. Obtain independent review; do not commit.
Unknown-cost statements (including generic rows with no costs) remain blocked until
explicit costs are available; do not bypass this using zero. Cost editing is not added.
Real PDF/device checks, completeness, sorting and editing remain separate follow-ups.
