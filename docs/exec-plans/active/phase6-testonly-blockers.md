# Phase 6 official TestOnly blockers — 2026-10-10

## Goal

Reproduce the current official TestOnly failures, repair only stale test contracts
and observed module deadlines, then obtain official TestOnly exit 0.

## Scope

Worktree D:/Project/Vibe/StockBoda.worktrees/structured-trade-review, branch
feature/structured-trade-review, HEAD 787a9d5683803003fe2c7bfe1e786f5874847462.
Starting staged 0 / tracked unstaged 37 / untracked 53; 390 nonignored starting
files recorded by SHA-256. Preserve all production, F1-F4 and Unicode safety
bytes and all previous hunks. No Git mutation or other worktree writes.

Allowlist: tests/test_ai_review_openai_client.py, tests/test_quick_verify_docs.py,
tests/run_isolated_tests.py, tests/test_full_test_entrypoint.py, docs/TESTING.md,
docs/quick_verify.md and this plan. Runtime/log/snapshot writes belong only to
explicit task-owned temporary paths. Synthetic DB/cache/env and external
boundary mocks/denials remain under the existing H4 protocol.

## Decisions

- Stop and report any actual production defect; do not repair it in this scope.
- Malformed/nonJSON input is decode-terminal and bodyless. A valid JSON unsafe
  semantic fixture must retain the existing safety-rule telemetry assertions.
- Align current docs/counts with source inventory; preserve historical numbers.
- Diagnose timed-out module wall/CPU timings before any deadline change. Do not increase
  all module timeouts or weaken guards, restoration, coverage or cleanup.
- BuildChecks, browser matrix, production behavior/configuration/data,
  dependencies/install and migration/backfill remain out of scope.

## Current Status

- [x] Verify checkout/status and capture current bytes.
- [x] Reproduce official TestOnly before source edits.
- [x] Reconfirm nonJSON and inventory test failures against current contracts.
- [x] Measure route/cache case timings and resolve only observed test deadlines.
- [x] Verify focused assertions and deadline failure/cleanup contracts.
- [x] Run the complete official TestOnly and record exit 0/lifecycle coverage.
- [x] Audit preservation, diff whitespace and final Git status; report and wait.

## Verification

Initial official wrapper used the existing approved absolute Python and Node
executables with -Mode TestOnly. It exited 2 after 1034.182 seconds. Python:
917 PASS / 2 FAIL / 0 ERROR / 0 SKIP, 38 route cases absent from the completed
ledger due to the standard 120-second TimeoutExpired. Probes 18/18 PASS,
unexpected 0, probe contract mismatch 0, cleanup true. Route restoration is
unconfirmed and the initial suite is not passed. The wrapper stopped before Node.

Actual failures: AiReviewOpenAiClientTest.test_safety_rejection_records_only_rule_ids_and_internal_status
expected chart-rules for a nonJSON phrase, while current decode-first finalization
returns source none. QuickVerifyDocsTest.test_verify_project_runs_every_frontend_safety_test_script
expected 230 while the current verified Node inventory has 233. The docs also
need their current Python 957 and Node 233 inventory text aligned; historical
closeout evidence remains intact. No additional failures were observed.

## Remaining / Unverified

Final complete official TestOnly verification passed. Focused regression:
43/43 PASS (OpenAI client 16, quick docs 7, coordinator 15, storage fixture runner
2, SQLite isolation 3), exit 0. Restoration, patch restoration and cleanup true.
The coordinator's deliberate negative child failures remain expected evidence.
Inventory: Python 957 direct / 103 modules / 18 probes; Node 233 / 23 entrypoints,
with no missing, extra or duplicate cases. git diff --check exited 0.

## Next Step

Report and wait. Phase 6 final review can resume; this does not perform that review.

## Out of Scope

Production/F1-F4/Unicode behavior changes, BuildChecks/browser matrix, live
provider/network/private DB, other worktrees and all Git mutations.


Route diagnostic: exact current route source, original H4 execute_child and
CaseResult semantics, only per-case wall/CPU observations added in an owned
temporary helper. 38/38 PASS in 158.018 seconds; longest case 22.007s (20.938 CPU),
duplicate-key matrix 19.573s, nested metadata matrix 18.120s, canonical projection
matrix 12.441s, integer/duplicate-order matrix 11.591s. Unexpected 0, restored,
patches_restored and owned-root cleanup true. This demonstrates aggregate
coverage work exceeding the old module budget, not a stuck case or production
functional failure. The diagnostic's 300s ceiling is not the official result.

Use a fixed, source-local module-name policy only for observed timeout cohorts:
route 360s and cache 180s, with bounded margins above official/diagnostic timings.
Other guarded modules
remain 120s and approved coordinator self-tests remain 600s. Exact-name policy,
timeout-as-failure, no completed ledger/restoration claim on killed children,
sanitized command/env and owned-root cleanup are covered in the existing
coordinator regression method without changing direct testcase inventory.

The first corrected official run exited 2 after 1540.057 seconds: the two stale
expectations were resolved, 943/943 completed direct cases and 18/18 probes passed,
but the unchanged cache 14-case module timed out at 120s. No functional failure
or unexpected violation was observed. The route was 38/38 PASS in 234.359s with
restoration/patch restoration/cleanup true. Suite restoration remains unconfirmed
for the killed cache child; this run is not passed and Node was not reached.

Timing comparison: cache passed the initial official run in 77.291s. Other long
modules also slowed (approved-write 70.677 to 103.150s; content 69.017 to 92.666s).
A fresh original-H4 cache timing run passed 14/14 in 80.581s, longest case
21.887s (19.938 CPU); unexpected 0 and restoration/patch restoration/cleanup true.
This is observed runtime variability of complete mutation matrices, not a stuck
case. Cache and F1-F4 production/test bodies are unchanged; only those two
module-name deadlines change. No global timeout increase or weaker H4 protocol.

Updated deadline policy focused verification: docs/coordinator 22/22 PASS, exit 0;
restoration, patch restoration and cleanup true. Exact-name route/cache policies
and near-name defaults all fail closed on TimeoutExpired with owned-root cleanup.
Current source inventories remain Python 957/103/18 and Node 233/23; inventory
commands and git diff --check exit 0.

Final official wrapper (same approved command/runtime paths, -Mode TestOnly):
exit 0 after 957.604 seconds. Python 957/957 PASS across 103 modules, probe 18/18
contract PASS; Node 233/233 PASS across 23 entrypoints. Direct/probe/Node coverage
missing/extra/duplicate 0, unexpected 0, probe contract mismatch 0; the six
expected negative raw probe violations remain expected evidence. Python and Node
restoration, patch restoration and cleanup all true. Route 38/38 in 123.512s,
cache 14/14 in 62.253s, both with original H4 lifecycle checks true. No other
functional failures appeared. BuildChecks and browser matrix were not rerun.

Evidence is retained only in the task-owned temporary directory
C:/Users/mario/AppData/Local/Temp/stockboda-testonly-0440a98723c543089bc3f1186e0a6122:
before.log (fresh reproduction), after.log (new cache timeout), final.log
(official exit 0), route-timing/cache-timing logs and before-source snapshots.

Final preservation audit: 384 starting files unchanged; only six allowlisted
test/document files differ from the 390-file baseline, plus this new plan.
All six tested files remained byte-identical throughout the final official run;
only this result plan was updated afterward. Before-source byte diffs confirm
the existing unrelated hunks were retained. Production, F1-F4, Unicode safety,
isolation implementation and earlier plans are unchanged. Plan whitespace and
git diff --check pass. Final wrapper-owned root was removed. Root/branch/HEAD
remain as above; staged 0, tracked unstaged 37, untracked 54 (existing dirty work
included; the only added path is this plan). No Git mutation/other worktree writes.
