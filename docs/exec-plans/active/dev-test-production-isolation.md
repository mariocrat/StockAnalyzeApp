# StockBoda 개발·테스트·운영 환경 경계 분리 계획

### Goal

개발/debug/test라는 이름만으로 production API/data와 분리되었다고 가정하지 않도록 H1~H3 환경 경계를 단계적으로 보완한다. 이 문서는 같은 스레드에서 작성한 전체 계획과 이후 사용자가 축소 승인한 **Phase A: backend safety foundation**을 복원한 공식 ExecPlan이다. 새로운 환경 시스템을 설계하거나 전체 H1~H3 구현을 재승인하는 문서가 아니다.

H1은 frontend/Android/QA 빌드와 실제 API 대상의 불일치, H2는 환경 오류가 개발 접근·익명 저장 데이터 접근으로 이어지는 문제, H3는 환경파일 및 저장 경로 해석 불일치다. 1차 구현은 H2 및 backend H3 기반으로 한정한다. Phase A 완료가 H1 또는 전체 환경 격리 완료를 뜻하지 않는다.

### Scope

- Worktree: `D:\Project\Vibe\StockBoda.worktrees\env-isolation`
- Branch: `fix/dev-test-production-isolation`
- Current baseline HEAD: `5d999e83edc6c70048bdfbb564ab40dedafa4721`
- 최초 스레드 조사 baseline: `7614831e6634e84ac0542721aec03c634a2a2e8e`. 이후 축소 승인과 현재 baseline 보존 요구가 최초 전체 계획보다 우선한다.
- 이번 2026-09-11 작업은 이 ExecPlan 파일 작성만 허용한다. 애플리케이션·테스트·설정 코드 구현은 시작하지 않는다.
- 향후 구현 승인 범위는 backend 환경 판정, dev-access opt-in, 저장 매매 인증/ownership, 공통 환경 loader, CWD 독립적인 경로 해석, startup safety gate, 해당 변경의 격리된 집중 테스트뿐이다.
- 다른 worktree, 기존 사용자/개발자/production DB 및 실제 환경파일을 수정·복사하지 않는다. stage/commit/push/deploy는 별도 승인 없이는 수행하지 않는다.

작성 규칙은 [ExecPlan 규칙](../README.md), [개발 workflow](../../DEVELOPMENT_WORKFLOW.md), [테스트 안전 규칙](../../TESTING.md)을 따른다. 기존 active `credential-safe-access-logging.md`의 필수 section 구조를 따르며 completed에는 `.gitkeep`만 있다. Index에 새 active plan을 등록해야 한다는 규칙은 없다.

### Current Verified Baseline

2026-09-11 현재 worktree의 root/branch/HEAD/worktree list 및 전체 Git status를 읽기 전용으로 확인했다. 시작 시 staged/unstaged/untracked 변경은 없었다. 다음은 repository/static 증거이며 실제 production 반영 상태는 사용자 제공 정보다. Render나 외부 endpoint에 접근하여 검증하지 않았다.

| 항목 | 현재 소스에서 확인한 사실 / 보존할 계약 |
| --- | --- |
| H2 환경 판정 | `backend/core/account_store.py`, `access_control.py` 등에서 production 문자열을 개별 비교한다. 개발 로그인은 production만 차단하고, dev-access flag 누락도 허용하는 분기가 남아 있다. |
| H2 저장 매매 | `backend/main.py`의 `_persistent_journal_user()`는 non-production에서 인증 실패를 삼키는 `_optional_session_user()`를 사용한다. 사용자 없는 저장 매매 분기가 전체 DB 접근으로 이어질 수 있다. |
| H3 loader | `backend/core/env.py`는 process, 지정 파일, root/backend `.env`를 키별로 보충한다. `journal.py`의 독자 loader는 `ALPHAMATE_ENV_FILE`을 읽지 않는다. |
| H3 path | DB별 설정 누락 fallback과 상대경로가 존재한다. 기존 절대 production 경로를 재배치할 이유로 취급하지 않는다. |
| Startup/cache | `main.py` lifespan은 중앙 환경 검증 없이 scheduler를 시작한다. `journal_chart.py`에는 import 시 yfinance cache 디렉터리 생성이 있고, 시장 cache는 process 환경을 별도로 읽는다. |
| `937d775` | `fix: harden credential-safe logging`. Credential redaction, query 없는 HTTP summary, Uvicorn error 정리와 `--no-access-log`를 보존한다. 환경 오류 로그도 비밀값을 출력하지 않아야 한다. |
| `abdbfd1` | `fix: support debug OAuth callback scheme`. Backend OAuth debug callback scheme 허용 hotfix를 보존한다. 정상 callback/scheme 선택과 protocol을 재설계하지 않는다. |
| `5d999e8` | `chore: pin production auto-deploy off`. `render.yaml`의 `autoDeployTrigger: off`, startup의 `--no-access-log`, `healthCheckPath: /healthz`를 보존한다. |
| Health | 기존 `/healthz` 및 `/api/healthz`의 응답 계약을 보존한다. 최초 전체 계획의 frontend handshake용 environment 필드 추가는 이번 Phase A 필수 작업이 아니다. |

H1의 과거 스레드 조사에서는 일반 debug가 release Vite mode의 mobile build를 사용하고, OAuth/AdMob QA가 production 공개 설정을 쓰면서 development 표시를 덮어쓰는 경로를 확인했다. Vite mode, API 대상, 광고 테스트 정책이 분리되지 않은 문제가 후속 범위다. 이번 문서 작업에서 APK/AAB나 실제 API 연결을 재검증하지 않았다.

### Decisions

#### 승인 범위와 환경 의미

- 실제 허용 문자열은 기존 승인대로 `development`, `test`, `production`이다. dev/test/prod는 설명용 약칭이며 `dev`/`prod` alias를 새로 추가하지 않는다.
- 공백 제거와 대소문자 정규화 후 중앙에서 판정한다. 누락·빈 값·오타·unknown을 development로 fallback하지 않는다.
- 환경 설정 실패 또는 production 판정 실패는 개발 기능 허용 근거가 될 수 없다. 환경 이름을 hostname, debug 여부, 실행 CWD로 추측하지 않는다.
- `ALPHAMATE_ENV`, `ALPHAMATE_ENV_FILE`, `ALPHAMATE_ALLOW_DEV_ACCESS`, 기존 DB 설정 등 기술 식별자를 rename하지 않는다.

#### Dev access와 인증/ownership

- Development/test라는 사실만으로 개발 로그인·기본 개발 토큰·권한 우회를 열지 않는다. 해당 환경과 명시적으로 true인 dev-access 조건을 모두 요구한다. 누락/false는 비활성이다.
- Production의 dev-access=true는 startup 검증 실패다. Test의 개발 동작도 격리된 fixture가 명시적으로 활성화한 경우만 허용한다.
- 저장된 사용자 매매의 조회·추가·삭제·복기·차트는 유효한 사용자 세션과 ownership을 요구한다. 인증 실패가 사용자 ID 없는 전체 조회/삭제로 내려가지 않게 한다.
- OAuth/auth 설정 부재·실패를 anonymous/local/stored-user 인증으로 대체하지 않는다. 정상 OAuth protocol, callback query, debug callback scheme hotfix, 정상 로그인 및 review-login 정책은 유지한다.
- 저장 opt-in과 AI consent 및 기존 사용자별 권한을 유지한다. 요청 본문으로 계산하는 일회성 분석처럼 사용자 저장 DB가 필요 없는 기능을 불필요하게 차단하지 않는다.
- 최초 전체 계획에 있던 `build_review()` 등 fallback의 일괄 제거는 승인되지 않았다. 먼저 실제 인증 없는 저장소 접근 호출 경로를 증명하고, 그 경로 차단에 직접 필요한 변경만 한다. Route에서 안전한 명시 입력을 전달하는 것으로 해결되면 관련 없는 내부 fallback refactor는 제외한다.

#### Environment loader와 경로

- 명시적 `ALPHAMATE_ENV_FILE`은 backend 애플리케이션 설정의 단일 출처다. 다른 `.env`나 process의 애플리케이션 값을 누락 키에 조용히 보충하지 않는다. 지정 파일 부재/읽기 실패는 설정 오류로 취급한다.
- 파일을 지정하지 않은 실행은 process 설정을 사용한다. 암묵적인 root/backend `.env` 탐색에 의존한 개발 실행은 명시적으로 파일을 선택해야 한다. Render의 process 기반 운영 방식 자체를 교체하지 않는다.
- 모든 DB 모듈이 같은 loader 계약을 사용하며 journal의 독자 해석을 제거한다. 단일 실행에서 각 모듈이 다른 출처의 값을 소비하지 않도록 한다.
- 상대 환경파일 경로는 repository root 기준으로 해석한다. 상대 저장 경로도 CWD가 아닌 명시적으로 정한 공통 기준으로 해석하며, 선택 출처·환경과 최종 경로를 값 노출 없는 방식으로 검증한다.
- Development의 격리 기본 경로와 test의 명시적 temporary 경로는 환경별로 구분한다. Test DB는 허용된 임시 root를 벗어나지 않도록 검증하며, 경로 정규화/탈출 및 서로 다른 DB의 경로 충돌을 검사한다.
- 현재 production의 절대 DB 경로·schema·data는 이동·복사·변경하지 않는다. 실제 운영 상태 확인 없이 production DB/cache 설정을 새 필수값으로 강제하지 않는다. 최초 전체 계획의 운영 필수 경로 강화안은 이번 축소 승인에 포함되지 않는다.
- Cache/storage도 CWD에 우연히 좌우되지 않아야 한다. 다만 cache 전체 구조 통합이나 production cache 재배치는 하지 않는다. Invalid startup에서 cache 쓰기가 발생하는 순서 문제와 집중 테스트 격리에 직접 필요한 부분만 다룬다.

### Phase A Implementation Steps

아래는 향후 구현 순서이며 현재 모두 미착수다. 환경 판정만 고친 상태에서 journal loader 불일치를 남긴 결과를 완료·배포하지 않는다. 한 worktree의 backend safety foundation 변경으로 연결해 검증한다.

1. **공통 환경/설정 기반:** `core/env.py`와 관련 소비 지점을 확인하고 순수 환경 판정 및 설정 검증을 중앙화한다. 명시 파일 단일 출처와 process-only 실행 계약을 먼저 집중 테스트로 고정한다. 설정 오류 메시지는 이름/오류 종류만 포함한다.
2. **DB loader/path 정렬:** account/access/journal/review-history/event-log의 최종 경로를 같은 규칙으로 해석한다. CWD 변경에도 경로가 같고 test가 임시 경로만 사용할 수 있게 한다. 기존 production 경로 정책을 강화하거나 schema를 바꾸지 않는다.
3. **Dev/auth 경계:** 개발 로그인·우회를 명시적 opt-in으로 제한하고 저장 매매 route의 인증 실패 fallback을 제거한다. 다른 사용자 행의 조회·수정·삭제 불가 및 저장 off 정책을 검증한다. OAuth 정상 흐름과 debug callback hotfix를 보존한다.
4. **Startup safety gate:** DB 초기화, scheduler/background task, cache/persistent 쓰기보다 검증을 앞에 둔다. Lifespan만이 아니라 그 이전 module import 부작용도 추적한다. 필요한 초기화 순서 조정에 한정하고 cache architecture를 통합하지 않는다.
5. **집중 검증과 review:** 격리된 신규 테스트와 안전성이 확인된 관련 기존 테스트만 실행한다. 전체 diff, `git diff --check`, allowlist/status, logging/OAuth/Render 회귀를 검토하고 구현자와 구분된 독립 review를 받는다. 결과와 남은 한계를 이 plan에 기록한다.

### Current Status

2026-09-11 구현 재개 및 중단 기록:

- 사용자 후속 지시로 Phase A 구현이 승인되었다. 위 문서 작성 당시의 단일 파일 제한은 이번 구현 승인으로 대체되며 Deferred는 그대로 유지한다.
- 시작 branch/HEAD/main/origin-main은 지정 baseline과 일치했다. 시작 변경은 이 untracked ExecPlan 하나뿐이었다.
- 중앙 환경 enum/명시 파일 단일 출처, 다섯 DB 경로 검증, dev-access opt-in, 저장 매매 route의 필수 인증, import/lifespan 선행 gate 및 지연 yfinance cache 초기화 코드를 작성했다. 아직 검증 완료가 아니므로 아래 구현 완료 체크는 유지한다.
- Test 경로 검증을 위해 `ALPHAMATE_TEST_ROOT`를 추가했다. Test에서는 다섯 DB와 cache 경로를 모두 명시하고 system temporary directory 아래 root 및 경로 탈출/충돌을 검사한다. Development 기본 데이터/cache는 기존 backend 경로 아래 development 하위 디렉터리다. Production 기본 경로와 기존 yfinance cache 위치는 보존한다.
- `tests/phase_a_isolation.py`, `tests/test_phase_a_environment.py`, `tests/run_phase_a_tests.py`를 작성했다. 임시 root 밖 쓰기/DB 접근, socket 및 requests/curl transport 외부 통신을 차단한다. 사용자의 실제 환경파일은 읽거나 수정하지 않았다.
- 테스트 두 번 실패 후 사용자 지시대로 추가 구현/테스트 반복을 중단했다. 집중 검증 및 독립 review는 완료되지 않았다.

- [x] 이전 스레드의 전체 방향 및 이후 Phase A 축소 승인 복원
- [x] 현재 root/branch/HEAD/status 및 ExecPlan 형식 확인
- [x] 현재 baseline의 logging/OAuth/Render 보호사항 정적 확인
- [x] Phase A와 Deferred를 구분한 공식 ExecPlan 작성
- [x] Phase A 환경/loader/path 구현
- [x] Phase A dev-access/auth/ownership 구현
- [x] Phase A startup safety gate 구현
- [x] 집중 격리 테스트 및 관련 회귀 검증
- [x] 구현 diff 독립 review 및 Phase A 완료 판정
- [ ] H1/frontend/Android/QA 후속 단계 (현재 구현 범위 밖)

문서 영구화 완료와 제품 구현 완료를 구분한다. 과거 plan이나 logging hotfix의 테스트 통과 수치를 Phase A 결과로 재사용하지 않는다.

### Verification

#### 최종 독립 재검증 승인 — 사용자 제공 결과

- A-MAJ-01: RESOLVED / A-MIN-01: RESOLVED
- Independent runner: 87 passed / 0 failed / 0 errors / 0 skipped
- Blocker / Major / Minor: 0 / 0 / 0
- 검증 전후 repository 변경 없음. Independent verdict: 승인 가능.
- Phase A 구현 및 독립 검증 완료. 이번 commit 준비에서는 이 승인 기록만 최소 갱신하며 runner를 반복하지 않는다.
- 후속 main 통합·push·production 검증은 이번 승인 범위 밖이며 별도 검토가 남아 있어 plan은 active에 유지한다. Deferred는 완료 처리하지 않는다.

#### 독립 검증 finding 보완 — 2026-09-11

사용자가 제공한 독립 검증 판정은 Blocker 0 / Major 1 / Minor 1, 수정 후 재검증 필요였다. 이번 보완의 시작 root/branch/HEAD는 지정값과 일치했고 기존 tracked modified 12개, untracked 4개, staged 없음 상태를 보존했다. 수정 범위는 `tests/phase_a_isolation.py`, `tests/test_phase_a_environment.py`, `tests/test_oauth_login.py`, `tests/run_phase_a_tests.py` 및 이 Progress 기록뿐이다. 시작/종료의 backend 및 render.yaml diff가 동일함을 비교했다. Application code 추가 변경은 없다.

- **A-MAJ-01 수정:** 누락된 `socket.gethostbyname`, `socket.sendto`와 관련 reverse DNS/name lookup(`gethostbyaddr`, `getnameinfo`) 및 `sendmsg` audit event를 거부한다. 기존 connect/getaddrinfo 차단과 requests/curl-cffi transport 차단을 유지한다. 설치된 Python `_socket` binary에서 connect/getaddrinfo/gethostbyname/gethostbyaddr/getnameinfo/sendto event 이름을 읽기 전용으로 확인했다. 이 Windows binary에는 sendmsg가 없지만 해당 event가 발생하는 플랫폼에서도 거부하도록 명시했다.
- **Local 정책:** 임의의 127/8, ::1, localhost 접근을 더 이상 허용하지 않는다. 실제 설치된 Python의 `_fallback_socketpair` 소스를 확인하고, socketpair 함수 실행 context에서만 127.0.0.1/::1의 ephemeral TCP listener bind와 그 listener의 실제 주소/port로 연결하는 한 번의 peer connect를 허용한다. ContextVar를 사용해 다른 실행 context에 허용 상태를 공유하지 않고 finally에서 원복한다. 복잡한 별도 network sandbox는 만들지 않았다.
- **A-MAJ-01 검증:** sys.audit synthetic probe로 external connect/getaddrinfo/gethostbyname/sendto 및 reverse DNS/sendmsg 거부를 확인했다. 이 probe는 DNS 조회나 packet 전송을 하지 않는다. 실제 Windows socketpair의 local 데이터 송수신, asyncio event loop, FastAPI ASGI 요청은 통과했다. 임의 loopback bind/connect/sendto는 거부됨을 확인했다.
- **A-MIN-01 수정:** OAuth 테스트의 requests.get/post, _request_json, _exchange_json, login_oauth_code 직접 fake 대입을 patch.object + addCleanup으로 교체했다. 불필요한 importlib.reload를 제거하여 함수 identity와 모듈 상태를 reset하지 않으며, 테스트별 process env도 addCleanup으로 복원한다. 모든 module global을 snapshot/restore하는 wrapper는 추가하지 않았다.
- **A-MIN-01 검증:** fake를 사용하는 OAuth 테스트 6개를 정방향/역방향으로 실행하고 각 case 종료 시 원래 함수 identity/env/tempfile을 확인했다. 의도적인 assertion 실패 뒤에도 cleanup이 수행됨을 검사했다. Runner의 마지막 검사도 알려진 patch 대상의 identity와 env/tempfile.tempdir/socketpair/sys.path가 시작 상태와 같은지 관측만 하며 강제 복원하지 않는다.
- 작은 harness 검사에서 tempfile.tempdir의 최초 초기화가 None으로 원복되지 않는 문제가 한 번 재현됐다(5개 중 1 failure). TemporaryDirectory 생성 바깥에서도 기존 tempdir 값을 보존하도록 수정 후 재실행하여 5개 모두 통과했다. 동일 문제의 두 번째 실패는 없었다.

실행 위치는 이 worktree, 실행기는 `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`이며 아래 인자로 실행했다. 모든 DB/cache는 임시 root를 사용했고 실제 외부 서비스·production DB·사용자 환경파일에 접근하지 않았다.

| 인자 | total | passed | failed | errors | skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| `-B -m unittest -v tests.test_phase_a_environment.PhaseAHarnessTest` (tempdir 원복 보완 전) | 5 | 4 | 1 | 0 | 0 |
| 위 명령 (원복 보완 후) | 5 | 5 | 0 | 0 | 0 |
| `-B -m unittest -v tests.test_phase_a_environment.PhaseAOAuthCleanupTest` | 2 | 2 | 0 | 0 | 0 |
| `-B -m unittest -v tests.test_phase_a_environment` | 27 | 27 | 0 | 0 | 0 |
| `-B -m tests.run_phase_a_tests tests.test_oauth_login` | 16 | 16 | 0 | 0 | 0 |
| `-B -m tests.run_phase_a_tests` | **87** | **87** | **0** | **0** | **0** |

최종 runner는 10.018초, exit 0이었다. 27 Phase A + 59 기존 OAuth/logging/Render 회귀 + 1 종료 상태 검사로 구성된다. Cleanup 실패 경로 검사의 내부 의도적 assertion은 바깥 테스트가 성공적으로 검증한 fixture이며 runner failure가 아니다. 기존 credential-safe logging, OAuth debug scheme, Render off/no-access-log/health 계약은 회귀로 보존했다.

Self-review: A-MAJ-01/A-MIN-01은 구현자 검증에서 해결됐으며 추가 Blocker/Major/Minor는 확인하지 않았다. Python audit와 검토한 HTTP transport 경계의 집중 테스트이지 임의 native library/child process 전체를 위한 범용 보안 sandbox라고 주장하지 않는다. 독립 재검증, 전체 H4 및 기존 Deferred 범위는 남아 있다. Plan은 active로 유지하며 Phase A 완료 승인/독립 재검증 체크를 완료 처리하지 않는다. Git 상태는 modified 13개, untracked 4개, staged 없음이며 commit/push/deploy/stash/Render 접근/다른 worktree 파일 변경은 수행하지 않았다.

#### Harness 수정 및 Phase A 집중 검증 완료 — 2026-09-11

사용자가 harness 수정과 Phase A 검증 재개를 승인했고 독립 검증은 다음 단계로 분리했다. 재개 시작 상태는 지정 baseline, tracked modified 12개, 이 계획과 테스트 3개의 untracked, staged 없음으로 일치했다. Canonical 환경은 Decisions의 `development` / `test` / `production`과 구현이 일치하여 변경하지 않았다. `dev` / `prod` alias는 추가하지 않았다.

Harness는 socketpair 실행 중 전역 예외를 두던 방식에서 loopback 목적지의 bind/connect와 local DNS만 허용하는 경계 검사로 교체했다. 외부 DNS/IP 연결, requests와 curl-cffi HTTP transport, subprocess는 차단한다. 임시 root 밖 파일 쓰기/SQLite 접근도 차단하고 모든 DB/cache 및 프로세스 설정을 격리한다. 실제 provider나 production에는 접속하지 않았다. Windows asyncio event loop 및 실제 FastAPI ASGI 메시지의 200 응답과 외부 접근 거부를 별도 harness 테스트로 확인했다.

CWD 테스트는 선택한 파일의 절대경로를 repository/backend/임시 CWD에서 비교한다. 상대 env-file 선택은 임시 repository root를 지정해 확인하므로 C:와 D: 간 relpath 계산이 없다. 다섯 DB 모듈의 실제 임시 SQLite 생성도 선택한 파일 경로만 사용하는지 확인했다.

이번 재개에서 추가 수정한 application 파일은 `backend/core/env.py`뿐이다. 아래 두 결함을 먼저 테스트로 재현한 뒤 수정했다.

| 실패한 테스트 | 기대 / 실제 / 수정 |
| --- | --- |
| test_test_dev_access_requires_complete_isolation | Test opt-in이라도 임시 root/DB/cache 누락 시 거부해야 하나 true를 반환했다. Test dev-access 활성 판정 전에 같은 설정 snapshot의 경로 검증을 수행하도록 변경했다. |
| test_drive_relative_paths_cannot_depend_on_drive_cwd | Windows `C:filename`은 drive CWD에 의존하므로 거부해야 하나 허용했다. Env-file/storage 해석기에서 drive가 있고 absolute가 아닌 경로를 거부했다. |

두 재현 테스트는 수정 전 2 tests / 4 subtest 포함 failures, 수정 후 2개 통과했다. Harness 자체의 첫 실행에서 SQLite context manager가 연결을 닫지 않아 WinError 32가 발생한 것은 `closing()`으로 테스트에서 해결했다. 합산 실행 중 `core.env`와 `backend.core.env`의 예외 클래스 identity가 달라 발생한 assertion 오류도 실제 DB 모듈이 사용하는 ConfigurationError를 검사하도록 테스트에서 수정했다. 이 두 infrastructure 문제 때문에 application 코드를 변경하지 않았다.

모든 명령은 이 worktree에서 실행했다. 아래 `PY`는 `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`이다. 실행 인자는 모두 `-B`로 시작한다. 런타임 stub이나 실제 HTTP 서버 대신 설치된 FastAPI의 ASGI application을 메시지로 호출하며, 시장 차트 계산은 mock으로 사용자 입력 경계를 검사했다.

| 순서 | PY 뒤 실행 인자 | tests / passed / failures / errors / skipped |
| --- | --- | --- |
| 1 | `-B -m unittest -v tests.test_phase_a_environment.PhaseAHarnessTest` | 3 / 2 / 0 / 1 / 0 (SQLite fixture 미종료) |
| 2 | 위 명령, fixture 연결 종료 수정 후 | 3 / 3 / 0 / 0 / 0 |
| 3 | `-B -m unittest -v tests.test_phase_a_environment.PhaseAEnvironmentTest` | 9 / 9 / 0 / 0 / 0 |
| 4 | `-B -m unittest -v tests.test_phase_a_environment.PhaseAApplicationTest.test_dev_login_and_default_token_require_opt_in tests.test_phase_a_environment.PhaseAApplicationTest.test_invalid_import_precedes_application_imports_and_persistent_effects tests.test_phase_a_environment.PhaseAApplicationTest.test_lifespan_validates_before_cache_and_background tests.test_phase_a_environment.PhaseAApplicationTest.test_cache_import_is_pure_and_initialization_uses_test_root` | 4 / 4 / 0 / 0 / 0 |
| 5 | `-B -m unittest -v tests.test_phase_a_environment.PhaseAApplicationTest.test_asgi_auth_failure_never_reaches_stored_journal tests.test_phase_a_environment.PhaseAApplicationTest.test_asgi_ownership_and_storage_opt_in tests.test_phase_a_environment.PhaseAApplicationTest.test_once_analysis_does_not_access_stored_journal` | 3 / 3 / 0 / 0 / 0 |
| 6 | `-B -m tests.run_phase_a_tests tests.test_oauth_login tests.test_credential_safe_logging tests.test_event_log tests.test_render_blueprint` | 59 / 59 / 0 / 0 / 0 |
| 7 | `-B -m unittest -v tests.test_phase_a_environment.PhaseAEnvironmentTest.test_test_dev_access_requires_complete_isolation tests.test_phase_a_environment.PhaseAEnvironmentTest.test_drive_relative_paths_cannot_depend_on_drive_cwd` | 2 / 0 / 4 (subtests 포함) / 0 / 0 (결함 재현) |
| 8 | 위 명령, 중앙 설정 모듈 수정 후 | 2 / 2 / 0 / 0 / 0 |
| 9 | `-B -m unittest -v tests.test_phase_a_environment` | 23 / 22 / 0 / 1 / 0 (두 import namespace의 예외 클래스 identity) |
| 10 | 위 명령, 테스트의 예외 클래스 검사 수정 후 | 23 / 23 / 0 / 0 / 0 |
| 11 | `-B -m tests.run_phase_a_tests` | **82 / 82 / 0 / 0 / 0**, 8.321초, exit 0 |

최종 82개 구성: Phase A 23, credential-safe logging 11, Render 7, event-log 26, OAuth 15. 개별 실행 수치는 단계별 증거이며 합산해 별도 테스트 개수로 주장하지 않는다.

완료 기준별 증거:

- Environment 허용값/정규화와 missing/empty/typo/unknown 거부, dev/test opt-in 및 production opt-in 거부: environment matrix와 실제 dev login/default token 검사.
- Loader/CWD: 선택 파일 단일 출처, process 충돌 및 누락 키 보충 없음, 파일 부재/읽기 실패, 다섯 DB 공통 loader와 실제 임시 파일 생성, 절대/상대 선택의 CWD 독립성.
- Paths: development/prod 기본 경로 보존·분리, test 명시 경로 필요, `..` root escape·DB/cache collision·drive-relative 거부. Production 기본 경로 검사는 경로값만 비교하며 해당 디스크를 열지 않는다.
- Auth/ownership: 3개 환경에서 무인증/invalid/expired 세션 × 저장 매매 GET/POST/DELETE/복기/차트 54개 ASGI 거부 시나리오, A/B 합성 사용자의 조회·쓰기·다른 사용자 삭제 차단·자기 데이터 전체 삭제, 저장 off 및 복기/차트 입력 격리. 일회성 빈 요청 분석은 저장 매매 DB 없이 성공한다.
- Startup: invalid/missing/empty 환경, prod dev-access, root escape, collision, unreadable env 파일에서 import 실행이 DB connect/mkdir/thread start 전에 실패한다. Lifespan에서도 validation이 cache/background/DB보다 앞선다. Journal chart import 자체는 mkdir/yfinance cache 설정을 수행하지 않는다.
- OAuth: 설정 부재가 identity 생성으로 이어지지 않음, 기존 OAuth 15개, Kakao/Naver의 release/debug/unapproved scheme 선택과 code/state 전달·ticket 소비를 세 환경에서 추가 검증.
- Logging/Render: credential query 입력 보존과 raw query 비출력, code/state/ticket 등 redaction, 안전한 summary 회귀 통과. `render.yaml`, `credential_redaction.py`, `http_access_log.py`는 baseline과 diff 없음. `autoDeployTrigger: off`, `--no-access-log`, `/healthz` 정적 계약 및 두 health ASGI 응답을 확인했다.

Self-review: Phase A 범위에서 미해결 Blocker/Major는 발견하지 않았다. Minor로 남길 제품 결함은 확인하지 않았으나 이 판단은 독립 검증이 아니다. Optional session helper는 저장 매매 route에서 제거되었고, 남은 호출은 저장을 건너뛰거나 client-event 사용자 표시에 쓰인다. Backend application 설정의 process 직접 읽기는 공통 loader 외 배포 revision 표시 및 OS temp 기반 경로 판정뿐이다. 광범위 H4/외부 SDK 전체 격리, H1/H5/H6/H7, production/device/provider 검증은 Deferred다.

Git 검증: tracked `git diff --check` 오류 없음. 최종 변경은 tracked modified 12개와 untracked plan/테스트 4개, staged 없음이다. Commit/push/deploy/Render 접근 및 다른 worktree 파일 변경은 수행하지 않았다. Plan은 active에 유지하고 독립 review 완료 체크는 비워 둔다.

#### Phase A 구현 시도 — 2026-09-11

실행 위치는 이 worktree이며 Python은 기존 `D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe`를 `-B`로 사용했다. 다른 worktree의 설정/DB 복사나 파일 수정은 수행하지 않았다. 실제 FastAPI runtime은 있고 httpx는 없어 ASGI 메시지로 요청을 전달하는 테스트를 작성했다.

1. `& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -B -m unittest tests.test_phase_a_environment`: 16 tests, failures=57, errors=3으로 실패했다(subtest 실패 포함). Windows asyncio가 내부 socketpair를 만드는 과정의 `socket.bind`를 harness가 차단해 ASGI 검증이 실패했다. 출력이 잘려 첫 실행의 나머지 오류 세부는 모두 확보하지 못했다. 이 결과는 제품 인증 실패의 증거가 아니다.
2. Harness에서 socketpair 생성 중의 loopback bind/connect만 허용하도록 수정한 뒤 `& 'D:\Project\Vibe\StockBoda\.venv\Scripts\python.exe' -B -m unittest -v tests.test_phase_a_environment.PhaseAEnvironmentTest`: 9개 중 8개 통과, 1개 error. `test_cwd_does_not_choose_env_or_storage`의 `os.path.relpath`가 C: 임시 파일과 D: repository 사이에서 `ValueError: path is on mount 'C:', start on mount 'D:'`로 실패했다.

두 번 실패 규칙에 따라 세 번째 실행은 하지 않았다. Socketpair 수정 이후 ASGI/lifespan 테스트는 재검증하지 않았다. OAuth/event-log/credential-safe logging/Render 회귀 runner는 아직 실행하지 않았다. 다음 시도는 drive별 fixture로 상대경로/CWD 검증을 분리하고 harness 자체를 먼저 검증하는 접근이 필요하다. 미검증 구현을 완료 또는 배포 가능으로 판단하지 않는다.

#### 향후 Phase A 검증 기준

| 시나리오 | 필요한 증거 |
| --- | --- |
| Development/test/production 및 정규화 | 허용 환경만 정확히 판정하고 대소문자/공백은 정규화함 |
| Missing/empty/invalid 환경 | 개발 fallback 없이 실패하고 DB/cache 쓰기 및 scheduler 시작이 없음 |
| Dev access | Dev/test의 flag true/false/누락, production의 true 거부 및 false 정상 경계 |
| 명시 환경파일 | 다른 파일/process에 충돌 값을 넣어도 보충되지 않음; 지정 파일 부재/읽기 오류 거부 |
| Loader consistency | journal 포함 다섯 DB가 같은 설정 출처를 사용함 |
| CWD independence | root/backend/임시 CWD에서 같은 입력의 최종 경로가 동일함 |
| Temporary isolation | 모든 DB가 임시 root 내부이며 탈출·DB 간 경로 충돌을 거부함 |
| Auth fail-closed | 무인증·만료/잘못된 세션·auth 설정 실패가 전체 조회/삭제 또는 다른 저장 사용자로 fallback하지 않음 |
| Ownership | 합성 사용자 A/B 데이터 격리, 저장 opt-in 유지, 사용자별 조회/쓰기/삭제 |
| 일회성 분석 | 명시 요청 본문 기반 기능이 저장 DB 접근 없이 기존 기능을 유지함 |
| Invalid startup | Import부터 startup까지 DB 초기화·scheduler·background·cache 쓰기 이전 실패를 관측함 |
| OAuth regression | 정상 callback 입력과 debug scheme 선택 hotfix를 mock/static 및 격리 가능한 테스트로 보존함 |
| Logging regression | 합성 credential이 설정 오류/event/traceback에 노출되지 않고 기존 redaction 및 안전한 summary가 유지됨 |
| Runtime 정적 계약 | `autoDeployTrigger: off`, `--no-access-log`, `/healthz` 보존 및 Render 변경 없음 |

설정 순수 테스트, DB 집중 테스트, 실제 ASGI/HTTP 경계 증거를 구분한다. 함수 직접 호출이나 runtime stub만으로 실제 HTTP 동작을 통과 처리하지 않는다. 관련 기존 후보는 `tests/test_oauth_login.py`, `tests/test_credential_safe_logging.py`, `tests/test_event_log.py`, `tests/test_render_blueprint.py`이며 파일 이름만으로 실행 안전성을 보장하지 않는다. 실행 전 import·fixture·DB/cache·환경·network 효과를 확인하고 안전한 subset만 선택한다.

구현 후 전체 diff와 미추적 파일을 함께 검토하고 `git diff --check`, 변경 범위, 최종 Git status를 확인한다. 새 파일은 일반 diff에 안 나오므로 별도 원문/no-index 검사를 한다. 실제 사용한 명령·실행 위치·revision·결과·미검증을 기록한다.

#### 문서 영구화 검증 기록 — 2026-09-11

- 현재 baseline `5d999e83edc6c70048bdfbb564ab40dedafa4721`에서 Git 상태·governance·기존 active/completed 구조 및 관련 소스를 읽기 전용으로 확인했다.
- 이전 전체 설계보다 이후 축소 승인이 우선하도록 Phase A와 Deferred를 분리했다. 새 기능/환경변수 구현이나 production 필수 설정 강화를 추가하지 않았다.
- 이번 검증은 문서의 형식·범위·baseline/보존사항·링크·whitespace·Git allowlist 확인에 한정한다. Phase A 테스트/build/server/provider 실행 증거는 없다.
- 필수 section 13개, baseline/보존사항 문자열, 로컬 링크 3개 및 conflict marker 검사는 통과했다. 승인된 Phase A와 본문을 대조했고 구현 항목은 모두 미착수로 남겼다.
- `git diff --check` 및 새 미추적 파일 대상 `git diff --no-index --check -- /dev/null docs/exec-plans/active/dev-test-production-isolation.md`에서 whitespace 오류가 없었다. LF/CRLF 변환 안내만 출력되었다.
- Tracked/staged diff는 없고 전체 status의 변경은 이 plan 한 파일의 `??`뿐이다. Index 등록 규칙이 없어 index는 수정하지 않았다. 실제 secret 값을 읽거나 문서에 기록하지 않았다.

### Safety / Isolation

- DB 테스트 전에 계정·권한·매매·복기·로그 다섯 DB와 모든 관련 cache를 임시 디렉터리로 지정한다. 실제 운영/기존 개발 DB를 fixture로 읽거나 복사하지 않는다.
- Process 환경과 환경파일을 격리하고 테스트 후 원복한다. Import 및 연결 시 임시 root 밖 접근을 차단하며 synthetic 데이터만 사용한다.
- 외부 네트워크는 기본 차단하고 mock을 사용한다. Production 모드 테스트도 실제 production에 연결하는 것이 아니라 합성 설정/임시 데이터에서 정책만 검사한다.
- Python `-B`는 bytecode만 막는다. DB 초기화, cache 쓰기, scheduler, 외부 호출까지 막는 장치로 간주하지 않는다.
- 기존 전체 backend suite와 `verify_project.ps1`는 H4 격리가 끝나지 않아 실행하지 않는다. 집중 테스트도 안전성이 확인되지 않으면 순수/static 검사까지만 하고 미검증으로 남긴다.
- 실제 secret, 환경파일 원문, token, 고객 데이터를 로그·문서·테스트 결과에 넣지 않는다. Credential-safe logging의 기존 sanitizer와 원본 OAuth 입력 보존을 함께 지킨다.

### Remaining / Unverified

- Phase A 구현 및 독립 재검증은 최종 승인됐다(위 사용자 제공 결과). Main 통합·push·production 검증은 수행하지 않았으며 별도 검토 대상이다.
- 실제 production 환경값·DB/cache 위치·Render runtime과 운영 logging 상태는 미검증이다. 사용자의 production 반영 설명과 repository 소스 증거를 구분한다.
- 기존 개발 실행의 암묵적 `.env` 의존과 test fixture의 환경 누락은 구현 시 compatibility 확인 대상이다. 기존 데이터 자동 이동이나 테스트 무력화로 해결하지 않는다.
- Cache import 쓰기는 lifespan 이후로 옮겼고 invalid startup 선행 실패를 검증했다. Cache 전체 통합과 H4 전체 격리는 남겨둔다.
- Android/device/provider 동작은 Phase A 집중 테스트로 검증되었다고 주장하지 않는다.

### Out of Scope / Deferred

- **Phase B 이후 H1:** frontend/Vite 환경 분리, Android debug/release profile, API target 검증, QA opt-in wrapper, APK/AAB 및 Gradle artifact gate, Capacitor sync, localStorage/sessionStorage 정책 변경.
- 기존 production OAuth/AdMob QA를 별도 명시적 opt-in으로 보존하자는 이전 결론은 후속 기록으로 유지한다. 이번에 provider QA나 AdMob QA를 실행·수정하지 않는다.
- Android applicationId/scheme 추가 변경, 기존 OAuth/package/product/storage/`ALPHAMATE_*` 식별자 rename, non-production HTTPS API 생성·주소 임의 선정.
- Production DB/schema migration·이동·복사, production cache 재배치 및 운영 확인 없는 DB/cache 새 필수 설정 강제.
- Support_id/structured observability 후속 단계, OAuth H6 protocol remediation, AI H7 idempotency, H5 schema/account deletion, 전체 H4 테스트 격리.
- Broker import, product/UI 기능, dependency 변경, 광범위 architecture refactor, cache 전체 구조 통합.
- Render 접근·설정 변경·배포, external service 요청, Android build/sync, 다른 worktree 수정, stage/commit/push.
- 이번 문서 작업에서는 이 파일 외 애플리케이션·테스트·환경파일·다른 문서를 수정하지 않는다.

### Completion Criteria

**문서 완료:** 승인된 Phase A를 복원하고 현재 baseline/보호사항/미착수 상태/Deferred가 명시되어 있으며 ExecPlan 형식, 링크, whitespace, 단일 파일 변경 범위를 확인한다.

**향후 Phase A 완료:** 중앙 환경 판정·단일 loader·경로 일관성·dev opt-in·인증/ownership·startup 선행 실패에 대한 집중 격리 증거가 있고, logging/OAuth hotfix 및 Render/health 계약이 보존된다. 전체 diff와 독립 review 결과, 실행/미실행 및 compatibility 위험을 기록한다. 사용자/운영 데이터 변경 없이 완료해야 한다. H1이나 device/external 검증 및 H4 전체 해결까지 완료로 표시하지 않는다.

### Rollback / Failure Handling

- 일반적인 직접 edit/patch만 사용한다. 같은 material approach가 두 번 실패하면 추가 우회 쓰기를 하지 않고 시도·오류·증거·원인·현재 변경 상태와 다른 다음 접근을 보고한다.
- 문서 작성 실패의 복구 범위는 이 새 plan 파일뿐이다. 향후 코드 rollback도 해당 작업이 만든 hunk만 검토해 처리하며 unrelated 변경이나 다른 worktree에 영향을 주지 않는다. 이 문서는 자동 restore/reset/delete 승인이 아니다.
- Schema/data migration을 포함하지 않으므로 DB 삭제·복원·복사로 코드 실패를 복구하지 않는다. 잘못된 설정은 시작을 중단하고 명시적 설정을 교정한다. 개발 fallback을 다시 열어 통과시키지 않는다.
- 이전 코드로 rollback하면 H2/H3 위험이 돌아올 수 있으므로 unsafe 개발 경로를 재개하지 않는다. Production 설정/배포/rollback은 별도 승인 범위다.

### Next Step

승인된 Phase A 변경을 지정된 메시지로 commit한 뒤 결과를 보고하고 대기한다. Main 통합·push·deploy는 수행하지 않는다. Plan은 active로 유지하며 Deferred 범위를 확대하거나 완료 처리하지 않는다.
