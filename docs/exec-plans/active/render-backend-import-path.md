# Render backend import namespace repair

## Goal

Import `main:app` from the Render `backend` working directory with a single `core.*` runtime namespace and no dependency on the repository parent being importable.

## Scope

- Worktree: `D:/Project/Vibe/StockBoda.worktrees/render-backend-import-path`.
- Branch: `fix/render-backend-import-path`; base: `ea756820669e07d4708ae2316fa6310cebfe5e07`.
- Runtime import statements, matching script/test import and patch targets, isolated startup regression, inventory/count documentation only.
- Main's existing Play README and all other worktree content are protected.

## Decisions

- Render keeps `cd backend && uvicorn main:app ...`; no PYTHONPATH/env/start-command change.
- All runtime dependencies use `core.*`. No compatibility alias loader or dual module namespace.
- Test/bootstrap imports use the same namespace so DTO classes, receipts, patches and process-local state retain identity.
- Startup reproduction uses the official H4 storage boundary, removes repository-root import visibility and cached application modules, denies `backend` imports, and calls Uvicorn's real `import_from_string("main:app")` without starting lifespan/server.
- Existing pure-layer/import guards retain their exact allowed edges and negative coverage.

## Current Status

- [x] Approved main/base verified; isolated worktree created clean.
- [x] Mixed `core.*` and `backend.core.*` imports identified across the startup/review graph.
- [x] Startup regression reproduced before correction at `main -> core.ai_review_v2 -> core.journal_chart -> backend.core.review_source_contract`.
- [x] All backend imports normalized; obsolete namespace fallback removed; application import succeeds with `backend` imports denied.
- [x] Namespace normalization and focused verification complete; final complete coverage is 680 Python direct tests and 46 Node tests.
- [ ] Independent verification and later commit/deployment approval.

## Verification

- Official approved Python: `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe`, `-I -X utf8 -B tests/run_isolated_tests.py`; no dependency installation or timeout change.
- Red reproduction: the registered Render-cwd case failed with `ModuleNotFoundError` at `journal_chart.py`; unexpected access 0, restoration/patch restoration/cleanup true.
- After correction the real Uvicorn app importer succeeds with repository root removed from `sys.path`, fresh application modules, `backend` explicitly unavailable, DB connection/thread start denied, and no second module/class identity.
- Production AST equivalence audit: all **33 changed runtime modules** match HEAD after only import namespace and obsolete namespace-fallback normalization. Four standalone backend scripts select the backend package root. Business behavior and activation gate are unchanged.
- Exact text audit: **61 test files** outside the explicit bootstrap/guard/new-case/metadata edits match HEAD plus namespace replacements only.
- Tests/fixtures/patch targets use canonical `core.*` too; no test alias loader or production PYTHONPATH workaround. The 65 existing Python files referencing the old namespace received mechanical path replacements; H4 bootstrap and exact import guards were adjusted without widening I/O permissions or permitted runtime edges.
- Python inventory: **108 modules / 1,079 direct**, baseline **36 / 1,005 / 22**, Stage 1 16, 18 child probes; missing/duplicates/expected skips 0. One new A1 startup test accounts for the increase. Current-count docs updated, historical evidence retained.
- Node inventory: **23 entrypoints / 259 direct**, missing/extra/duplicate 0, missing source dependencies 0.
- Startup/runtime/storage group **34/34 PASS**; review display/durable guard group **61/61 PASS**; source/theme/OAuth group **123/123 PASS**; H4 bootstrap/coordinator/release/docs group **44/44 PASS**. Expected negative-isolation cases in runtime environment recorded 22 denials with unexpected 0; coordinator negative probes passed their contracts.
- Node `--node-entrypoint test:ai-chart-source --node-executable "C:/Program Files/nodejs/node.exe"`: **46/46 PASS**, missing/extra/duplicate 0, guard/unexpected 0, cleanup/restoration true. All five real backend handoff stages passed (basic, advanced, failures, titles, paired). Initial post-migration attempt failed before Node execution because the standalone chart child imported `core` before its H4 bootstrap; reordered those two imports and the official rerun passed. No dependencies/guards/timeouts were changed.
- Execution/negotiation group **115/115 PASS**: activation 14, execution cache 14, idempotency 14, capability negotiation 14, client gate 21, route compatibility 38. Guarded unexpected access/violations 0, restoration/patch restoration/cleanup true. Idempotency testcase work took 124.141s within its existing 180s budget; route work took 245.894s within its existing 360s budget.
- History batch exited nonzero: whole-module writer/content coverage was interrupted, including writer output stopping during `test_twenty_producer_variants_save_and_read_exact_approved_parameters`. These modules already have documented aggregate-120s limitations in the base migration plan (strict writer 102.26s testcase work; content 100.90s plus roughly 30s shared setup). Do not claim a new production defect or a precise environmental cause from this interrupted run. No whole-module retry or timeout change was made.
- Complete paired history **23/23**, producer **8/8**, safety finalization **2/2**, and refund **13/13** PASS reports were captured in that batch. Only complete per-module reports contribute to the final count.
- Following the existing documented official selector strategy, strict writer **23/23 PASS** in 4/4/4/4/4/3 groups and content **25/25 PASS** in 5/5/5/5/2/2/1 groups. No whole-command repeat, timeout change or direct unittest bypass. Longest selected testcase: strict writer 26.350s; content 38.444s. All registered cases covered once in the final count; every selected child has unexpected/violations 0, inventory issues empty and restoration/patch restoration/cleanup true.
- To recover complete lifecycle evidence from the long batch's truncated output, rechecked only the six unresolved modules: approved writer 24, prepared content 18, history adapter 44, finalizer compatibility 18, envelope 26, structured review 79: **209/209 PASS**. Adapter's eight intentional rejection probes preserve their expected contract, with unexpected 0.
- Final complete distinct coverage: **680/680 Python direct PASS in 37 modules** (34 startup/runtime/storage + 61 review guards + 115 execution/negotiation + 303 history/finalizer + 123 source/theme/OAuth + 44 H4/bootstrap/release/docs). Repeated diagnostic/selected invocations and Node's internal Python handoff stages are not double-counted. FAIL/ERROR/unexpected SKIP 0 in these completed reports; unexpected accesses 0 and all restoration/patch restoration/cleanup true. Runtime environment and adapter negative tests deliberately record 22 + 8 expected denials; coordinator nested negative probes retain their contract.
- Final Node evidence: **46/46 PASS** with five backend handoff stages and all guard/coverage/lifecycle checks satisfied. Python/Node source inventory and changed Python syntax validation PASS; runtime AST equivalence and 61-file mechanical test audit PASS. No full suite/build/live API was run.
- Main still points to the approved base and has only the pre-existing Play README modification; its SHA-256 remains `5FDEEF682DCF0890894E8F170CFCCC3C4A5B1CC811850BC38E6C42F4E8F52328`. No other worktree content was edited. Hotfix scope: 37 backend files, 70 test/inventory files, two count documents and this new plan. Staging/commit/push/deploy remain unperformed.
- Final `git diff --check`: PASS; complete backend AST import audit: PASS. Hotfix HEAD remains the approved base; staged 0 / tracked modified 109 / untracked plan 1 / unmerged 0.

## Remaining / Unverified

- Actual Render startup after a later authorized deployment remains unverified.
- Whole strict-writer/content modules completing within the unchanged 120s budget are not claimed; all 48 cases are verified using the existing official grouped selectors.

## Next Step

Obtain independent verification of the namespace-only runtime diff, the canonical test/bootstrap migration and completed H4 evidence before requesting commit approval. Actual Render startup/health follows a separately authorized deployment.

## Out of Scope

Business behavior changes, activation changes, new dependencies, production settings/DB/deployment, staging/commit/push/merge/rebase, other worktree edits.
