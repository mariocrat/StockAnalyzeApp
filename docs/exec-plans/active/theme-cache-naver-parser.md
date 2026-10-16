# Naver theme cache parser hotfix

## Goal

Restore non-empty Naver theme membership ingestion and prevent empty or failed refreshes from replacing a good cache.

## Scope

- Worktree: `D:/Project/Vibe/StockBoda.worktrees/theme-cache-naver-parser`.
- Branch: `fix/theme-cache-naver-parser`; base HEAD: `15578b2b23d8254b882458ee9e35d11098ba76d6`.
- Change only the theme ingestion/cache validation, focused synthetic tests, required H4 inventory/count metadata, and this plan.
- Main's existing Play README modification and the original feature worktree remain untouched.

## Decisions

- The former `finance.naver.com/sise/theme.naver` redirects to a client-rendered UTF-8 `stock.naver.com` page. Its server HTML has no theme table or old detail links.
- On 2026-10-16, the page-referenced `58268-c95850c12ee285fe.js` modules 64983/57553 exposed the actual requests below; one public ranking and one constituent response were independently fetched successfully.
- Rankings: `/api/stockSecurity/rankings/v2/domestic/themes`, `sortType=changeRate`, `size=100`, `period=daily`. Response: `items` with `code`/`name`, plus `hasNext`/`cursor`.
- Constituents: `/api/domestic/market/theme/{code}/stocklist`, `sortType=tradingValue`, `sortDirection=desc`, `size=100`. Response: `items` with `itemCode`/`itemName`/`krx.changeRate`, plus `hasNext`/`cursor`. The page normalizes an `A` prefix on six-digit stock codes.
- Decode these responses as UTF-8. Preserve `(themes, names, theme_returns_map)` and existing bounded worker configuration.
- Reuse valid existing seven-day theme caches. Ignore poisoned empty cache payloads. Failed refreshes must raise, must not be memoized as success, and must not write theme membership or period caches.
- Preserve existing expired last-good files and the existing standard-period fallback behavior; do not invent a new freshness policy or fabricate example themes on failure.
- Every ranked theme must have complete non-empty detail pages. One empty/malformed detail (including an empty continuation page) fails the entire refresh before any cache publication; no ranked theme may be skipped to produce a smaller successful result.

## Current Status

- [x] Exact base/branch/path checked; new worktree began clean; main README hash unchanged.
- [x] Current public page/script/JSON evidence inspected without calling the production API.
- [x] Paginated UTF-8 JSON parser and cache admission implemented in `backend/core/data_fetcher.py`; no frontend/main-route changes.
- [x] Focused H4 parser/cache/worker/mobile/coordinator regression and source inventory passed.
- [x] Documentation regression and final diff/worktree-protection checks passed.
- [x] Original HOLD/Major 1 corrected: empty/malformed ranked details fail the whole refresh; targeted H4 and separate live parser revalidation passed.
- [ ] Independent re-review of the correction; commit and production deployment require later approval.

## Verification

- Public page: HTTP 200, UTF-8, no HTML theme tables / old-style detail links.
- Page-used ranking response: HTTP 200, 100 items and a continuation cursor.
- Page-used constituent response: HTTP 200, non-empty items with the observed fields above.
- Automated tests use minimized synthetic responses only, with H4-owned caches and mocked external I/O.
- Initial pre-Major verification, 2026-10-16, hotfix worktree at the base HEAD plus working diff, existing approved Python `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe`:
  - `-I -X utf8 -B tests/run_isolated_tests.py --inventory-only`: PASS; 108 modules / 1,078 direct, baseline 35 / 1,005 / 22 plus Stage 1 16, 18 separate child probes; missing/duplicate 0. No isolation allowlist, coordinator execution policy or timeout was changed.
  - `-I -X utf8 -B tests/run_isolated_tests.py tests.test_theme_cache_memory`: **11/11 PASS**, including eight new direct cases. Minimized synthetic JSON fixes field shape, pagination on both request types, UTF-8 Korean strings, A-prefix normalization, absent quote handling, corrupt/empty response rejection, stale last-good file preservation, recovery after a failed call, and all four period warm-up success/failure.
  - `-I -X utf8 -B tests/run_isolated_tests.py tests.test_theme_cache_workers tests.test_mobile_runtime_recovery tests.test_full_test_entrypoint`: **26/26 PASS** (4 + 6 + 16). Existing bounded executor and stale-period fallback contracts remain green.
  - Guarded reports: unexpected access / isolation violations **0**, restoration / patch restoration / cleanup **true**. Coordinator report has the required null direct violation counters and passed its nested negative-probe contracts; synthetic negative/timeout fixtures are not actual failed test runs.
  - Separate public-source probe: exact production parser function bodies were selected with AST (decorator excluded), with cache read/write supplied in memory, default bounded workers 8, and no application import. One complete live Naver crawl returned **264 themes / 2,393 unique stocks / 6,524 memberships and rates** in **7.321 seconds**; validated payload publication **1 in memory**, filesystem cache writes **0**. This is separate from the network-blocked H4 tests, and did not contact the production backend.
  - `-I -X utf8 -B tests/run_isolated_tests.py tests.test_quick_verify_docs`: final **7/7 PASS**. The first attempt was 6 PASS / 1 FAIL because `docs/quick_verify.md` still stated 1,070; synchronized only the current counts in both verification docs, preserving historical evidence. No test assertion was weakened. Total final focused evidence: **44 unique direct tests PASS**; no full suite or build was run.
  - Final full diff review and `git diff --check`: PASS. Hotfix staged 0 / tracked modified 7 / untracked plan 1 / unmerged 0; changes are the parser, synthetic tests, necessary inventory/count metadata, and plan only.
  - Main remains at the base HEAD with only its pre-existing Play README modification; SHA-256 remains `5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328`. Original feature worktree remains tracked modified 9 / untracked 10. No other worktree content was edited.

### Major correction revalidation

- Before the correction, the existing selected H4 invalid-constituents case reproduced `RuntimeError not raised` for partial details. The first partial success also became memoized and masked subsequent invalid subcases. This intentional red regression had unexpected access 0 and successful restoration/cleanup.
- Added empty single-theme detail, empty final continuation, and malformed detail subcases without new direct test IDs. Failure assertions compare membership and all four period files' raw bytes and nanosecond mtimes, require zero writes/chart requests, and verify a healthy subsequent retry without clearing the memoization cache.
- Official `-I -X utf8 -B tests/run_isolated_tests.py tests.test_theme_cache_memory`: **11/11 PASS** after the correction.
- Official `-I -X utf8 -B tests/run_isolated_tests.py tests.test_theme_cache_workers tests.test_mobile_runtime_recovery`: **10/10 PASS** (4 + 6). Current post-correction focused total: **21/21 PASS**, failures/errors/skips 0, unexpected access/isolation violations 0, restoration/patch restoration/cleanup true.
- Official `-I -X utf8 -B tests/run_isolated_tests.py --inventory-only`: PASS, **108 modules / 1,078 direct tests**, missing/duplicate 0, no inventory changes for this correction. `git diff --check`: PASS.
- Separate live public-source probe using the exact parser bodies with cache I/O replaced in memory: **264 ranked / 264 returned themes**, 2,393 unique stocks, 6,524 memberships/rates, **7.135 seconds**; one in-memory publication, zero filesystem cache writes. No production backend request or recovery claim.
- Only the parser, existing focused test file, and this plan received additional edits for the Major; coordinator, inventory, and production settings were not changed.

## Remaining / Unverified

- Independent review and later explicit commit/deployment approval remain pending.
- Actual Render logs, disk state and deployment revision remain unverified; local source evidence is not a production recovery claim.
- The existing seven-day membership TTL and standard-period fallback freshness are unchanged. An expired last-good membership file is preserved on failure, not relabeled as fresh or silently served as a new successful refresh.

## Next Step

Obtain independent review of these eight uncommitted hotfix files before requesting commit approval. A later authorized production deployment must verify warm-up completion and all four standard-period API responses.

## Out of Scope

Production API calls/settings/deployment, frontend, new dependencies, Git staging/commit/push/merge/rebase, other worktree edits, and broad cache/retention changes.
