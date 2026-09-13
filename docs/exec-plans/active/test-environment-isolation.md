# H4 test environment isolation

## Goal
Install isolation before each explicitly selected test module is imported or discovered in its own child process. Prove H4-A1 with synthetic probes and the pure rate limiter module only.

## Scope
Base main/origin/main: `f2cc8e8cf4fe5a422897ec41758eb07d04d9488f`, ahead/behind 0/0.
Branch: `fix/test-environment-isolation`; worktree: `D:/Project/Vibe/StockBoda.worktrees/test-isolation`, initially clean.
Only tests foundation/runner/self-tests, minimal Phase A helper extraction, and this plan may change.
Main's unstaged `store-assets/google-play/ko-KR/README.md` is excluded; blob hash `e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61`.

## Decisions
- Module per child; bootstrap precedes target import/discovery. No coordinator target import.
- Keep OS execution environment only; reuse production DB_FILES and validate_configuration without changing production code.
- Writes limited to owned root; ordinary source/dependency reads allowed, sensitive/persistent paths denied.
- Reuse Phase A socketpair/network protection; record violations even when caught. Explicit negative expectations acknowledge only matching violations.
- Parent owns a unique temporary container per module; child owns runtime root below it. OS temp env names point to the container to satisfy the existing resolver's strict descendant rule; tempfile.tempdir points inside runtime root. The guard disallows writes elsewhere in the container.
- No package installation; existing main .venv interpreter/dependencies may be read with bytecode disabled. No private settings/data are copied.

## Current Status
- H4-A1 isolation foundation: implementation and local validation COMPLETE; independent acceptance review may be requested.
- H4-A2 DB/env/CWD fixture migration: deferred.
- H4-B1 external/filesystem isolation: deferred.
- H4-B2 startup/background/global lifecycle: deferred.
- H4-C frontend isolation: deferred.
- H4-D official entrypoint / independent verification / closeout: deferred.
- Preflight passed; dedicated branch/worktree created and verified clean.
- Static rate limiter inspection: only math/threading/time and in-memory state; no filesystem/network requirement.
- Implementation and authorized execution checks passed on 2026-09-14. Independent static review found no Windows A1 blockers; broader independent execution/closeout remains H4-D.

## Verification
2026-09-13: read-only Git preflight matches all user expectations; no staged/untracked main files, only protected README unstaged. Named branch/path did not exist before creation.
Allowed commands: new self-tests/synthetic child probes, explicit isolated rate limiter, directly related safe Phase A harness/config tests, git diff --check.
Tests may write only disposable synthetic roots and must block external requests. No full discovery or verify_project.ps1.

## Remaining / Unverified
H4 as a whole is not resolved. Python audit/patch guards are regression boundaries for cooperative tests, not an OS security sandbox against hostile native code. Full async/native transport coverage is B1. Full lifecycle/thread ownership is B2.

## Next Step
Inspect the exact A1 staged diff and commit with `test: add isolated backend test foundation`; no push. After commit, wait for independent acceptance or further user direction. Do not begin A2/B1/B2/C/D.

## Out of Scope
A2/B1/B2/C/D implementation; testcase-per-process; broad file-read sandbox; worker 2 / reverse-order full-suite; H1 frontend/Android environment separation; H5/H6/H7; new CI; production/config/provider access; frontend/package.json/verify_project.ps1 changes; other worktrees and main edits.

## A1 stop record — 2026-09-13

Final state: **stopped after two failures of the same filesystem-guard approach**. H4-A1 remains IN PROGRESS / not accepted. No third workaround, runtime allowlist expansion, stage, commit or push.

Implementation draft files:
- `tests/module_isolation.py`: sanitized child environment, production path validator reuse, runtime root, audit/read/write guards, violation ledger and exact negative expectations, restoration.
- `tests/run_isolated_tests.py`: explicit module child, pre-import bootstrap, parent-owned temp container cleanup, child report.
- `tests/isolation_probes.py`, `tests/isolation_swallowed_probe.py`, `tests/test_isolation_runner.py`: synthetic acceptance probes and coordinator checks.
- `tests/phase_a_isolation.py`: minimal shared network patch extraction.

Executed in this dedicated worktree, using `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe` with `-B` (no packages installed or private settings copied):
1. `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -B -m unittest tests.test_isolation_runner -v`: FAIL, 3 coordinator tests / 3 failures. Four children were attempted (rate limiter twice, swallowed probe once, synthetic probe once); all stopped during bootstrap before target discovery. Initial reporting lost bootstrap violation counts because the context had not yielded; the reported zero counts are not valid evidence of no violations. Each reported restoration and temp cleanup successful.
2. After diagnostic/reporting-only corrections, `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe -B tests/run_isolated_tests.py tests.test_rate_limit`: FAIL, 0 target tests, 1 sensitive-read violation / 1 unexpected violation, child exit 1, restored=true, cleanup=true.

Evidence / cause: the guard rejects any outside-root path with a `.cache` component. The actual Python standard library is under `C:/Users/mario/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib`. During shared network bootstrap, importing requests reaches a normal dependency import, which is denied by `Boundary.path`'s generic component rule. This is a harness design error, not a rate limiter defect. No normal dependency read allowlist was added.

Independent static review (required by AGENTS.md): identified a successful-test/cleanup-exception reporting hole. The coordinator now requires context completion (`completed`) before success and retains a boundary ledger even on bootstrap failure. The requested synthetic cleanup-error regression is still unimplemented/unverified. Reviewer also recorded POSIX relative `os.open(..., dir_fd=...)` coverage as a B1 limitation; Windows is the current execution platform.

Acceptance status:
- Pre-import guard activation and fail-closed child exit: observed by the bootstrap failure.
- Parent-owned root cleanup and environment/CWD/temp restoration on bootstrap failure: observed.
- Host secret filtering, five DB/cache path acceptance, synthetic write/read/network probes, swallowed violation failure, normal rate limiter success, normal target cleanup: NOT VERIFIED because targets never ran.
- Phase A regression: NOT RUN; do not claim regression-free from static extraction review.
- Full suite, official wrapper, production/provider/device checks: NOT RUN.

Next materially different step requires design reconsideration: replace broad `.cache` component rejection with explicit application-persistent boundary registration while preserving normal runtime/dependency reads. Do not implement or rerun automatically after this two-failure stop. Finish read-only Git/whitespace checks and report the draft for user direction.

## Authorized redesign — 2026-09-14

Resumed by explicit user approval with a materially different protected-path registry. Preflight matches the prior draft exactly: one tracked modification, six untracked files, no staged work; branch/base unchanged, main README hash unchanged.

The old name/component/extension rules are removed, not patched with runtime exceptions. READ uses canonical protected directory roots and exact files only; owned runtime fixtures take precedence. WRITE remains a separate outside-root denial.
Source of truth: env._validated_paths with explicit production/development settings (no _settings/file loading), env._resolve_path for configured backend paths, RELEASE_ENV_FILES for release targets, frontend validator's frontend/.env fallback, and access_control.py's GOOGLE_PLAY_SERVICE_ACCOUNT_FILE. Linked checkout ownership comes from Git metadata only. Parent sends only canonical roots/files through child stdin; no provider values or credential contents are sent. Configured DB exact paths include explicit -wal/-shm/-journal companions.

First validation is the new isolation_smoke target only. Full synthetic tests and selected Phase A regressions follow only if this smoke passes. The prior stop record remains historical evidence, superseded only by this explicit approval.


## Redesign validation and closeout — 2026-09-14

### Previous failure removal
The old `.cache`/`.env`/DB extension/credential-name heuristics are gone. The registry contains canonical directory roots and exact files only, with no special Codex-runtime allowlist. Module-per-child coordination, sanitized environment, production DB_FILES/path validation, separate write audit, network patches, violation scopes and parent-owned cleanup were retained.

### Protected path derivation
- Default production/development database directories and application caches come from `backend/core/env.py::_validated_paths` with explicit in-memory settings, never `_settings()` or a private file. The resolver results are mapped to the current checkout and the owning main checkout derived from Git metadata. No other worktree is read or modified for this registry.
- Exact release targets reuse `scripts/create_release_env_files.py::RELEASE_ENV_FILES`; the frontend validator's default `frontend/.env` is an exact registered file. There is no generic `.env` rule.
- Parent DB/cache/selected backend-env settings use the existing repository-relative resolver. Configured `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` and frontend-env paths follow their existing CWD-relative callers. Only these known path settings are used; credential JSON/API secrets are never metadata. No private content is opened or copied.
- Configured DB files register exact `-wal`, `-shm`, `-journal` companions. Directory containment covers default database sidecars. Exact files do not imply a protected directory or filename prefix.
- Metadata travels through child stdin and is not restored into application env. `Path.resolve` and Windows path equality handle relative paths, `..`, mixed separators and case; synthetic tests cover these cases. Owned-root fixtures take precedence over registered ancestors.
- Runtime create/write/delete/rename and SQLite opens outside the owned root remain denied. Read policy has no general source/dependency allowlist. Full native/async and POSIX descriptor-relative hardening are deferred, not claimed as an OS sandbox.

### Smoke finding and resolution
First redesigned smoke reached target execution and successfully read normal runtime/dependency source, but failed its zero-violation assertion: 1 test, 1 unexpected violation. Source inspection identified `urllib3/util/connection.py::_has_ipv6`, which binds `::1` during import and catches all exceptions. This is a distinct import-time network capability probe, not the previous filesystem false positive.
During only the shared transport imports, A1 now sets `socket.has_ipv6=False` with a restoring patch, preventing that probe from attempting a real socket operation. No network rule is relaxed and no violation is silently consumed. The next smoke passed. The new registry did not fail twice for the same cause.

### Executed commands and results
Execution cwd: `D:/Project/Vibe/StockBoda.worktrees/test-isolation`.
`PY` below is the existing `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe`; no package installation, bytecode generation, production configuration loading or real provider call was performed.

| Command | Result | Tests / violation evidence |
| --- | --- | --- |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke` (initial redesign) | FAIL, diagnosed above | 1 test; 1 unacknowledged import capability-probe violation; restoration/cleanup passed |
| Same smoke after targeted capability patch | PASS | 1 test; 0 violations; runtime/contextlib/pathlib/requests files read under guard; target requires active guard at import; restoration/cleanup passed |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results -v` | PASS | 11 coordinator/result tests; synthetic child 9 tests with 27 expected violations and 0 unexpected; swallowed import child 1 test deliberately exits 1 with its 1 unacknowledged violation; rate limiter also passes twice in unique roots |
| `PY -B tests/run_isolated_tests.py tests.test_rate_limit` | PASS | 3 tests; 0 violations; env/CWD/temp/patch restoration and container cleanup true |
| `PY -B -m tests.run_phase_a_tests tests.test_phase_a_environment.PhaseAHarnessTest tests.test_phase_a_environment.PhaseAEnvironmentTest` | PASS | 17 tests including existing RunnerCleanupCheck; Phase A has no aggregate violation recorder, so no invented violation count; expected blocked operations are asserted by its tests |

### Synthetic acceptance evidence
- Runtime/dependency and repository source reads pass, including the actual Codex Python runtime beneath the user's `.cache` directory.
- Owned `.cache`, `.env`, DB-named files and credential/service-account JSON names are allowed, including when an ancestor is registered. Real SQLite is used only for an owned synthetic database, explicitly closed.
- Registered synthetic production/development DB roots, persistent cache, private config and opaque credential files fail before OS read (paths do not exist). Exact configured sidecars and Windows normalization variants are covered. Adjacent names/unregistered sensitive-looking names are not classified as sensitive.
- Create/write/mkdir/delete/rename outside the runtime root are blocked before a synthetic mutation. No real repository or production path was used as a negative target.
- Fake provider secrets/config are absent from child env. All five DB paths plus cache validate inside runtime root. Parent path-only metadata blocks synthetic selected env/credential targets without exposing the corresponding application env settings.
- Socket connect, loopback, DNS, UDP, requests, urllib and existing curl_cffi transport are blocked. Owned socketpair works and its handles close.
- Bootstrap violation is retained with zero target tests; nonexistent-module import is a reported failure; assertion failure is distinguished from violation; swallowed runtime/import violations still fail; wrong/multiple expected violations cannot be acknowledged as success.
- Cleanup exception after successful test/restoration fails the child. Parent cleanup exception is retained in the module result and fails it; the synthetic probe performs real owned cleanup before injecting the error, leaving no files. Normal env/CWD/temp and patched transport restoration are checked.

### Independent review
Read-only independent static review of the final A1 code/tests found no actionable Windows A1 blockers. It confirmed the previous cleanup reporting hole is fixed, generic read heuristics are removed, protected-path sources and owned-root precedence are correct, and bootstrap/network/result handling remain in scope. The reviewer did not run tests; execution evidence above belongs to this implementation run.

### Scope and Git gate
Nine A1 files only: this plan, `tests/phase_a_isolation.py`, `tests/module_isolation.py`, `tests/run_isolated_tests.py`, `tests/isolation_smoke.py`, `tests/isolation_probes.py`, `tests/isolation_swallowed_probe.py`, `tests/test_isolation_runner.py`, `tests/test_isolation_results.py`.
Production/backend/frontend/config/official entrypoints are unchanged. Final whitespace and staged full-diff checks precede commit. Only the scoped commit is authorized; no push, merge, rebase or other-worktree changes.

### Deferred unchanged
A2 DB/env/CWD fixture migration; B1 broader filesystem/native/async transport; B2 startup/background/global lifecycle; C frontend; D official entrypoint/full independent execution/closeout. Testcase-per-process, worker 2/reverse full-suite, broad read sandbox, H1/H5/H6/H7 and new CI remain deferred. No full unittest discovery or verify_project.ps1 was run.
