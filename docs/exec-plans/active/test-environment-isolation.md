# H4 test environment isolation

## H4-B1 OAuth transport start — 2026-09-16

- A2 closeout independently approved by the user at `4a856d362fae6b0a42f3f94ff3c0e1d673d4a878`. This B1 entry supersedes historical next-step statements below. Preflight confirmed that HEAD, `fix/test-environment-isolation`, the assigned worktree and clean staged/unstaged/untracked state.
- Scope: only the five unchanged testcase bodies in `tests.test_oauth_login_transport.OAuthTransportTest`, split in A2-9; the existing direct-entry target list and this plan. No production, A1 guard/runner, shared helpers, other provider tests or D orchestration changes. Main has only its protected README modification, blob `e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61`. Initial Main status read hit dubious ownership; command-local safe.directory permits read-only verification without changing Git configuration.
- Inventory from source:
  - `test_oauth_request_timeout_setting_is_capped`: `_exchange_json`/`_request_json` call `requests.post/get`; existing fakes capture timeout and return synthetic 200 JSON. Input 999 must cap both calls at 20 seconds. No retry or sleep.
  - `test_kakao_access_token_profile_creates_alphamate_session`: `login_oauth_provider` -> Kakao profile -> `_request_json` fake at `https://kapi.kakao.com/v2/user/me`; original token/profile/session/first-login entitlement assertions retained, including repeat login.
  - `test_naver_access_token_profile_creates_alphamate_session`: same profile boundary at `https://openapi.naver.com/v1/nid/me`; original token/profile/session assertions retained.
  - `test_kakao_authorization_code_is_exchanged_before_login`: `login_oauth_code` -> `_exchange_json` fake at `https://kauth.kakao.com/oauth/token` -> `_request_json` fake at Kakao profile endpoint; original grant/client/secret/code/redirect and exchanged-token assertions retained.
  - `test_naver_authorization_code_is_exchanged_before_login`: same exchange/profile boundaries at `https://nid.naver.com/oauth2.0/token` and Naver profile endpoint; original state and other payload/token/session assertions retained.
- Production request helpers perform one requests call: RequestException -> HTTP 502, non-200 -> 401, JSON ValueError -> 502. These five existing tests do not exercise those error branches; no new error/retry coverage is claimed. No urlopen or time patch exists in their bodies.
- Existing `_replace` already registers patch.object cleanup for shared requests.post/get and OAuth functions. Missing boundaries were direct-entry rejection, all-five-store/cache/temp isolation, host configuration sanitation and OAuth module globals. Reuse storage_fixture, _import_state and module dictionary snapshot-before-reload; registered LIFO cleanup restores body patches before module/import state and storage, including setup/assertion failure. Fresh OAuth ticket dictionary/lock avoids sharing mutable state. Existing fakes stay at their original seams; A1 Session.request, urllib opener and socket audit guards remain active with no allowlist.
- Commands: inspection/AST/Git checks are read-only; selected runner/regression children create and remove only synthetic owned temp storage. No external service calls are authorized. Same-cause two-failure stop remains in force. Validation pending; after this five-test batch the remaining B1 inventory is 48 (53 - 5), unexecuted.

### B1 OAuth validation and handoff

- Interpreter: `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe`, always `-B`; no dependency installation. `python` was absent from PATH (tool discovery failure, not a testcase failure).
- `-B tests/run_isolated_tests.py tests.test_oauth_login_transport`: 5 PASS on the first target run; violations 0, unexpected 0, restored/patches_restored/cleanup true. Actual external network 0: unchanged A1 requests Session, urllib opener and socket audit boundaries remained active; no network access attempt or network violation occurred in the OAuth run. This is guarded local evidence, not live provider validation.
- AST comparison with starting HEAD: all five names and entire testcase bodies, plus original `_replace`, identical. HTTP request/timeout/fake semantics, assertions, inputs and expected values preserved.
- Additional in-memory state probe under unchanged isolated_module: each of the five cases passed with exact module dictionary key/value identities restored for OAuth, requests, time, urllib.request and loaded core/backend account/access modules. env, sys.path, CWD, tempfile.tempdir and testcase temp contents matched baseline after each case. Synthetic assertion failure after requests/OAuth function patches and synthetic setup failure after reload both restored the same state. Outer A1 patches and container cleanup passed; violations 0. No extra test file or framework change.
- Probe incident: first state-probe invocation passed per-case and injected-failure checks but failed its final coordinator comparison because its snapshot preceded tempfile's lazy global cache initialization. Corrected the probe only by calling gettempdir before the baseline snapshot; second invocation fully passed. No target code change or network attempt; no same-cause second failure. Main status ownership and interpreter discovery issues above were also tooling issues, not product failures.
- A1 minimum `-B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS, including intentional fail-closed probes. Their expected negative child reports are not OAuth violations. `-B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1 + 3 PASS; unexpected 0, restoration and cleanup true.
- Direct gate `-B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 32 targets. Raw OAuth transport import fails before storage dependencies/files even with forged test env. No full suite or other B1 provider execution; stale phase_a_environment orchestration remains deferred to D.
- Production code changed: no. A1 network guard/allowlist, shared storage/import helpers and README files unchanged. Commit allowlist: this plan, tests/test_oauth_login_transport.py and tests/test_storage_fixture_runner.py. git diff --check passed; full staged diff/name/check review precedes `test: isolate oauth transport tests`. No push or other worktree modifications.
- Remaining B1: 48, unexecuted. H4-B1 OAuth transport migration is ready to request independent verification after commit; this is not independent approval or overall H4 closeout.

## H4-A2 closeout — 2026-09-16

This is the current status and next-step record. Earlier A1/A2 entries below are retained in full as chronological evidence; their then-current pending, withheld or next-batch statements do not override this closeout.

- The user independently approved A2-1 through A2-12. A2-12 implementation HEAD: `161a9958976e7dddd6886eb5a75599efd2e8839c` (`test: isolate local release tests`). H4-A2 migration is complete and approved: **225 tests**.
- The user's final residual inventory confirms **remaining A2: 0**. This closeout records that approved inventory; it does not claim a new inventory audit or test execution.
- Remaining inventory: **B1 53 / B2 7 / C 22 / D 85 / OUT 20**. These categories remain incomplete or outside the A2 scope; no completion or validation of them is implied.
- D follow-up: the final inventory identified stale `phase_a_environment` references to transport testcases on the old `OAuthLoginTest` class. Correct those references for the split transport tests and validate the affected orchestration in a separately authorized D task. No reference/code correction or transport test execution is performed here.
- **Only H4-A2 is closed; H4 as a whole is not complete.** B1 external/provider boundaries, B2 lifecycle/background isolation, C frontend work, D entrypoint/orchestration/verification work and OUT disposition remain unresolved.
- Closeout preflight confirmed `D:/Project/Vibe/StockBoda.worktrees/test-isolation`, branch `fix/test-environment-isolation`, starting HEAD above and a clean worktree. This task changes only this ExecPlan; no production, shared helper or test files change, and no tests are rerun.
- Main and its existing unstaged `store-assets/google-play/ko-KR/README.md` are preserved; README blob: `e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61`.
- Next step: commit this document-only closeout as `docs: close A2 test isolation migration`, then wait for user direction. No new migration, B1 implementation, other phase work or push is authorized by this closeout.


## Goal
Install isolation before each explicitly selected test module is imported or discovered in its own child process. H4-A1 is independently accepted; A2-1 is independently accepted; A2-2 is independently accepted; A2-3 is independently accepted; A2-4 is independently accepted; A2-5 is independently accepted; A2-6 is independently accepted; A2-7 is independently accepted; A2-8 is independently accepted; A2-9 is independently accepted; A2-10 is independently accepted; A2-11 is independently accepted; the current authorized step is A2-12 local release isolation (25 A2, 8 D deferred).

## Scope
Base main/origin/main: `f2cc8e8cf4fe5a422897ec41758eb07d04d9488f`, ahead/behind 0/0.
Branch: `fix/test-environment-isolation`; worktree: `D:/Project/Vibe/StockBoda.worktrees/test-isolation`, initially clean.
A1 originally allowed only tests foundation/runner/self-tests, minimal Phase A helper extraction, and this plan. A2-1 allowed the five storage test modules, shared fixture/focused regressions and pure main/AI/consent separation. A2-2 covered SAFE me_data_routes/admin_event_routes and their focused state checks. A2-3 covered test_billing_rate_limits. Current A2-4 scope is request_id, market_rate_limits, auth_routes A2 tests, unchanged lifespan-test separation, one async API state regression, the existing direct-entry target list and this plan. No new helper/framework or next-candidate migration. Production, A1 foundation, A2-1 storage fixture and deferred review_access remain unchanged.
Main's unstaged `store-assets/google-play/ko-KR/README.md` is excluded; blob hash `e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61`.

## Decisions
- Module per child; bootstrap precedes target import/discovery. No coordinator target import.
- Keep OS execution environment only; reuse production DB_FILES and validate_configuration without changing production code.
- Writes limited to owned root; ordinary source/dependency reads allowed, sensitive/persistent paths denied.
- Reuse Phase A socketpair/network protection; record violations even when caught. Explicit negative expectations acknowledge only matching violations.
- Parent owns a unique temporary container per module; child owns runtime root below it. OS temp env names point to the container to satisfy the existing resolver's strict descendant rule; tempfile.tempdir points inside runtime root. The guard disallows writes elsewhere in the container.
- No package installation; existing main .venv interpreter/dependencies may be read with bytecode disabled. No private settings/data are copied.

## Current Status
- H4-A1 isolation foundation: independent re-verification approved by the user; final HEAD `bc7ccfb4a26bb76125c74a5696c79751399534be` (preceded by `11312695a17e9a0d71f4186baadb79600cf6ecae`). Historical failures/F1 records below are retained.
- H4-A2 DB/env/CWD fixture migration: A2-1 independently approved at `38d625c9c443c002ada4ade54d79bbd2fd790431`, with no Blocker/High/Major/Minor findings. A2-2 independently approved at 4c3ef2e310d49f74c910da4a061c3c7d2b8538af. User-reported residual read-only classification concludes additional A2 implementation is needed. A2-3 independently approved at 39e4894061cfcf1ed164dd18ee49adbab4e24136. A2-4 local 12-test verification passed, but commit is withheld: an accidental pre-split runner invocation called the 2 excluded B2 test methods, both failing at the method-internal main import after executing their path-setting preamble. The mandatory B2 non-execution gate was not met. See incident below; all other candidates deferred.
- H4-B1 external/filesystem isolation: deferred.
- H4-B2 startup/background/global lifecycle: deferred.
- H4-C frontend isolation: deferred.
- H4-D official entrypoint / independent verification / closeout: deferred.
- Preflight passed; dedicated branch/worktree created and verified clean.
- Static rate limiter inspection: only math/threading/time and in-memory state; no filesystem/network requirement.
- Implementation and authorized execution checks passed on 2026-09-14. Independent static review found no Windows A1 blockers; broader independent execution/closeout remains H4-D.

## Verification
2026-09-13: read-only Git preflight matches all user expectations; no staged/untracked main files, only protected README unstaged. Named branch/path did not exist before creation.
A1 allowed commands: new self-tests/synthetic child probes, explicit isolated rate limiter, directly related safe Phase A harness/config tests, git diff --check. A2-1 additionally allows only the five named storage modules through the A1 runner and focused testcase fixture/direct-entry regressions, as recorded below.
Tests may write only disposable synthetic roots and must block external requests. No full discovery or verify_project.ps1.

## Remaining / Unverified
H4 as a whole is not resolved. Python audit/patch guards are regression boundaries for cooperative tests, not an OS security sandbox against hostile native code. Full async/native transport coverage is B1. Full lifecycle/thread ownership is B2.

## Next Step
Complete the scoped A2-12 commit gate for `test: isolate local release tests`, then request independent verification and wait. No automatic H4 closeout, deferred-phase work or push.

## Out of Scope
Remaining A2 and all B1/B2/C/D implementation; testcase-per-process; broad file-read sandbox; worker 2 / reverse-order full-suite; H1 frontend/Android environment separation; H5/H6/H7; new CI; production/config/provider access; frontend/package.json/verify_project.ps1 changes; other worktrees and main edits.

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

## F1 independent verification hold — 2026-09-14

Independent verification reported F1 Blocker: an allowed SQLite connection can execute ATTACH DATABASE and SQLite opens the additional file internally, bypassing the initial sqlite3.connect path audit and the Python filesystem/violation recorder.
Preflight: branch fix/test-environment-isolation, HEAD 11312695a17e9a0d71f4186baadb79600cf6ecae, clean/no staged or untracked files. Base-to-HEAD contains only the A1 foundation commit. Main and protected README hash remain unchanged.

Scope: fix F1 in the test isolation layer only; no production edits, SQL/path parser, ATTACH allowlist or A2/B1/B2/C/D expansion. Search found normal sqlite3.connect calls in the five backend stores and tests, but no existing ATTACH/DETACH/VACUUM/backup/authorizer/custom connection factory usage. Confirm synthetic ATTACH and VACUUM INTO effects inside a coordinator-owned outer temp container, then install a connection authorizer at sqlite3.connect/handle so aliases also receive it. Deny SQLITE_ATTACH and retain the violation before returning SQLITE_DENY. Determine DETACH policy and backup behavior from this bounded evidence. Run synthetic normal/negative SQLite tests and the existing permitted A1/Phase A checks, obtain independent static review, then create a new scoped commit only on success; never amend 1131269 or push.
Current acceptance: ON HOLD pending F1 correction and independent re-verification. Earlier completion/review records are historical and do not override F1.


## F1 correction and local re-verification — 2026-09-14

### Root cause and bounded reproduction
On starting commit `11312695a17e9a0d71f4186baadb79600cf6ecae`, an inline synthetic probe used isolated_module with its runtime root inside a disposable outer TemporaryDirectory. ATTACH created an outer DB and VACUUM INTO created another outer DB while the violation ledger stayed empty. Both files were synthetic and the outer container was removed. No real DB/env/credential/repository file was used. SQLite version: 3.53.1.
Adding a local authorizer to that synthetic connection demonstrated that VACUUM INTO emits SQLITE_ATTACH and is denied before creating its output. The same action-level policy can cover both escapes without parsing SQL or filenames.

### Installation attempt and final interception
The first installation at `sqlite3.connect/handle` failed once with `ProgrammingError: Base Connection.__init__ not called` because that event is too early on this Python runtime. It failed closed but the incomplete connection held its synthetic file until process exit. The exact owned leftover was subsequently removed and absence confirmed; an already-removed empty temp subdirectory caused a cleanup retry, with no user file targeted. No repeated authorizer-at-handle workaround was attempted.

Final design: isolated_module temporarily wraps `sqlite3.connect`, `sqlite3.dbapi2.connect`, and `_sqlite3.connect`. Each wrapper authorizes one initial audited open, calls the original connect, installs the authorizer on the initialized connection, then returns it. A captured pre-bootstrap alias or direct Connection constructor has no authorization token and is rejected at the initial audit before file creation. The repository uses ordinary module-level connect calls; no prior alias/custom factory requirement was found. Alias imports after bootstrap receive the wrapper. API arguments otherwise pass through unchanged, and all patches restore after the module.

The callback records `sqlite-attach` then returns SQLITE_DENY for SQLITE_ATTACH. SQLite raises DatabaseError; catching it cannot erase the ledger. Installation failures record sqlite-authorizer and close the owned connection before failing. Independent static review found a custom factory could execute SQL before installation; both keyword and positional custom factory arguments are now rejected before construction (sqlite-factory). Explicit default Connection factory remains supported. No connection class rewrite, SQL parser, URI parser or ATTACH allowlist was introduced.

### DETACH and additional SQLite paths
- DETACH does not open an additional file, there are no permitted attachments, and repository code does not need DETACH. No extra DETACH denial was added.
- VACUUM INTO was a confirmed baseline WRITE bypass. SQLITE_ATTACH denial blocks it for both inside- and outside-root targets. Ordinary VACUUM also uses SQLite's internal attach mechanism and is not promised as supported under this fail-closed A1 policy; there is no repository usage.
- backup takes an already-open destination connection rather than a filename. The initial audited open prevents acquiring an outside-root destination. Normal owned source-to-owned destination backup passes and preserves rows. A fresh child does not inherit parent SQLite connection objects.
- Static scan of backend/tests found only ordinary connect calls and PRAGMA foreign_keys/table_info; no ATTACH, DETACH, VACUUM, backup, custom factory, authorizer, extension-loading, blobopen, serialize or deserialize use existed before these probes. No additional currently used file-opening API required a change.
- This remains cooperative Python test isolation. Deliberate guard/authorizer replacement and arbitrary native code are not a newly implemented SQLite security sandbox. Broader B1/B2 work remains deferred.

### Synthetic F1 regression
New files: tests/isolation_sqlite_probes.py, tests/isolation_sqlite_swallowed_probe.py, tests/test_isolation_sqlite.py. The coordinator creates only a synthetic existing-decoy.sqlite3 in its owned outer container, registers it as protected metadata, launches the real child runner, then checks byte-identical decoy content and no ATTACH/VACUUM/backup/factory output outside runtime before cleanup. A regression therefore cannot damage repository or production data.
Positive child: 5 tests, 19 expected violations, 0 unexpected. Coverage includes four standard connect/alias forms, inside/outside/existing-target ATTACH, executescript ATTACH, inside/outside VACUUM INTO, outside backup target open, fail-closed direct constructor, custom factory constructor not invoked in either API form, and normal explicit default factory/CRUD/commit/select/close/reopen/owned backup.
Negative child: one successful unittest body catches ATTACH DatabaseError, but final child exit is 1 with one unacknowledged sqlite-attach violation. Target file remains absent. Coordinator also checks pre-bootstrap aliases fail closed before opening and connect patches restore.

### Commands and evidence
Cwd: dedicated test-isolation worktree. `PY` = `D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe`; all executions use `-B`. No package install, external request, production/private file access, full discovery, or official wrapper execution.

| Command/check | Result | Tests / expected and unexpected violations |
| --- | --- | --- |
| Inline baseline ATTACH/VACUUM reproduction using only outer temp files | Reproduced F1 and VACUUM escape | 2 unguarded creations; baseline recorded 0; outer cleanup confirmed |
| Initial inline authorizer-at-handle smoke | FAIL, diagnosed and replaced | 0 completed CRUD checks; installation violation; owned leftover cleanup confirmed |
| Inline post-connect authorizer smoke | PASS | CRUD + ATTACH + VACUUM checks; 2 expected / 0 unexpected; cleanup passed |
| `PY -B -m unittest tests.test_isolation_sqlite -v` (before factory review correction) | PASS | 3 coordinator tests; then-current positive child 4 tests / 17 expected / 0 unexpected; swallowed child deliberately failed with 1 unacknowledged |
| `PY -B -m unittest tests.test_isolation_sqlite tests.test_isolation_runner tests.test_isolation_results -v` (final code) | PASS | 14 coordinator/result tests; SQLite child 5 tests / 19 expected / 0 unexpected; existing synthetic child 9 tests / 27 expected / 0 unexpected; SQLite and original swallowed children deliberately fail with 1 unacknowledged each |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` (final code) | PASS | Separate module children: 1 + 3 tests, 0 expected / 0 unexpected, restoration and cleanup true |
| `PY -B -m tests.run_phase_a_tests tests.test_phase_a_environment.PhaseAHarnessTest tests.test_phase_a_environment.PhaseAEnvironmentTest` (final code) | PASS | 17 tests; expected blocked operations asserted by tests; Phase A has no aggregate violation counter, so unexpected count is not independently measured |

The existing A1 11-test command and Phase A/smoke/rate checks also passed before the factory refinement, then were repeated on final code as above. Phase A helper/runner files were not changed for F1. SQLite patches are active only in the new isolated_module context, and all existing patch/restoration checks passed.
Independent read-only static review first identified the custom-factory gap; final review confirmed its correction and reported no further F1 blockers. The reviewer did not run tests. F1 is locally corrected; A1 independent re-verification is still required before acceptance. Prior failed-attempt records remain intact.

### Git and next step
Only module_isolation.py, the three SQLite regression files, and this ExecPlan are in F1 scope. Inspect whitespace and full staged diff, then commit as `test: block sqlite isolation escapes` in a new commit (no amend of 1131269). No push. After commit, wait for independent re-verification/user direction. Main/README protection and A2/B1/B2/C/D deferrals remain unchanged.


## H4-A2-1 authorized start and pre-write inventory — 2026-09-14

Preflight: dedicated worktree/branch and starting HEAD `bc7ccfb4a26bb76125c74a5696c79751399534be` match; clean, no staged/untracked work. Both A1 commits and this active plan exist. Main has only its excluded README modification, hash `e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61`. Main Git status required a command-local safe.directory override, with no config write.

| Module | Tests | DBs and indirect use | Original fixture/global/connection findings |
| --- | --- | --- | --- |
| test_account_store | 8 | accounts; access for wallets; deletion touches all five stores | Per-test TemporaryDirectory, usually partial DB env assignments without restoration. Privacy-version test has try/finally restoration. Module reloads reset import-time consent settings. Deletion assigns an SSV verification lambda without restoring it. Three direct SQLite connections use closing. |
| test_access_control_persistence | 4 | access, with account session lookup possible | TemporaryDirectory; two patch.dict contexts restore env, two direct assignments do not. Reloads access_control (including in-test persistence check). No test-created connection. |
| test_user_journal_storage | 2 | accounts + journal | TemporaryDirectory and direct unrestored env assignments; both modules reloaded. No test-created connection. |
| test_review_history | 6 before separation; 2 storage + 4 deferred | Storage tests: review DB; main/AI cases: accounts/access/journal/review and indirect main dependencies | Partial paths and unrestored env. Main cases mutate sys.path and main functions. User explicitly approved pure file separation; four method bodies must remain identical and must not run in A2-1. |
| test_event_log | 26 | event DB | TemporaryDirectory and local patched_env restores named settings, but supplies only one DB path. Module reloads; eight direct connections close in finally. |

Partial path sets can use module-level fallback DBs and leave env pointing at removed directories; other testcase mutations can survive to the next test. Existing tests generally allocate different direct DBs, but do not own the full DB/cache/temp set. Production path resolvers consult configuration at call time; retain reloads and all product assertions. No production lifecycle refactor is needed.

Design: tests-only storage_fixture context reuses current_boundary, sanitized_environment, DB_FILES-backed path allocation and validate_configuration. Each context owns a fresh child root with all five DBs/cache/temp/config, sanitized env, restoring env/temp/CWD, and ExitStack-owned optional real SQLite connections/patches. Existing explicit connection closes remain. Import-time gate checks active A1 guard and test-root invariants before target dependencies. This adds no runner, guard or testcase-per-process framework.

Scope addition: move four unchanged main/AI/consent methods to tests/test_main_ai_review_history_consent.py as A2-1 test-scope separation; count/text/AST comparison is static only. Their execution and isolation migration are deferred to later A2. All prior A1 failure/F1 history remains intact. B1/B2/C/D remain deferred.

### Account migration validation
First isolated account run: 8 tests, 5 errors (development login disabled), 0 violations, restoration/cleanup true. The original tests implicitly depended on ALPHAMATE_ALLOW_DEV_ACCESS left by earlier tests. Set the scenario flag explicitly in each login context (not the shared default); no product assertion or production behavior changed. This is the first failure for this cause; next run validates the correction.

Account correction PASS: 8 tests, 0 unexpected violations, restoration/patch restoration/container cleanup all true. Full five-store deletion assertions retained; SSV lambda now restoring patch. Proceeding to access_control_persistence.

Access persistence PASS: 4 tests, 0 unexpected violations, restoration/patch restoration/container cleanup true. In-test reload persistence and real access SQLite retained. Journal contexts explicitly enable synthetic dev login as required by the account finding.

Journal storage PASS: 2 tests, 0 unexpected violations, all restoration/cleanup true. Review test-scope separation static check PASS: 6 original = 2 storage + 4 deferred; method names preserved, each moved method source text and AST identical. The new main/AI/consent module was not imported or executed.

Review storage PASS: 2 tests, 0 unexpected violations, all restoration/cleanup true. Event log now uses the shared full path context; original eight try/finally SQLite closes retained.

### Event log migration validation
Initial run: 26 tests, 1 error, 0 violations, restoration/cleanup true. Inventory refinement: one legacy context explicitly selected development; the new fixture correctly rejected overriding its test environment. Static record_api_failure -> record_event inspection shows no environment-specific product branch, only the storage resolver. Removed that obsolete fixture setting to retain ALPHAMATE_ENV=test, keeping the input, redaction and logging assertions unchanged. Corrected run PASS: 26 tests, 0 unexpected violations, all restoration/cleanup true. This was one failure for a distinct cause, not a repeated guard bypass attempt.

All five target modules have now passed sequentially: 8 + 4 + 2 + 2 + 26 = 42 storage tests. No A1/Phase A foundation, production or other worktree file was changed. Next: focused sequential testcase/failure restoration/connection and direct execution regression; then minimum A1 regression.


## H4-A2-1 verification and closeout — 2026-09-14

### Final fixture and independent static review
An independent read-only reviewer found that the initial fixture reused sanitized_environment with a testcase root whose parent was the module temp directory. Although tempfile.tempdir was local, explicit TEMP/TMP/TMPDIR writes could remain shared. Corrected without changing A1: own a unique testcase container under the A1 root/temp, place ALPHAMATE_TEST_ROOT at container/runtime, and reuse sanitized_environment so OS temp variables select that unique container. The entire container is cleaned. The production resolver's strict TEST_ROOT-below-TMPDIR invariant remains intact.

All five database files use the existing DB_FILES filenames under container/runtime (accounts.sqlite3, access.sqlite3, trades.sqlite3, review_history.sqlite3, event_log.sqlite3); cache, config and tempfile.tempdir are under runtime. Environment and CWD restore via ExitStack, test-created registered connections close before deletion, and existing explicit closing/finally blocks remain unchanged. Overrides cannot replace isolation configuration. SSV lambda replacement is restoring; existing per-test module reloads and in-test access persistence reload remain.

Reviewer inspected the corrected fixture and explicit env-temp regression and reported no remaining actionable static issue. The reviewer did not run tests; runtime evidence belongs to the implementation run below. Independent A2-1 execution verification remains the next step.

### Commands and outcomes
Cwd: D:/Project/Vibe/StockBoda.worktrees/test-isolation, branch fix/test-environment-isolation, starting HEAD bc7ccfb4a26bb76125c74a5696c79751399534be plus this scoped working diff.
PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe, used read-only with -B; no install or main writes.

| Command | Result and evidence |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_account_store` | Final PASS, 8 tests, 0 violations/unexpected, restored/patches_restored/cleanup true; initial scenario-env failure recorded above. |
| `PY -B tests/run_isolated_tests.py tests.test_access_control_persistence` | PASS, 4 tests, 0 violations/unexpected, all restoration/cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.test_user_journal_storage` | PASS, 2 tests, 0 violations/unexpected, all restoration/cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.test_review_history` | PASS, 2 storage tests only, 0 violations/unexpected, all restoration/cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.test_event_log` | Final PASS, 26 tests, 0 violations/unexpected, all restoration/cleanup true; initial obsolete development setting failure recorded above. |
| `PY -B -m unittest tests.test_storage_fixture_runner -v` | PASS, 2 coordinator tests. Runs 4 focused fixture tests in an A1 child with 0 unexpected violations and restoration/container cleanup asserted; direct imports of all 5 migrated modules fail before storage dependencies/file creation even with forged test env. Repeated after testcase-container correction: PASS. |
| `PY -B tests/run_isolated_tests.py tests.test_account_store tests.test_access_control_persistence tests.test_user_journal_storage tests.test_review_history tests.test_event_log` | Final testcase-container correction: sequential module children all PASS, 42 tests total, each 0 violations/unexpected and restored/patches_restored/cleanup true. |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | PASS, 14 A1 coordinator/result tests; synthetic child 9 tests/27 expected/0 unexpected and SQLite child 5 tests/19 expected/0 unexpected. Deliberately swallowed-violation negative children each fail as required, with one unacknowledged violation and cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | PASS, separate 1 + 3 test children, 0 violations/unexpected, all restoration/cleanup true. |
| Static AST/source comparison against starting HEAD | PASS: original five modules' 46 test names/counts and every self.assert* call preserved across the split. 42 migrated + 4 deferred = 46; 6 added fixture/coordinator tests. Each deferred method source and AST identical; no target import/execution for this comparison. |
| `git diff --check` and production/foundation diff | PASS before staging; no backend, main.py, A1/Phase A helper/runner modification. Full staged diff and staged whitelist are required before commit. |

### Testcase isolation evidence
Focused Writer/Reader unittest cases run consecutively inside one module child after success, assertion failure, body exception and setUp failure. Each writer creates a real SQLite table/row in all five DBs, cache, relative data, tempfile files, and explicit TEMP/TMP/TMPDIR files; mutates/deletes env keys; and replaces an object attribute. Before/inside the next testcase, checks prove old containers absent, handles raise ProgrammingError, new paths unique and new SQLite schema empty, no cache/data/temp/env residue, original attribute restored, and CWD/temp/env restored. Context-body exception with cleared env also restores and closes. Synthetic host marker is absent in the child. Invalid environment/root/path and reserved override checks fail before testcase storage allocation.

These are local static/unit/isolated-process results. No claim of OS sandbox security or full native/async/global lifecycle isolation is added. Phase A focused tests were not rerun because its helper was unchanged. No full discovery, 46-test full run, official wrapper, frontend/Android, production/provider/network or device verification was executed.

### Git/protection and remaining scope
Only ten A2-1 files: this plan; tests/storage_fixture.py; tests/test_storage_fixture.py; tests/test_storage_fixture_runner.py; tests/test_account_store.py; tests/test_access_control_persistence.py; tests/test_user_journal_storage.py; tests/test_review_history.py; tests/test_event_log.py; tests/test_main_ai_review_history_consent.py.

Main status rechecked after validation: only the pre-existing unstaged store-assets/google-play/ko-KR/README.md. Its blob hash remains e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. No other worktree was modified. Commit authorized only after scoped staged/full-diff review, with subject `test: isolate core storage test fixtures`; no A1 amend, push, merge or rebase.

Deferred: the four main/AI/consent tests moved unchanged to tests/test_main_ai_review_history_consent.py were not executed. Remaining A2 includes auth_routes, oauth_login, me_data_routes, review_access, billing_readiness, admin_event_routes, other main/API/AI/market/cache and release-validator test isolation. All B1 external/filesystem, B2 startup/background/global lifecycle, C frontend and D official entrypoint/closeout remain deferred. A2-1 is ready to request independent execution verification; H4/A2 overall are not complete.


## H4-A2-2 start and read-only candidate inventory — 2026-09-14

User accepted A2-1 independent verification: approved, no Blocker/High/Major/Minor finding. Preflight matches dedicated worktree D:/Project/Vibe/StockBoda.worktrees/test-isolation, branch fix/test-environment-isolation, HEAD 38d625c9c443c002ada4ade54d79bbd2fd790431, clean/no staged/untracked files. A1 commits 11312695a17e9a0d71f4186baadb79600cf6ecae and bc7ccfb4a26bb76125c74a5696c79751399534be and this active plan are present. Main has only the protected README unstaged; hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61 unchanged.

Inventory was reported to the user before any file change:

| Candidate | Count/imports/DBs | Original env/global/cleanup | Classification |
| --- | --- | --- | --- |
| tests/test_me_data_routes.py | 3 tests; core.account_store, core.journal, core.access_control, core.review_history, main; summary uses accounts/journal; export adds access/review; deletion indirectly uses all five DBs | TemporaryDirectory per test, partial paths, direct unrestored env and sys.path mutation; account/core/main reloads; no direct SQLite connections or explicit function mocks | SAFE FOR A2-2: direct route and OpenAPI calls, no provider, transport, thread, lifespan or background execution. Use storage_fixture full paths and explicit synthetic dev-login scenario; restore reload/import state. |
| tests/test_review_access.py | 6 tests; backend.core.account_store/access_control; main in 2 tests; accounts/access plus journal/review/events in AI route case | TemporaryDirectory; patch.dict env with in-context direct assignments; core/main reload, sys.path not restored; AI/chart replacements restored in finally; 3 direct SQLite connections use closing; ThreadPoolExecutor/Barrier/Events with two actual workers | DEFER TO LATER A2/B1/B2 as an intact module: one test executes both AI route types and another tests concurrent example seeding. Do not split, migrate or run it in this bundle. Other four storage tests remain with the deferred module; no test deletion or skip. |
| tests/test_admin_event_routes.py | 11 tests; main, core.access_control, core.rate_limit, fastapi; accounts/access/events and cache; main not reloaded per test originally | setUp sys.path append never restored; partial TemporaryDirectory contexts, local patched_env restores only named settings; repeated main admin/callback limiter assignments not restored; existing sync_google_play_purchase_order_status patch restores; 3 helper-created SQLite connections close in finally | SAFE FOR A2-2: direct routes/config helpers, no HTTP server. Provider sync is already mocked at route dependency with asserted call args; no transport/mock redesign. Cache-status reads only get_cached_theme_returns -> local empty cache; no warmup/fetch/thread call. |

Main import audit: validate_configuration, credential-safe logger filter installation, yfinance logger level change, locks/limiter/cache/app object allocation and route registration occur at import. initialize_yfinance_cache and scheduler/thread startup are inside lifespan and will not be called. core.data_fetcher cached-status reads are local and use cache_directory; no fallback provider call. Imported OAuth/AI modules define provider functions but selected routes do not invoke them. No existing library/private data was read for this inventory.

Plan: keep tests/storage_fixture.py and A1/Phase A infrastructure unchanged. Add only a tests-only context for the observed main/core reload, sys.path, and logger side effects; it composes with storage_fixture and does not allocate storage, start/disable startup, or patch transport/provider behavior. Register core/main dictionary restoration before reloading so per-case locks, rate limiters, app/OpenAPI cache and env-derived constants are discarded. Main/core initial imports happen under the approved A1 guard with module-default test configuration. Preserve existing real SQLite assertions and local provider mock. Admin production short-token policy remains an inner restoring env context calling only the pure token guard, with all storage paths still explicitly owned; no environment policy change.

Validation writes only disposable A1 roots, no production/private files or external calls. SAFE modules run sequentially; a network violation reclassifies the affected module to B1, no extra provider mocks/allowlist/startup bypass. Minimum A1 regressions follow. Shared storage fixture is not planned to change, so accepted A2-1 evidence is retained; API-specific regression is justified by observed unrestored limiter/reload/logger/sys.path state. All other A2 and B1/B2/C/D implementations deferred.

A2-2 me_data_routes first isolated run PASS: 3 tests, 0 expected/unexpected violations, restored/patches_restored/cleanup true. The main import needed no network mock or lifecycle bypass. All three original route/assertion bodies retained; fixture makes synthetic dev-login authorization explicit. Proceeding to admin_event_routes; review_access remains unchanged/unexecuted.


## H4-A2-2 verification and closeout — 2026-09-14

### Migrated scope and state ownership
- me_data_routes: 3 original tests, full storage_fixture per test context, explicit local synthetic dev-login setting, privacy-version override limited to its original summary scenario. Direct route/OpenAPI assertions unchanged.
- admin_event_routes: 11 original tests, storage_fixture and api_module_state entered with TestCase.enterContext in setUp; cleanup runs even if setUp or a testcase fails. Old partial DB/cache directories removed. Development setup uses the test environment. The existing short-admin-token production policy context remains unchanged and calls only _require_admin_token; its explicit owned path set is never removed. Limiter assignments now restoring patch.object contexts; three helper-created SQLite connections still close in finally. Existing provider sync patch and assert_called_once_with arguments unchanged.
- api_test_modules: small test-only helper composes with the approved storage fixture, allocates no storage and changes no guard. Initial main/core imports establish sanitized module defaults under A1; dependencies stay loaded. Before each reload, module dictionaries are saved/restored with patch.dict; per-case app/OpenAPI cache, locks, limiters and import-time consent constants are replaced and restored. sys.path, uvicorn.error/ancestor-handler filters and yfinance logger level restore on success/failure. No lifespan invocation, startup bypass, provider mock or transport patch added.
- The direct-entry coordinator adds only the two newly migrated names to its existing target tuple. A2-1 fixture and its existing tests remain unchanged; A2-1 independent acceptance is retained.

### Executed checks
Execution cwd: D:/Project/Vibe/StockBoda.worktrees/test-isolation, branch fix/test-environment-isolation, starting HEAD 38d625c9c443c002ada4ade54d79bbd2fd790431 plus scoped A2-2 diff. PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe, all Python runs use -B. Writes only to disposable test roots; no production/private data read or actual provider/network call.

| Command/check | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_me_data_routes` | PASS, 3 tests, 0 expected/0 unexpected violations; restored, patches_restored and cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.test_admin_event_routes` | PASS, 11 tests, 0 expected/0 unexpected violations; restored, patches_restored and cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.test_api_module_state` | PASS, 2 focused tests, 0 expected/0 unexpected violations; restored, patches_restored and cleanup true. |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS, existing direct-entry check now covers 7 modules (old 5 + new 2); all reject a forged test env without A1 before storage dependencies/files. No DB-backed target body runs directly. |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | PASS, 14 tests. Synthetic 9-test child: 27 expected/0 unexpected; SQLite 5-test child: 19 expected/0 unexpected. Deliberately swallowed violations each fail the negative child as required, with cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | PASS, 1 + 3 tests, 0 expected/0 unexpected violations, restoration/patch restoration/cleanup true. |
| Static AST comparison to starting HEAD | PASS, all 3 + 11 original names/counts/assert calls (including mock call expectations) preserved. Deferred review_access source unchanged. |
| Production/foundation/storage fixture diff and whitespace | No backend/frontend, A1/Phase A helper/runner, storage_fixture.py or deferred review_access change. git diff --check PASS before staging; full staged diff/allowlist checked separately before commit. |

All A2-2 executions passed on first attempt; no repeated-failure or network-reclassification workaround was used. A2-1 42 storage tests and its unchanged focused fixture suite were not rerun because the shared fixture was not modified. The existing direct-entry check was rerun only because its target list changed. No full discovery/full Python suite, verify_project.ps1, frontend Node suite, server, lifespan, background worker, OAuth/provider/device verification was run.

### Isolation and independent review
The new regression addresses observed API-specific leakage rather than adding a new framework. It runs synthetic unittest cases through success, assertion failure, body exception and setUp failure, with the same storage/API contexts used by targets. It exercises real limiter state and app.openapi cache, changes auth/callback references with restoring patches, and compares main/core env-derived constants, function/limiter/app identities, sys.path/CWD/env, logger/handler filters and log level to the prior baseline. Each next context has a fresh root, empty OpenAPI cache and fresh limiter. Old containers are absent. A separate partial-main-reload exception verifies dictionary and logger restoration after actual reload initialization and before context entry.

The A2-1 accepted fixture supplies all five DB paths/cache/temp and restores env/CWD/resources; no new DB lifecycle ownership was introduced. API targets retain real storage access and explicit direct-connection cleanup. A1 boundary reports no persistent-path or network violations. These are local static/unit/direct-route/isolated-process results, not HTTP-server, provider or lifespan evidence.

Independent read-only static reviewer reported no actionable findings after inspecting helper cleanup order (test patches, then API state, then storage), partial reload/setup restoration, unchanged assertion/input/provider mock semantics, and bounded production-policy context. Reviewer did not execute/import target modules or modify files. Independent A2-2 execution verification remains pending.

### Git/protection and deferred scope
Six scoped files: docs/exec-plans/active/test-environment-isolation.md; tests/api_test_modules.py; tests/test_api_module_state.py; tests/test_me_data_routes.py; tests/test_admin_event_routes.py; tests/test_storage_fixture_runner.py. After explicit staged-name/full-diff verification, only the new commit `test: isolate data access api tests` is authorized. No amend/push/merge/rebase or other-worktree edit.

review_access remains unchanged and unexecuted: AI route case belongs to later A2/B1 provider/AI work; concurrent example seeding belongs to B2 concurrency/lifecycle work. No testcase was removed, skipped or split. The already deferred four main/AI/consent tests remain untouched/unexecuted. Remaining A2 auth/OAuth, billing_readiness, AI/OpenAI, market/data-fetch, other main integration and request/background/lifespan tests remain deferred; B1/B2/C/D implementation is not started.

Main protection is checked again at commit handoff: preserve its sole pre-existing unstaged store-assets/google-play/ko-KR/README.md and hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. A2-2 is ready to request independent data-access API verification; overall A2/H4 is not closed.


## H4-A2-3 start and pre-write inventory — 2026-09-14

Preflight: root D:/Project/Vibe/StockBoda.worktrees/test-isolation, branch fix/test-environment-isolation, HEAD 4c3ef2e310d49f74c910da4a061c3c7d2b8538af, clean/no staged/untracked files; active plan present. Main has only excluded README unstaged, hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61 unchanged.

A1/A2-1/A2-2 independently approved per user. User-supplied residual READ-ONLY classification concludes additional A2 implementation is needed. Only billing_rate_limits is selected: smallest two-test env/path/limiter migration matching approved admin pattern. This run rechecked the target and production call chain, not the full residual inventory.

| Existing testcase | Imports/env/state/cleanup | Suitability |
| --- | --- | --- |
| test_billing_rate_limit_rejects_excessive_purchase_requests | main and core.rate_limit inside body; setUp sys.path append not restored; patched_env restores threshold 2; direct _billing_rate_limiter replacement not restored; no reload/DB paths/temp/connection | A2: memory check only, two allowed calls then 429 + Retry-After; no provider/network/lifespan/background. |
| test_billing_rate_limit_has_upper_bound | main inside body; same sys.path issue; patched_env restores 999999; no limiter consumption/reload/storage/connection | A2: bounded env integer returns 120, no external/lifecycle path. |

Inventory reported before edits. Reuse storage_fixture/api_module_state through setUp enterContext and restoring limiter patch.object. Helpers remain unchanged; same raw-import gate before main. All five DB paths/cache/temp and test env are inherited from approved fixture. Existing API regression consumes only admin and does not exercise the actual billing patch: add one focused method using the real BillingRateLimitTest lifecycle, consumption, assertion/exception injection, and subsequent identical testcase. Check restored baseline limiter identity/unmodified hits plus existing env/module/path snapshot. Extend existing direct-entry tuple by one name. No new helper or limiter abstraction.

First apply_patch failed to match the UTF-8 BOM at the target start; no changes were applied, confirmed clean. Raw bytes confirmed BOM; a BOM-preserving UTF-8-sig read/write is the different edit method. This is a tooling failure, not a test/product failure.

Four scoped files: billing target, test_api_module_state.py, test_storage_fixture_runner.py and this plan. Validation writes only disposable A1 roots; no persistent data/provider/server/lifespan. request_id, market_rate_limits, auth_routes and remaining A2 untouched/deferred; B1/B2/C/D deferred. No full suite, production/helper/framework changes.


## H4-A2-3 verification and closeout — 2026-09-14

Implementation reuses unchanged storage_fixture and api_module_state in setUp with enterContext; the existing limiter replacement is now patch.object registered for cleanup. Cleanup order is limiter patch, API module state, then storage. Every testcase owns accounts/access/journal/review/event DB paths plus cache/temp, with sanitized ALPHAMATE_ENV=test. No direct DB connection is introduced. Main imports only under A1; no startup, lifespan, scheduler or provider execution.

Execution cwd is the dedicated worktree; PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe. Only disposable test-owned roots were written.

| Command/check | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_billing_rate_limits tests.test_api_module_state` | PASS: billing 2, API state 3 (existing 2 + focused billing regression 1). Both reports: expected violations 0, unexpected 0, restored=true, patches_restored=true, cleanup=true. |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | PASS: 14 coordinator tests. Synthetic probe: 9 tests/27 expected/0 unexpected; SQLite: 5 tests/19 expected/0 unexpected. Deliberately swallowed-violation negative child fails as required, cleanup true. |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | PASS: 1 + 3 tests, expected/unexpected 0, restored/patches_restored/cleanup true. |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS: one existing coordinator checks all 8 listed modules, including billing, fail closed without A1 before storage dependencies/files. |
| Static full test-method AST comparison against starting HEAD | PASS: 2 -> 2 names/bodies identical except precisely the approved assignment-to-restoring-patch substitution; inputs, assertions, expectations and failure semantics unchanged. No skip, duplicate or loss. Initial comparison script incorrectly assumed assignment preceded body imports; corrected to locate the assignment. This was a checker error, not a target test failure. |
| Scope and whitespace | Only four listed test/plan files differ; production, storage_fixture.py, api_test_modules.py and A1 foundation unchanged. git diff --check PASS. |

The focused regression executes the actual consuming billing testcase lifecycle through success, injected assertion failure and injected exception, then executes the same original testcase with identical user/client/threshold again. Each following case allows two calls then rejects the third; consumed limiter objects are distinct. The original default limiter identity and hits remain unchanged after each lifecycle; existing snapshot checks env/module/sys.path state restoration. Existing API regression also checks setup failure and partial reload exception cleanup. No limiter bypass or new mock/transport framework was needed.

All test commands passed on their first run. API/storage helpers were not changed, so approved A2-2 full 14 and A2-1 storage 42 were not rerun. No full suite, frontend, server, provider or lifecycle verification was performed. Independent read-only static review found no actionable findings in preservation, cleanup ordering, real billing lifecycle regression, direct-entry gate or production scope; reviewer did not import/execute targets or write files. Independent A2-3 execution acceptance remains pending.

Four-file commit allowlist: tests/test_billing_rate_limits.py, tests/test_api_module_state.py, tests/test_storage_fixture_runner.py, docs/exec-plans/active/test-environment-isolation.md. Full staged diff and names must be reviewed before the authorized new commit, subject `test: isolate billing rate limit tests`. No amend or push. Main recheck: sole pre-existing unstaged README, blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61 unchanged.

Remaining A2 candidates including request_id and market_rate_limits require separately authorized classification/migration; auth_routes and other previously deferred modules remain untouched. B1 external/provider/OAuth, B2 lifecycle/background/concurrency, C frontend and D official entrypoint/overall closeout remain deferred. A2/H4 overall is not closed; stop after this commit and request independent billing rate-limit migration verification.


## H4-A2-4 start and pre-write inventory — 2026-09-14

User independently approved A2-3 at 39e4894061cfcf1ed164dd18ee49adbab4e24136. Preflight matches root D:/Project/Vibe/StockBoda.worktrees/test-isolation, branch fix/test-environment-isolation, that HEAD and clean staged/unstaged/untracked state; active plan present. Main retains only protected README unstaged, blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.

Bounded batch: request_id 2, market_rate_limits 2, auth_routes A2 8; auth lifespan 2 split unchanged to tests/test_auth_lifespan.py, H4-B2 deferred and unexecuted. Total original target tests 14 = executed 12 + deferred 2. No next-candidate work.

| Module | Original inventory | Classification |
| --- | --- | --- |
| request_id | 2 tests; main import inside bodies, unrestored setUp sys.path; pure header/UUID function, no DB/env/limiter changes, reload, provider or lifecycle | A2 SAFE, reuse storage/API contexts and gate |
| market_rate_limits | 2 tests (sync + async IsolatedAsyncioTestCase); main/core.rate_limit; patched_env restores threshold; raw market limiter replacement and setUp sys.path not restored; synthetic call_next returns in-memory response, no provider, worker or lifespan | A2 SAFE, restoring limiter patch; retain existing unittest async loop ownership |
| auth_routes | 10 tests; main, rate_limit and HTTPException; per-body unrestored sys.path; local patched_env cleanup; raw auth limiter assignment. 8 tests cover OpenAPI registration, limiter, health and public HTML, with no DB/provider/lifecycle call | 8 A2 SAFE with approved contexts; remove obsolete per-body path setup only |
| auth lifespan subset | test_lifespan_skips_theme_warmup_when_disabled_for_render; test_lifespan_can_enable_theme_warmup_for_manual_prewarming. asyncio.run main.lifespan, FakeThread assignment restored in finally, warmup env restored; actual cache initialization and lifespan purpose | 2 H4-B2 deferred; preserve complete method bodies, helper and imports needed, no execution |

Production call-chain inspection confirms request_id is pure UUID/string handling; market middleware only checks limiter then awaits synthetic call_next; auth limiter is memory-only, health reads revision env, HTML functions render local strings. Main registers routes and logging at import under A1 but lifespan runs only when invoked; no production changes needed. Each A2 testcase will reuse unchanged storage_fixture and api_module_state for all five DB paths/cache/temp, sanitized env, reload/sys.path/logger cleanup. Existing API regression covers success/assertion/body/setup/partial-reload failure; inspect async-specific cleanup evidence after the sequential module runs. No new framework, transport mock, provider allowlist or lifespan bypass. Validation writes only disposable owned roots. Execute request_id, then market_rate_limits, then auth A2, checking reports between migrations. B2 module is excluded from execution and direct-entry target list.


## H4-A2-4 local verification and commit hold — 2026-09-14

### Implementation and preservation
request_id uses approved storage_fixture/api_module_state in setUp, before unchanged test bodies. market_rate_limits retains IsolatedAsyncioTestCase and synthetic call_next, with a restoring patch for _market_rate_limiter. auth_routes has the same per-case contexts and restoring _auth_rate_limiter patch; obsolete per-body sys.path insertion was removed. All five DB paths and cache/temp belong to each testcase; env, sys.path, logger and module dictionaries restore via unchanged helpers. No real SQLite connection is introduced, no external provider/server/startup call is needed.

Auth lifespan methods moved with names, complete bodies, inputs/assertions and FakeThread semantics unchanged to tests/test_auth_lifespan.py. Its local patched_env helper is copied unchanged; it does not import the gated A2 module. This is test-scope separation, not a feature change. Static full method AST comparisons against 39e4894061cfcf1ed164dd18ee49adbab4e24136 PASS: request_id 2, market 2, auth 10 = A2 8 + B2 2. Only allowed A2 path-setup removal and limiter assignment-to-restoring-patch changes were normalized; deferred bodies/helper match exactly. No assertion relaxation, skipped/duplicate/lost tests.

### Execution incident and mandatory commit hold
1. request_id passed on first run (2 tests).
2. Initial market edit placed the original UTF-8 BOM after new imports; isolated import failed SyntaxError before any test. Restored BOM to the start, parsed statically, then market passed 2 tests. No guard/production workaround; both reports had zero violations and successful cleanup.
3. The first auth split script decoded raw CRLF bytes without universal-newline normalization and failed finding the LF separator before any write. The same PowerShell command unfortunately continued to the runner despite that failure. It invoked the ORIGINAL 10 auth tests, including the 2 explicitly excluded B2 methods. All 10 errored with ModuleNotFoundError at import main. Both B2 methods entered their path-setting preamble and reached the internal import; neither reached asyncio.run(), the lifespan context, cache initialization/warmup, FakeThread definition/patch or background/thread startup. Report: tests=10, errors=10, violations=0, unexpected=0, restored=true, patches_restored=true, cleanup=true. This was an assistant command-orchestration mistake, not a product failure. The B2 methods WERE invoked; do not describe this run as B2 unexecuted.
4. Reported the mistake promptly. Corrected the split with universal-newline reading and static parsing/count checks, then ran the A2-only auth module in a SEPARATE command: 8 PASS. The new deferred module was never imported or executed, and no lifespan call occurred in any run.

The user's mandatory commit condition "B2 2 tests unexecuted" was not satisfied. Successful later checks cannot undo this incident. Therefore no staging/commit/push is performed. The intended subject remains test: isolate lightweight api tests only for a later authorized disposition. No third workaround, network allowlist, production edit or assertion weakening was used.

### Passed validation
PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe, cwd = the dedicated test-isolation worktree. Each selected target uses the A1 runner; writes limited to disposable roots.

| Command | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_request_id` | PASS 2; expected/unexpected violations 0/0; restored, patches_restored, cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_market_rate_limits` | Corrected run PASS 2; expected/unexpected 0/0; restored, patches_restored, cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_auth_routes` | Post-split run PASS 8; expected/unexpected 0/0; restored, patches_restored, cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_api_module_state` | PASS 4 (existing 3 + focused async 1); expected/unexpected 0/0; restored, patches_restored, cleanup true |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | PASS 14; synthetic child 9 tests/27 expected/0 unexpected; SQLite 5/19 expected/0 unexpected; intentionally swallowed negative probes correctly fail their child with cleanup true |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | PASS 1 + 3; expected/unexpected 0/0; restored, patches_restored, cleanup true |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS 1 coordinator; all 11 A2 module names fail closed without A1 before storage dependencies/files; deferred lifespan module excluded |
| Static preservation and git diff --check | PASS; no production/shared helper/foundation changes |

The existing generic API regression covers env/path/logger/global cleanup after success, assertion failure, body exception, setUp failure and partial reload failure. The new focused async regression fills the prior sync-only evidence gap: actual market middleware testcase consumption, separate subsequent identical testcase, success/assertion/exception/asyncSetUp failure, closed distinct loops, no pending tasks, original limiter identity/hits and baseline state preserved. The probe temporarily isolates/restores its unittest-created asyncio policy using an existing patch pattern; no helper/framework change. Independent read-only static reviewer reports no additional actionable finding; confirms unchanged deferred method text and proper cleanup ordering, but explicitly agrees the incident still prevents commit.

Shared storage_fixture.py/api_test_modules.py unchanged: no full A2-1/A2-2/A2-3 regression rerun required. Existing API regression includes its approved billing lifecycle check. No full discovery, full Python suite, frontend Node, verify_project.ps1, actual server/provider/device verification or lifespan execution.

### Handoff scope
Seven changed files: docs/exec-plans/active/test-environment-isolation.md; tests/test_request_id.py; tests/test_market_rate_limits.py; tests/test_auth_routes.py; tests/test_auth_lifespan.py (new); tests/test_api_module_state.py; tests/test_storage_fixture_runner.py. Leave unstaged, no commit/amend/push. Main remains protected; final main status/hash recheck required at handoff.

H4-B2 deferred: test_lifespan_skips_theme_warmup_when_disabled_for_render and test_lifespan_can_enable_theme_warmup_for_manual_prewarming in test_auth_lifespan.py, with the failed pre-split invocation disclosed above. Remaining A2 review_access, journal limits, AI tests, billing_readiness and other candidates untouched. B1 external/provider/OAuth, B2 lifecycle/background, C frontend and D official entrypoint/overall closeout remain deferred. Final verdict: additional correction/disposition needed; no automatic next task.


### Incident acceptance revision and commit authorization
The user subsequently accepted the disclosed preamble-only invocation: lifecycle/cache/warmup/background execution was not reached, unexpected violations were 0, restoration/cleanup succeeded, and the separated B2 module was not rerun. This supersedes the historical commit hold above. Reuse the existing successful A2 12 and required regression evidence; no new tests or code changes. Commit only the seven scoped files after full staged-diff/whitespace checks with subject `test: isolate lightweight api tests`; no push or next-candidate work.


## H4-A2-5 start — 2026-09-14
User independently approved A2-4 at 7f5c2521d7a81f52f02bc136b0e3435ad3e055b4. Dedicated root/branch match, clean preflight; main only protected README unstaged with unchanged e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. Scope only journal_batch_limits 13 and journal_query_limits 5, existing helpers/gate regression and plan. No production, provider, lifespan, B2 or next-candidate execution.

Source inventory: batch reloads account/access/main, restores a partial env list, and allocates only two temporary DB paths for the AI-size rejection test. Invalid saved-trade cases now require actual authentication before journal validation. Batch is SAFE with full storage/API contexts and real dev-login session + storage opt-in. AI-size route rejects before AI/rate/charge/provider logic. Query has 5 tests with unrestored main function assignments; three saved routes require persistent authentication while two old mocks target optional auth. Query is SAFE if a real SQLite synthetic user-a / Bearer session fixture supplies the existing expected identity, without unconditional auth mocks or altered assertions. Retain existing list/build mocks and inputs, replace only auth setup and restoring patch lifecycle. Existing helpers remain unchanged. Run modules separately after edits; failure twice at same cause stops approach.


### A2-5 local verification and auth decision
Both modules SAFE and included: 13 batch + 5 query = 18 original testcases. All original names/self.assert* call ASTs match starting HEAD; manual diff confirms original trade payloads, invalid values, limit settings, expected results and list/build fake semantics unchanged. Only real auth context is supplied where current saved routes require it. No skip, duplicate, deletion, route/production change or provider bypass.

Batch uses a real local dev-login session with storage opt-in; original AI-size test retains its own batch-limit-user/session and payload. Per-case test environment replaces its old development env/two-path temp setup. Invalid saved-trade inputs still reach the same 400/413 validation; authentication is not mocked. Limits are read at call time, so replacing ad hoc reload with the existing API context does not change scenario settings.

Query seeds a fresh real account DB with active user-a, storage opt-in, and the SHA-256 hash of synthetic token session, unrevoked and expiring one day after setup. Production authenticate_session remains unpatched and validates actual rows. Literal Bearer session and expected user-a remain unchanged; the previously unauthenticated list call receives that same valid context. Obsolete optional-session mocks and the unconditional authenticate_session lambda are removed. Existing list/build replacements retain bodies and are registered with enterContext(patch.object), restoring before API module dictionaries and storage cleanup. The setup connection uses closing and commit; production auth/dev-login connections close in finally. No second fixture framework or common-helper change.

PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe; execution cwd = dedicated worktree, starting HEAD 7f5c2521d7a81f52f02bc136b0e3435ad3e055b4. Each target ran separately in A1, and all commands passed on first attempt:

| Command | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_journal_batch_limits` | 13 PASS; expected/unexpected violations 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_journal_query_limits` | 5 PASS; expected/unexpected violations 0/0; restored/patches_restored/cleanup true |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | 14 PASS; synthetic 9 tests/27 expected/0 unexpected, SQLite 5/19 expected/0 unexpected; intentional swallowed-violation children correctly fail with cleanup true |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | 1 + 3 PASS; expected/unexpected 0/0, restored/patches_restored/cleanup true |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS; 13 listed modules, including both new targets, reject raw import before storage/main dependencies or files |
| Static names/count/assertion AST and git diff --check | PASS; 13 + 5 preserved |

State isolation: full five DB/cache/temp paths owned per testcase; sanitized env restored even after setup failure via enterContext. Main/core reload/sys.path/logger restoration uses unchanged approved api_module_state; function patches restore LIFO before module/storage contexts. Existing accepted helper failure-path regression remains applicable and is not rerun because helpers are unchanged. No observed boundary leakage; no actual provider/network/background/lifespan execution. AI-size test stops at first batch guard, before charge/provider code; query charts/review use their existing synthetic builders.

Four-file commit scope: tests/test_journal_batch_limits.py, tests/test_journal_query_limits.py, tests/test_storage_fixture_runner.py, this plan. Production, common helpers and other candidates unchanged. Main README protected hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61; recheck at handoff. Full staged diff/allowlist/whitespace check precedes authorized commit; no amend/push. A2-4 independent approval is retained, including its disclosed and accepted incident history.

No query deferral needed. All other A2 candidates, auth lifespan B2 tests, B1 external/provider, B2 lifecycle/background, C frontend and D official entrypoint/overall closeout remain deferred and unexecuted. No full suite. Independent A2-5 execution verification is next; A2/H4 overall remain open.

Independent read-only static review: no actionable findings; confirmed 18-test assertion/input preservation, real session schema/auth compatibility, restoring patches and connection cleanup. Reviewer performed no execution/import/file or Git writes.


## H4-A2-6 start and source inventory — 2026-09-14
A2-5 independently approved by user at 27737521e7f5be18ee56f3a7ae44e91a12d650f7. Preflight: dedicated test-isolation root/branch, expected HEAD, clean/no staged/untracked; active plan present. Main retains sole protected README change, hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. Scope only four candidate modules (12 tests), existing direct-entry target list and this plan. No helper/framework/production changes planned.

| Module | Source assessment |
| --- | --- |
| main_ai_review_history_consent (4) | A2 SAFE: existing basic/advanced builder and chart lambdas cut off external calls; real local account/access/history/consent operations. Missing consent rejects before builder. Original partial env/temp directories, reload/sys.path and raw function assignments require restoring fixture lifecycle. |
| journal_chart_details (4) | A2 SAFE: build_review, marker/outcome arithmetic and interval calculation on supplied trades/candles; no chart fetch or initialize_yfinance_cache call. Only module-level sys.path/import state and testcase ownership needed. |
| ai_review_quality (3) | A2 SAFE: _trade_episode and _fallback_basic_text use provided trades/snapshots and local build_review/checklist arithmetic. Imported transport definitions are not called; no OpenAI request or chart snapshot fetch. |
| stock_chart_corporate_actions (1) | A2 SAFE: existing get_stock_ohlcv lambda supplies DataFrame.copy; get_stock_data processes local pandas values thereafter. Existing finally restores provider function; keep fake and assertion semantics. |

Inventory reported before edits. Use approved storage_fixture/api helper, full five DB/cache/temp roots and sanitized env; restore main/core/path/logger state. Consent uses an innermost ExitStack for unchanged builder lambdas so patches close before API module restoration and storage cleanup. Pure function imports use existing restoring import-state context; no mock expansion. Execute each SAFE module separately under A1; network violation means defer, never add provider workarounds. All remaining A2/B1/B2/C/D remain deferred.


### A2-6 verification and resumed closeout — 2026-09-15
Resumed from five authorized unstaged A2-6 files at unchanged HEAD 27737521e7f5be18ee56f3a7ae44e91a12d650f7. Diff matched the earlier implementation exactly; no unrelated edits. User authorized preserving that state. Reused the already completed consent 4, chart details 4 and quality 3 PASS evidence without rerunning them. Completed corporate actions 1 and required regression. All four candidates remain SAFE; no deferred candidate within this batch.

Consent now composes full per-case storage_fixture (dev access and original privacy version scenario), api_module_state and innermost ExitStack restoring the identical AI/chart lambdas. Local auth/purchase/history/consent behavior is unchanged. Pure chart details/quality use the existing _import_state around imports and storage_fixture per testcase; their functions only use supplied values and local variables, so no new reload or patch is needed. Corporate actions uses per-case storage/API contexts and retains its exact OHLCV fake and try/finally restoration. No provider transport, background, lifespan, cache initializer or worker is executed by these paths. No shared helper or production change.

PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe; cwd = dedicated worktree. Tests write only disposable A1-owned paths.

| Command | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_main_ai_review_history_consent` | Previous uninterrupted A2-6 run: 4 PASS; violations/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_journal_chart_details` | Previous run: 4 PASS; violations/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_ai_review_quality` | Previous run: 3 PASS; violations/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_stock_chart_corporate_actions` | Resumed run: 1 PASS; violations/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | 14 PASS; synthetic 9/27 expected/0 unexpected, SQLite 5/19 expected/0 unexpected; swallowed-violation negative probes correctly fail child and clean up |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | 1 + 3 PASS; violations/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS; existing gate coordinator now covers 17 listed modules, rejecting raw import before main/storage dependencies or files |
| Static normalized full method AST versus starting HEAD | PASS for all 12 names/methods; normalization only fixture/env/import setup and assignment-to-restoring-patch conversion. Assertions, payloads, expected values and every lambda body remain identical. No skips/duplicates/loss. |

No new regression framework: existing approved helper failure-path evidence remains applicable because storage_fixture/api_test_modules are unchanged. Context cleanup handles success/body/setup failure; patch restoration precedes module dictionary restoration and storage cleanup. No observed DB/env/path/module/function leakage. No A2-1 through A2-5 full rerun, no whole Python/frontend suite, no B2 execution and no next candidate.

Six-file commit allowlist: four target modules, tests/test_storage_fixture_runner.py and this plan. Review full staged diff, production/helper exclusion and git diff --cached --check before new commit `test: isolate local ai and chart tests`; no amend/push. Main README remains protected, expected hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61 checked at handoff. Other A2 and B1/B2/C/D remain deferred; independent A2-6 execution acceptance is next.

Independent read-only static review found no actionable findings: confirmed all 12 test semantics, patch/API/storage cleanup order, pure-function import scope and unchanged production/helpers. Reviewer did not execute/import targets or modify files.


## H4-A2-7 start and source classification — 2026-09-15
User independently approved A2-6 at 80659e1fb52e64718c1cade642cd1df5253d96be. Preflight matches dedicated worktree/branch/HEAD, clean and no staged/untracked files. Main only protected README unstaged, blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. Scope four candidate modules and one pure B2 split, gate list, plan; no production/shared helper/framework changes.

Source decisions: review_access five tests SAFE: local review session/quota/expiry/credentials and direct login/AI routes, existing basic/advanced/chart fakes and finally blocks fully isolate provider calls. One worker test test_review_example_trades_are_seeded_once_when_logins_overlap is B2: ThreadPoolExecutor, barrier/events/concurrent seeding. Move body and original helper methods unchanged to test_review_access_concurrency.py; never import or execute it in A2. Static 6 = 5 + 1 split check before any runner call.

production_dev_guards three tests SAFE with main imported under A1/test setup, then original production policy context for route auth/dev guards; real synthetic development session setup retains owned paths. No startup or external call. cors_config two and privacy_policy two SAFE pure env/config/HTML functions, restoring named patches over sanitized full testcase environment. Total A2 12 and B2 1. User-facing inventory reported before edits. Selected target commands write only disposable test roots; no B2/whole-suite execution.


### A2-7 implementation and validation
review_access: 6 original tests = 5 A2 + 1 B2 in test_review_access_concurrency.py. Worker body and its two original helper methods are AST-identical; it was separated before any execution and never imported/executed. A2 tests retain real SQLite/session/quota/credential checks and exact AI/chart fake bodies/finally restoration. Existing helper contexts own all five DB/cache/temp paths; explicit test dev access preserves the normal-user scenario. Canonical core module imports ensure original repeated reloads are covered by api_module_state snapshots. All direct SQLite connections retain closing; local synchronous seeding uses its ordinary lock without starting workers.

production_dev_guards: imports/reload ownership move to test-env setUp; original production policy blocks remain production and all 401/403 checks and once-review/once-chart expectations are unchanged. Test-owned paths are preserved throughout. Only inner synthetic development login enables dev access explicitly. No auth/permission mock; chart fake now registered for restoring cleanup. This does not test production startup and does not change production policy. CORS/privacy retain complete original method ASTs, with storage_fixture setUp and pre-import gate added to sanitize host env. No common-helper or production edits, no transport/lifecycle workaround.

PY = D:/Project/Vibe/StockBoda/.venv/Scripts/python.exe, cwd dedicated worktree, starting HEAD 80659e1fb52e64718c1cade642cd1df5253d96be. Every command passed on its first attempt:

| Command | Result |
| --- | --- |
| `PY -B tests/run_isolated_tests.py tests.test_review_access` | 5 PASS; expected/unexpected violations 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_production_dev_guards` | 3 PASS; expected/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B tests/run_isolated_tests.py tests.test_cors_config tests.test_privacy_policy` | Separate A1 children, 2 + 2 PASS; each expected/unexpected 0/0; restored/patches_restored/cleanup true |
| `PY -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v` | 14 PASS; synthetic 9/27 expected/0 unexpected; SQLite 5/19 expected/0 unexpected; deliberate swallowed-violation child failures correctly detected with cleanup true |
| `PY -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit` | 1 + 3 PASS; expected/unexpected 0/0; restoration/patch restoration/cleanup true |
| `PY -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v` | PASS; existing list now 21 modules; raw imports fail before storage/main dependencies/files. Worker module excluded |
| Static names/counts/assertion/lambda AST comparison | PASS: original 13 = executed A2 12 + deferred B2 1. Worker full body/helpers identical; all assertions and lambda mock inputs/outputs unchanged; no skip/duplicate/loss |
| git diff --check and production/helper scope | PASS; backend/render/shared storage/API helper unchanged |

State evidence: per-case disposable full path set, named scenario patches over sanitized env, registered cleanup for module/sys.path/logger and function restoration, retained finally/closing blocks. No observed leakage. Approved helper failure-path results remain applicable; helpers unchanged, so no extra helper/full A2 reruns. No provider/network/background/lifespan or whole-suite execution. The only worker test is Deferred to H4-B2; other A2 candidates and B1/B2/C/D remain deferred.

Commit allowlist seven files: test_review_access.py, new test_review_access_concurrency.py, test_production_dev_guards.py, test_cors_config.py, test_privacy_policy.py, test_storage_fixture_runner.py and this plan. Full staged diff/names/whitespace review before `test: isolate local access and config tests`; no amend/push. Main remains unchanged with protected README hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. A2-7 ready for independent execution verification after commit; overall H4 not closed.

Independent read-only static review: no actionable finding. Confirmed review reloads inside snapshots, production 401/403 semantics, isolated dev session, unchanged fake/finally behavior and B2 exclusion. Reviewer did not execute/import tests or write files.


## H4-A2-8 source classification — 2026-09-15
A2-7 independently approved at bd718d1f300731526ff92324d50e8df22c89f04e. Resumed read-only analysis with clean dedicated worktree/branch/HEAD; no earlier A2-8 edits or executions. Main protected README hash unchanged. Reclassification: A2 16, B1 11 (original OpenAI transport 10 plus QA fallback override test lacking chart/provider fakes). build_advanced_ai_review calls _compact_chart_snapshot and then _contexts_for_trades before its fake OpenAI function; these reach build_journal_charts/get_stock_ohlcv. No new mock is added; defer this testcase intact.

- test_openai_review_retries_transient_rate_limit_once — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_timeout_is_configurable — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_applies_review_specific_output_limits — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_sends_review_specific_reasoning_effort — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_reasoning_effort_override_and_invalid_value_are_safe — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_disables_response_storage — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_output_limits_are_safely_bounded — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_records_token_usage_without_prompt_content — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_runtime_settings_have_upper_bounds — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_openai_review_reads_api_key_from_explicit_env_file — B1: OpenAI request/urlopen/retry/timeout/env-file boundary
- test_ai_review_uses_expected_default_model_ids — A2 SAFE: existing local builder fakes or pure guidance validation
- test_ai_review_model_ids_are_configurable — A2 SAFE: existing local builder fakes or pure guidance validation
- test_advanced_review_requests_readable_korean_indicator_terms — A2 SAFE: existing local builder fakes or pure guidance validation
- test_trade_guidance_validator_blocks_future_actionable_advice — A2 SAFE: existing local builder fakes or pure guidance validation
- test_trade_guidance_validator_allows_retrospective_review_language — A2 SAFE: existing local builder fakes or pure guidance validation
- test_rule_1_allows_negated_and_retrospective_mentions — A2 SAFE: existing local builder fakes or pure guidance validation
- test_rule_1_blocks_exact_independent_review_regressions — A2 SAFE: existing local builder fakes or pure guidance validation
- test_rule_1_blocks_target_term_and_price_notation_combinations — A2 SAFE: existing local builder fakes or pure guidance validation
- test_rule_1_blocks_trade_action_and_positive_predicate_combinations — A2 SAFE: existing local builder fakes or pure guidance validation
- test_rule_1_blocks_actionable_recommendations_with_categories — A2 SAFE: existing local builder fakes or pure guidance validation
- test_safety_rejection_records_only_rule_ids_and_internal_status — A2 SAFE: existing local builder fakes or pure guidance validation
- test_advanced_review_uses_configurable_fallback_model_after_primary_failure — A2 SAFE: existing local builder fakes or pure guidance validation
- test_advanced_review_override_can_disable_fallback_for_qa_comparison — B1: unmocked chart/market path before fake OpenAI call
- test_successful_openai_review_results_expose_plain_string_summaries — A2 SAFE: existing local builder fakes or pure guidance validation
- test_many_trades_keep_basic_episode_and_advanced_history_scopes_separate — A2 SAFE: existing local builder fakes or pure guidance validation
- test_advanced_review_targets_only_the_selected_round_trip — A2 SAFE: existing local builder fakes or pure guidance validation
- test_basic_review_anchors_verdict_and_changes_only_analysis_focus — A2 SAFE: existing local builder fakes or pure guidance validation

Split before execution: tests/test_ai_review_openai_client.py retains 16 A2 tests; tests/test_ai_review_openai_transport.py contains 11 B1 tests with original bodies/setup/teardown/response helper. No B1 import or execution. A2 reuses storage_fixture, _import_state, patch.dict module snapshot before reload and restoring patch.object for original fake expressions. No production/shared helper/framework changes. All five DB/cache/temp paths owned per testcase. Only A2 runner, A1 minimum and direct gate checks allowed; no full suite or next candidate.


### A2-8 validation and closeout
- `python -B tests/run_isolated_tests.py tests.test_ai_review_openai_client`: 16 PASS; violations/expected/unexpected 0; restored, patches_restored and cleanup true. Original local builder fakes prevent OpenAI/chart/market transport; no lifespan/background execution. Per-case owned storage/env and restoring module/function/import state replace the original partial environment cleanup.
- Static AST comparison against starting HEAD: 27 = 16 A2 + 11 B1, exact name union and disjoint split. Every A2 test method matches after normalizing only restoring patch.object registration back to the original function assignment. Assertions, inputs, expected values and fake bodies therefore match. Every B1 method plus setUp/tearDown/response helper matches exactly. No added skip, duplicate or loss. Deferred B1 retains its original transport patch lifecycle for later B1 migration; it was neither imported nor executed here.
- `python -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS, including intentional negative isolation probes.
- `python -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1 + 3 PASS; unexpected 0 and restoration/cleanup true.
- `python -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 22 A2 target modules. Only the local module was added to the existing gate target list; no deferred B1 import.
- Production and shared helpers unchanged. No full suite, provider/transport expansion, B1 execution, push or next-candidate work. Remaining A2 candidates and B1/B2/C/D remain deferred; overall H4 is not closed.
- Commit allowlist: tests/test_ai_review_openai_client.py, tests/test_ai_review_openai_transport.py, tests/test_storage_fixture_runner.py and this plan. Whitespace/full staged diff and Main README preservation checked before commit. Ready for independent A2-8 verification after commit.


## H4-A2-9 — OAuth/cache/mobile local isolation
A2-8 independently approved at 7e96b35d76d631cf903f8f3a150cf525fdee4620. Approved residual inventory: 97 A2 tests to finish in bounded A2-9 through A2-12 batches. Only A2-9 (19 local tests) is authorized now; A2-10/11/12 remain pending, B1/B2/C/D deferred.
Preflight: expected root/branch/HEAD, clean staged/unstaged/untracked; Main unchanged except protected user README, hash e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
Source classification: OAuth 15 = A2 10 (missing-token/config/redirect validation and original fake login with one-time ticket) + B1 5 (timeout, two profiles and two code exchanges). Theme 7 = A2 3 (two corporate-action calculations and file cache save with original calculated-results fake) + B2 4 (bounded executor/futures/worker calculations). Mobile 14 = A2 backend local 6 (cache configuration, direct synthetic route/cache responses and pure dates) + C 6 frontend/mixed source checks + D 1 Render source check + OUT 1 admin source check. No transport/refresh/provider fake redesign; worker-count arithmetic does not launch workers.
OAuth split preserves every method body and the existing restoring _replace helper. Local setUp uses storage_fixture, _import_state and module snapshot before reload, including fresh ticket dictionary/lock; deferred transport setup/body retained. All five DBs/cache/temp are owned; original nested temp paths remain under the case root. No excluded test is executed.


### A2-9 split and validation — 2026-09-15
| Original module | SAFE A2 retained | Separate excluded module | Excluded count |
| --- | ---: | --- | ---: |
| test_oauth_login.py | 10 | test_oauth_login_transport.py | B1 5 |
| test_theme_cache_memory.py | 3 | test_theme_cache_workers.py | B2 4 |
| test_mobile_runtime_recovery.py | 6 | test_mobile_runtime_source_checks.py | C 6 / D 1 / OUT 1 |

OAuth B1 names: test_oauth_request_timeout_setting_is_capped, test_kakao_access_token_profile_creates_alphamate_session, test_naver_access_token_profile_creates_alphamate_session, test_kakao_authorization_code_is_exchanged_before_login, test_naver_authorization_code_is_exchanged_before_login.
Theme B2 names: test_large_theme_fetch_keeps_outstanding_futures_and_results_bounded, test_worker_exception_still_exits_bounded_executor, test_multiple_periods_are_calculated_from_one_bounded_fetch_pass, test_period_returns_use_available_closes_and_exclude_tickers_without_two_rows.
Mobile C names: test_mobile_layout_stacks_navigation_and_content, test_production_journal_hides_developer_diagnostics, test_oauth_handles_cold_launch_url_once, test_theme_requests_timeout_and_retry, test_empty_journal_does_not_require_an_initial_api_round_trip, test_oauth_success_and_app_failure_stages_are_logged_without_credentials. D: test_render_uses_persistent_cache_and_bounded_workers. OUT: test_admin_can_trigger_and_inspect_initial_theme_cache.

- Each SAFE module executed separately with `python -B tests/run_isolated_tests.py tests.<module>` in order OAuth, Theme, Mobile: 10 PASS, 3 PASS, 6 PASS = 19. Every result: violations/expected/unexpected 0; restored, patches_restored, cleanup true. No failed attempt. Excluded modules were not imported/executed.
- Full test-method AST comparison against starting HEAD: OAuth 15=10+5, Theme 7=3+4, Mobile 14=6+8; combined 36=19+17. All names, bodies, assertions, inputs, expected values and nested fake definitions are exactly unchanged; no normalization needed, no skip/duplicate/loss.
- Theme snapshots backend.core.data_fetcher before reload, including the original body-local reload, and restores its globals/cache function objects. Existing calculated-results fake avoids executor/transport while real JSON file saving stays in testcase-owned temporary cache.
- Mobile uses storage_fixture, _import_state, data_fetcher snapshot/reload and api_module_state. Main reload creates fresh per-case theme cache objects; cleanup clears only the captured fresh cache method before restoring the original main dictionary. Original baseline cache object/content is never cleared or consumed. Data-fetcher globals/functions, sys.path, logger, env and all five DB/cache/temp paths restore through existing cleanup stacks even on exceptions. Existing request/refresh fakes are unchanged; pure date/worker-limit functions launch no worker. Lifespan is never entered.
- A1 minimum: `python -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS (intentional negative probes included). `python -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1+3 PASS, unexpected 0, restored/patches_restored/cleanup true.
- Direct gate: `python -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 25 local targets, adding only these three SAFE modules. No excluded test module was included.
- No production/shared helper/framework changes; no full suite, B1/B2/C/D/OUT execution or push. Remaining approved inventory after these 19 is 78 A2 tests reserved for A2-10 through A2-12; no automatic continuation.
- Commit scope: the three local modules, three split excluded modules, existing direct-entry coordinator and this ExecPlan (8 files). Main README preserved at e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61. Review full staged diff/names and whitespace before commit; independent verification is requested after commit.


## H4-A2-10 — local AI safety isolation
A2-9 independently approved at d1c73791628b40854a64c2377f0c63d3ac6f0ce8. Preflight matches expected dedicated root/branch/HEAD and clean index/worktree. Main retains only the protected README unstaged; blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
Final source classification: 19 = A2 17 + B1 2. test_finalization_failure_refunds_general_access_and_cleans_history_and_pending_key and test_finalization_failure_refunds_review_quota_exactly_once remain B1: enabled storage reaches _save_ai_review_history_if_enabled -> build_journal_charts without a chart fake. They are moved to test_ai_review_safety_finalization.py with original bodies, helpers and setup/teardown; neither is imported/executed here.
A2 route tests use original local builder fakes; synthetic dev users retain original storage-off default, so history returns before chart/provider access. Other tests cover disabled route, validation/limits, local semaphore, credit state and idempotency without network or workers. No new fake/provider bypass, auth weakening or production change.
Local test setup reuses storage_fixture and api_module_state: five DBs/cache/temp under each owned root, full sanitized env, main/stores snapshot before original helper reloads, sys.path/logger restoration. Reload creates fresh semaphore/limiter/cache/lock objects; original main dictionary and function references restore after body or setup failure. The legacy core.ai_review module has a restoring dictionary snapshot for its one original reload test. Original helpers and testcase bodies remain unchanged, including synthetic input/session and rate/concurrency settings.


### A2-10 validation and closeout — 2026-09-15
- `python -B tests/run_isolated_tests.py tests.test_ai_review_safety`: 17 PASS; violations/expected/unexpected 0; restored/patches_restored/cleanup true. No failed attempt. B1 finalization module never imported or executed.
- Full test-method AST comparison against starting HEAD: 19 = 17 local + 2 deferred, disjoint exact name union. All test bodies/assertions/inputs/expected values/nested fakes and all original module helper ASTs match exactly. Deferred setup/teardown is unchanged; no skip, duplicate or loss.
- A1 minimum `python -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS including intentional negative probes. `python -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1+3 PASS, unexpected 0 and restoration/cleanup true.
- Direct gate `python -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 26 local modules. Only tests.test_ai_review_safety was added; B1 module excluded.
- State review: body-internal helper reloads happen inside pre-registered main/store snapshots; direct builder/global assignments and idempotency dictionary mutations affect the fresh case objects. Original semaphore, limiter, cache, module functions and logger/path/env state restore via existing cleanup stacks. Real SQLite operations remain within disposable case paths. No actual provider/network/chart generation, background/lifespan or worker execution in A2.
- Production and shared helpers unchanged. Scope is tests/test_ai_review_safety.py, new tests/test_ai_review_safety_finalization.py, tests/test_storage_fixture_runner.py and this plan. Check full staged diff/names and git diff --check before commit. Main README remains e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
- B1 two finalization tests remain deferred for chart/provider isolation. Remaining A2 count from the approved 97-test inventory is 61 after A2-9 (19) and A2-10 (17); A2-11/12 and B1/B2/C/D deferred. No full suite/push/next batch. Ready for independent A2-10 verification after the scoped commit.


## H4-A2-11 — local billing readiness isolation — 2026-09-16
A2-10 independently approved at c8ede7169e09726908ca23e6939203e3a94b8436. Preflight matches dedicated root/branch/HEAD, clean index/worktree. Main protected README unchanged at e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
Source reclassification confirms 72 = A2 36 + B1 35 + OUT 1. Readiness/catalog uses local Credentials.from_service_account_info validation only; no refresh/request follows. Missing purchase configuration rejects before _google_play_headers. The verification_cannot_run testcase has a synthetic valid key but can reach credentials.refresh(Request()), so remains B1. All Google Play purchase/subscription/consume/acknowledge/refund/reconciliation and AdMob/OIDC verification scenarios remain B1 even with existing fakes. RTDN missing/invalid shared token and missing bearer reject before external verification; SSV missing-field rejection occurs before public-key fetch. Voided window is pure arithmetic.
Split: tests/test_billing_readiness.py retains A2 36; tests/test_billing_provider_verification.py preserves B1 35; tests/test_billing_source_contract.py preserves OUT 1. Excluded modules will not be imported/executed. No mock expansion or ledger/quota/auth assertion change.
Each A2 case reuses storage_fixture and _import_state plus restoring backend access_control/readiness module dictionaries before reload. Full test-owned DB/cache/temp/env, existing nested temp DB paths and close/finally semantics retained. Readiness path literals/absent path settings are inspected as configuration strings only, with no DB/file access at those values. No production/shared helper/framework changes.

Testcase classification:
- test_purchase_credit_ledger_schema_tracks_order_balances_and_usage_sources: A2
- test_purchase_credit_ledger_rejects_incomplete_order_evidence: A2
- test_purchase_usage_requires_an_existing_order_for_the_same_user: A2
- test_legacy_test_purchase_balances_are_reset_only_by_explicit_one_time_initialization: A2
- test_app_readiness_summarizes_deployment_without_secret_values: A2
- test_app_readiness_rejects_short_admin_token_without_exposing_value: A2
- test_app_readiness_reports_missing_settings_by_section: A2
- test_production_readiness_rejects_local_or_relative_data_paths: A2
- test_app_readiness_rejects_placeholder_release_values: A2
- test_app_readiness_rejects_unsafe_release_cors_origins: A2
- test_app_readiness_accepts_capacitor_android_https_origin: A2
- test_product_catalog_exposes_public_ids_and_readiness_only: A2
- test_product_catalog_matches_current_review_offers: A2
- test_ad_policy_caps_ads_per_advanced_ticket_setting: A2
- test_google_play_readiness_rejects_invalid_service_account_json: A2
- test_google_play_readiness_rejects_malformed_service_account_key: A2
- test_production_readiness_requires_google_play_product_ids: A2
- test_production_readiness_requires_purchase_token_encryption_key: A2
- test_production_readiness_rejects_duplicate_google_play_product_ids: A2
- test_production_readiness_requires_strong_rtdn_shared_token: A2
- test_production_readiness_rejects_placeholder_rtdn_oidc_settings: A2
- test_basic_and_advanced_rewarded_ad_progress_are_separate: A2
- test_basic_rewarded_ad_does_not_consume_purchased_pass: A2
- test_google_play_purchase_code_does_not_claim_subscription_verification_is_missing: OUT
- test_google_play_purchase_requires_server_configuration: A2
- test_google_play_purchase_does_not_grant_when_verification_cannot_run: B1
- test_verified_google_play_consumable_grants_credits_once: B1
- test_google_play_consumable_rejects_non_processed_order: B1
- test_google_play_purchase_verification_loads_actual_order_amount: B1
- test_purchase_credits_are_consumed_fifo_and_record_order_source: A2
- test_basic_purchase_credit_is_consumed_after_free_credits: A2
- test_purchase_credit_refund_restores_the_same_order: A2
- test_purchase_credit_consumption_rolls_back_when_wallet_save_fails: A2
- test_purchase_credit_consumption_rolls_back_when_snapshot_fails: A2
- test_google_play_full_refund_revokes_only_the_matching_order_once: B1
- test_google_play_canceled_order_revokes_remaining_credit_without_refund_amount: B1
- test_failed_review_refund_does_not_restore_credit_to_refunded_order: B1
- test_google_play_order_verification_reads_full_refund_details: B1
- test_google_play_purchase_stored_fields_are_length_limited: B1
- test_google_play_consumable_consume_failure_can_be_retried_without_duplicate_credits: B1
- test_google_play_purchase_rejects_wrong_product: B1
- test_verified_google_play_subscription_enables_pro_plan: B1
- test_google_play_subscription_stored_fields_are_length_limited: B1
- test_unacknowledged_google_play_subscription_is_acknowledged_before_pro_plan: B1
- test_failed_subscription_acknowledgement_does_not_enable_pro_plan: B1
- test_google_play_subscription_token_cannot_be_reused_by_another_user: B1
- test_expired_google_play_subscription_does_not_enable_pro: B1
- test_active_google_play_subscription_uses_pro_review_quota: B1
- test_pro_advanced_quota_is_consumed_before_purchased_pass: B1
- test_pro_billing_cycle_renewal_preserves_purchased_passes: B1
- test_canceled_pro_remains_active_until_play_expiry_without_resetting_quota: B1
- test_grace_period_keeps_pro_until_play_expiry: B1
- test_payment_hold_disables_pro_even_before_previous_expiry: B1
- test_inactive_subscription_refresh_disables_previous_pro_plan: B1
- test_rtdn_subscription_notification_refreshes_stored_subscription: B1
- test_rtdn_requires_shared_token: A2
- test_rtdn_shared_token_uses_constant_time_compare: A2
- test_rtdn_rejects_short_shared_token_in_production: A2
- test_rtdn_requires_oidc_when_configured: A2
- test_rtdn_accepts_valid_oidc_claims: B1
- test_admob_ssv_records_reward_once: B1
- test_admob_reward_status_can_be_polled_without_consuming_reward: B1
- test_admob_ssv_stored_fields_are_length_limited: B1
- test_admob_ssv_rejects_wrong_ad_unit: B1
- test_admob_ssv_accepts_signed_numeric_ad_unit_identifier: B1
- test_admob_ssv_accepts_console_verification_probe_without_recording_reward: B1
- test_pending_admob_reward_is_consumed_for_basic_review: B1
- test_pending_admob_reward_waits_until_immediate_free_credits_are_exhausted: B1
- test_admob_ssv_signature_requires_required_fields: A2
- test_admob_ssv_signature_content_decodes_percent_encoded_reward_text: A2
- test_voided_purchase_reconciliation_defaults_to_thirty_day_window: A2
- test_voided_purchase_reconciliation_handles_chargebacks_partial_refunds_and_item_failures: B1


### A2-11 validation and closeout
- `python -B tests/run_isolated_tests.py tests.test_billing_readiness`: 36 PASS; violations/expected/unexpected 0; restored, patches_restored, cleanup true. No failed test attempt. B1/OUT modules were not imported or executed.
- Full AST comparison against starting HEAD proves 72 = 36 + 35 + 1, unique exact name union, identical entire testcase bodies and original fake_service_account_json/patched_env helpers. Ledger integrity, explicit initialization, FIFO, refund-to-same-order, quota and rollback assertions/inputs/expected values unchanged; no skips or mock changes.
- No credential refresh, provider verification, HTTP/network, background or lifespan execution in A2. Local RSA/key validation is preserved; no real credentials/config files used. Readiness path placeholders remain inert strings, never accessed as storage. SQLite connections keep original try/finally closing and test-owned temp paths.
- Per-case sanitized storage environment and existing import/logger state contexts restore after success/failure. Backend access_control/readiness snapshots precede reload, so fresh locks/cache/globals and the test-local hmac replacement restore to their original references. Existing local rollback patches retain their context managers. Shared helpers and production remain unchanged.
- A1 minimum `python -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS (intentional negative probes included). `python -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1+3 PASS; unexpected 0 and restoration/cleanup true.
- Direct gate `python -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 27 local targets, adding only tests.test_billing_readiness. No B1/OUT execution or whole suite.
- Commit allowlist: tests/test_billing_readiness.py, tests/test_billing_provider_verification.py, tests/test_billing_source_contract.py, tests/test_storage_fixture_runner.py and this plan. git diff --check passed; full staged review/check and Main README preservation required before commit. README blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
- Remaining approved A2 inventory: 25 reserved for A2-12 (97 - 19 - 17 - 36). B1/OUT tests preserved, B2/C/D deferred; no push or automatic continuation. Ready for independent A2-11 verification after commit.


## H4-A2-12 — local release isolation — 2026-09-16
- A2-11 independently approved by the user at 4278b6f5e9302bbdf1e466079e1dde3a7581a1f1. A2-12 preflight confirmed this HEAD, fix/test-environment-isolation, the assigned test-isolation worktree and clean status. Main has only the protected README modification; blob e672a49f8cbf2da1d0c7492ff0e9c30b20b02a61.
- Current-source classification: backend_release_check 15 = 11 A2 + 4 D; release_alignment 7 A2; release_env_file_setup 5 = 3 A2 + 2 D; release_secret_generation 6 = 4 A2 + 2 D. Total 33 = 25 A2 + 8 D, with no loss, duplication or skip.
- D source/docs/wrapper assertions move unchanged to test_backend_release_check_docs.py, test_release_env_file_setup_docs.py and test_release_secret_generation_docs.py. Those modules were not imported or executed. This is test-scope separation, not a product behavior change.
- All four A2 modules reuse require_storage_boundary and storage_fixture in TestCase.enterContext. Each testcase owns the five DB paths, cache/config/temp and CWD; the fixture clears host configuration and restores env/CWD/temp even on failure. Alignment additionally restores sys.path with the existing context-managed patch pattern because its validator can insert the repository path. No shared helper or A1 foundation changes; the existing direct-entry coordinator only adds four local target names.
- Release validators are local calculations/report formatting; configuration is supplied synthetically in memory or explicit owned env files. Production-looking data paths and report paths are inert validation strings, not accessed as storage. RSA service-account material is generated synthetically in memory for format validation; no Google auth refresh, credential/provider verification or network transport is invoked.
- File-generation tests load tracked script source without calling main, and pass explicit testcase-owned roots. They create their own example templates and release files. No actual private release env, credentials, secret/signing files are read or changed; generated secret values stay in memory and are not printed. Ordinary tracked source/dependency reads are allowed. No wrapper, lifespan, worker or background execution.
- Static full testcase AST and original helper AST comparisons against starting HEAD passed across all 33 tests. Names, entire bodies, assertions, inputs/expected values and fake semantics are unchanged. No new mocks or authentication/provider bypasses.

### A2-12 testcase classification

tests/test_backend_release_check.py:
- test_format_owner_release_readiness_report_hides_secret_values: A2 SAFE
- test_owner_release_report_shows_top_level_release_errors: A2 SAFE
- test_owner_release_report_explains_missing_oauth_redirect_uri_inputs: A2 SAFE
- test_owner_release_report_explains_unsafe_data_storage_paths: A2 SAFE
- test_owner_release_report_explains_missing_data_storage_path_inputs: A2 SAFE
- test_owner_release_report_explains_missing_billing_ad_and_legal_inputs: A2 SAFE
- test_owner_release_report_lists_all_next_actions: A2 SAFE
- test_rejects_missing_production_backend_settings_without_secret_values: A2 SAFE
- test_rejects_missing_production_oauth_redirect_uris: A2 SAFE
- test_accepts_complete_production_backend_settings: A2 SAFE
- test_accepts_complete_settings_from_explicit_env_file: A2 SAFE

tests/test_backend_release_check_docs.py:
- test_backend_env_example_documents_release_check_settings: D deferred
- test_backend_release_env_template_is_production_focused: D deferred
- test_gitignore_blocks_filled_release_env_files: D deferred
- test_release_readiness_report_uses_release_env_files_when_present: D deferred

tests/test_release_alignment.py:
- test_rejects_when_no_release_settings_can_be_compared: A2 SAFE
- test_accepts_matching_backend_and_frontend_release_settings: A2 SAFE
- test_release_alignment_report_uses_readable_korean: A2 SAFE
- test_rejects_backend_oauth_app_scheme_that_differs_from_android_package_identity: A2 SAFE
- test_rejects_backend_oauth_app_scheme_that_differs_from_backend_package_even_without_frontend_value: A2 SAFE
- test_rejects_mismatched_backend_and_frontend_release_settings: A2 SAFE
- test_rejects_frontend_package_name_that_differs_from_fixed_android_package_identity: A2 SAFE

tests/test_release_env_file_setup.py:
- test_creates_private_release_env_files_from_templates: A2 SAFE
- test_does_not_overwrite_existing_private_values_but_appends_new_template_keys: A2 SAFE
- test_keeps_existing_private_release_env_files_when_template_keys_are_current: A2 SAFE

tests/test_release_env_file_setup_docs.py:
- test_double_click_batch_runs_release_env_setup_script: D deferred
- test_release_env_setup_script_uses_korean_owner_messages: D deferred

tests/test_release_secret_generation.py:
- test_generates_long_distinct_release_secret_values: A2 SAFE
- test_formats_output_without_writing_secret_files: A2 SAFE
- test_fills_empty_backend_release_secret_values_without_overwriting_existing_values: A2 SAFE
- test_fill_result_uses_korean_owner_messages: A2 SAFE

tests/test_release_secret_generation_docs.py:
- test_double_click_batch_runs_secret_generation_script: D deferred
- test_owner_docs_mention_secret_generation_helper: D deferred

### A2-12 validation
- Individually executed with `python -B tests/run_isolated_tests.py`: tests.test_backend_release_check 11 PASS; tests.test_release_alignment 7 PASS; tests.test_release_env_file_setup 3 PASS; tests.test_release_secret_generation 4 PASS. All four: violations 0 (expected/unexpected 0), restored true, patches_restored true, cleanup true. No failed target attempts.
- A1 minimum `python -B -m unittest tests.test_isolation_runner tests.test_isolation_results tests.test_isolation_sqlite -v`: 14 PASS, including intentional negative probes. `python -B tests/run_isolated_tests.py tests.isolation_smoke tests.test_rate_limit`: 1 + 3 PASS, unexpected 0 and restoration/cleanup true.
- Direct-entry coordinator `python -B -m unittest tests.test_storage_fixture_runner.StorageFixtureRunnerTest.test_direct_import_fails_before_storage_dependencies_or_files -v`: PASS across 31 local targets. All raw target imports fail closed before resource access. git diff --check passed; full staged diff/check and explicit nine-file allowlist review required before commit. No full suite or deferred D execution. Production, shared storage/API helpers and A1 guard/runner unchanged.
- The approved residual 97-test A2 plan has now executed 19 + 17 + 36 + 25 local tests in A2-9 through A2-12. Independent approval of A2-12 remains pending; this does not close H4. Existing B1/B2/C and D official wrappers/docs/orchestration/closeout remain deferred, as do source-only OUT items. This batch adds eight preserved D tests; no D/OUT validation is claimed.
