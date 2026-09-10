# Credential-safe access logging hotfix

### Goal

StockBoda가 제어하는 Uvicorn access log와 application/event log에 OAuth callback query 및 재사용 가능한 credential 원문이 남지 않게 한다. OAuth callback과 query 기반 검증 입력은 변경하지 않는다.

### Scope

- Worktree: `D:\Project\Vibe\StockBoda.worktrees\safe-logging`
- Branch: `hotfix/credential-safe-access-logging`
- Base HEAD: `7614831e6634e84ac0542721aec03c634a2a2e8e`
- Uvicorn 시작 경로의 raw access log 비활성화와 query 없는 HTTP summary
- backend event log의 명시적 credential key 및 자유 형식 query credential 방어
- synthetic 값만 사용하는 격리된 회귀 테스트
- 기존의 다른 worktree와 production/external 설정은 변경하지 않는다.

### Decisions

- ASGI request, query string, headers 및 endpoint 입력은 수정하지 않는다.
- HTTP summary에는 method, route template, status code, duration만 기록한다. route template을 확인할 수 없으면 raw path 대신 고정 fallback을 쓴다.
- credential key는 명시적인 deny set으로 판정해 `input_tokens`, `output_tokens`, `error_code` 같은 운영 필드를 보존한다.
- 자유 형식 문자열에서는 명시적인 credential assignment/query 값만 마스킹한다. 전체 structured logging 체계는 만들지 않는다.
- Uvicorn application error log의 formatted message/traceback은 같은 credential policy로 정리하되 원본 exception과 propagation은 유지한다.
- credential assignment 탐색은 regex suffix 재검색 대신 단방향 scanner를 사용한다. event/client log의 기존 출력 한도는 로그용 사본을 sanitizer에 넘기기 전에 적용하고, bounded prefix도 반드시 redaction한 뒤 저장한다.
- bounded prefix 안에서 quoted credential의 closing quote를 확인할 수 없으면 newline이 아니라 bounded log copy의 끝까지 credential value로 처리한다. header line boundary는 suffix `find`가 아니라 현재 index부터 CR/LF까지 직접 전진한다.
- credential query 뒤의 정상 query field까지 보수적으로 제거하는 N2는 credential 보호 우선 동작으로 유지하며 이번 hotfix에서 parser를 재설계하지 않는다.

### Current Status

- [x] 시작 root/branch/HEAD/status/worktree 및 governance 확인
- [x] Uvicorn 시작 경로와 event/application logging 경로 확인
- [x] 구현
- [x] synthetic unit/static 검증
- [x] 최종 diff/status 검토
- [ ] 독립 review (별도 승인 단계)

2026-09-10 독립 review 보완:

- [x] B1: 실제 credential alias 누락 재현 및 policy 보강
- [x] B2: percent-encoded key와 quoted/escaped string 우회 재현 및 보강
- [x] M1: chained exception formatted traceback 노출 재현 및 Uvicorn error filter 추가
- [x] m1: `status-code`/`error-code` 오탐 재현 및 full-key 판정으로 수정
- [x] m3: summary logging sink 실패 전파 재현 및 국소 격리
- [x] m4: governance/plan/`.env.example` 실행 예시 동기화
- [x] m2: 일부 429/CORS summary 누락은 credential blocker가 아님을 확인하고 deferred 기록

2026-09-10 N1 성능 보완:

- [x] 긴 `-` 비매칭 입력의 1k→2k→4k→8k 약 4배 scaling 재현
- [x] backend/frontend assignment 탐색을 단방향 scanner로 교체
- [x] event/client log의 문자열 한도를 sanitization 전에 로그용 사본에 적용
- [x] 1k/2k/4k/16k `-`, `.`, 혼합 key-like 입력 성능 회귀 추가
- [x] 4k User-Agent event 저장 및 truncation 경계 credential 회귀 추가
- [x] N2를 의도적으로 수정하지 않고 deferred로 기록

2026-09-10 B3 및 multiline N1 residual 보완:

- [x] closing quote가 log limit 밖에 있는 multiline quoted credential의 다음 줄 노출을 backend/frontend에서 재현
- [x] Uvicorn error filter의 반복 LF header 128k→256k→512k 비정상 scaling 재현
- [x] unmatched plain/escaped quoted credential을 bounded copy 끝까지 fail-closed 처리
- [x] line boundary를 현재 index부터 CR/LF까지 한 방향으로 전진하도록 변경
- [x] key/encoded key/assignment/quote/value/escape/CR/LF/duplicate-query truncation 경계 회귀 추가
- [x] LF/CRLF/CR/header/quoted/escaped 128k·256k·512k error-filter 성능 회귀 추가
- [x] N2 deferred 유지

### Verification

- Uvicorn 시작 경로가 기본 raw access log를 비활성화하는지 정적 검사한다.
- 순수 ASGI 테스트에서 callback 및 AdMob SSV query가 endpoint에 그대로 전달되지만 HTTP summary에는 들어가지 않는지 확인한다.
- 임시 event-log DB에서 credential field 및 URL/query sentinel이 저장되지 않는지 확인한다.
- 같은 DB 테스트에서 token usage metric과 `error_code`가 보존되는지 확인한다.
- 관련 격리 가능 unit tests와 `git diff --check`를 실행한다. 전체 backend suite는 H4 격리 문제로 실행하지 않는다.

2026-09-09, base HEAD와 working diff 기준:

- `tests.test_credential_safe_logging` 및 `tests.test_render_blueprint`: 11개 통과. 순수 ASGI query 보존, safe summary, 세 Uvicorn 시작 경로를 검사했다.
- `tests.test_event_log`: 25개 통과. 임시 DB를 사용했다. 사용 가능한 bundled Python에 FastAPI가 없어 `HTTPException` 호환 최소 stub으로 event-log 모듈만 격리 실행했다.
- `frontend/scripts/client-event-log.test.js`: 7개 통과.
- documentation/security source tests: 16개 통과. 변경 Python 6개 파일 AST parse 통과. `git diff --check` whitespace 오류 없음(LF/CRLF 변환 경고만 있음).
- tracked-secret 검사는 기존 M2 설정 설명 문서 한 곳을 계속 보고했다. 해당 파일은 이번 작업에서 변경하지 않았고 새 finding은 확인되지 않았다.
- 실제 FastAPI HTTP server, external provider, device, production은 실행하지 않았다.

2026-09-10 보완 diff 기준:

- 보완 전 synthetic 재현에서 B1/B2/M1/m1/m3가 모두 확인됐다.
- `tests.test_credential_safe_logging` 및 `tests.test_render_blueprint`: 14개 통과. request/query/header/body 보존, failing logger/handler 격리, 원본 endpoint 예외 보존, chained traceback 출력, Uvicorn 시작 예시를 검사했다.
- `tests.test_event_log`: 25개 통과. 임시 DB와 `HTTPException` 호환 최소 stub을 사용했다.
- `frontend/scripts/client-event-log.test.js`: 7개 통과. backend와 같은 alias/encoded/escaped/정상 필드 벡터를 검사했다.
- 변경 Python 7개 파일 AST parse 통과.
- 설치된 FastAPI/Starlette/Uvicorn runtime이 없어 실제 server stderr 통합 검증은 수행하지 못했다. 표준 logging handler의 최종 formatted traceback 경계는 unit test로 검증했다.

2026-09-10 N1 보완 diff 기준:

- 수정 전 backend `"-" * n`: 1k 0.069944초, 2k 0.288739초, 4k 1.166514초, 8k 4.727977초. 인접 길이 증가마다 4.04~4.13배였다.
- 수정 전 frontend `"-".repeat(n)`: 1k 0.005572초, 2k 0.022972초, 4k 0.086619초, 8k 0.366983초. 인접 배율은 3.77~4.24배였다.
- 수정 후 backend: 1k 0.000577초, 2k 0.001014초, 4k 0.002439초, 8k 0.004629초, 16k 0.007686초. 인접 배율은 1.66~2.41배였다.
- 수정 후 frontend message+detail: 1k~16k 모두 0.0011초 이하였고, 출력 한도 이전의 로그용 prefix만 scan했다.
- 4k User-Agent를 포함한 실제 event DB 기록 sanity 측정은 0.021606초였다.
- `tests.test_credential_safe_logging` 및 `tests.test_render_blueprint`: 15개 통과. adversarial scaling/upper bound와 기존 request/error 회귀를 포함한다.
- `tests.test_event_log`: 26개 통과. 4k User-Agent, pre-sanitize bound, truncation 경계의 escaped credential을 포함한다.
- `frontend/scripts/client-event-log.test.js`: 9개 통과. 장문 message/details, scaling upper bound와 truncation 경계 credential을 포함한다.

2026-09-10 B3 및 multiline N1 residual 보완 diff 기준:

- 수정 전 B3 fixture는 bounded prefix의 첫 줄 credential만 제거하고 다음 줄 `SYNTHETIC_LINE_TWO`를 backend/frontend log copy에 남겼다.
- 수정 후 같은 fixture는 양쪽 모두 first/second line 원문을 남기지 않고 `[redacted]`와 `[truncated]`만 남겼다.
- 수정 전 Uvicorn error filter LF header: 128k 0.062252초, 256k 0.171670초, 512k 0.583997초. 인접 배율은 2.76배, 3.40배였다.
- 수정 후 같은 LF header: 128k 0.071262초, 256k 0.144670초, 512k 0.272556초. 128k→512k 배율은 3.82배였다.
- 수정 후 128k→512k 배율: CRLF 4.23배, CR 3.61배, closed quoted multiline 5.08배, escaped multiline 0.74배였다. 입력 크기 4배에 대해 quadratic 증가를 보이지 않았다.
- `tests.test_credential_safe_logging` 및 `tests.test_render_blueprint`: 18개 통과. B3, truncation boundary matrix와 Uvicorn multiline filter 성능 회귀를 포함한다.
- `tests.test_event_log`: 26개 통과. closing quote가 1,000자 limit 밖에 있는 multiline credential의 임시 SQLite 저장 회귀를 포함한다.
- `frontend/scripts/client-event-log.test.js`: 11개 통과. 같은 B3 및 truncation boundary 의미와 bounded multiline client-event를 포함한다.

### Remaining / Unverified

- Render/proxy/platform이 별도로 생성하는 request log의 query 처리와 retention
- production 배포 및 실제 OAuth/provider/device 동작
- 전체 repository의 자유 형식 출력과 장기 observability 체계
- 현재 middleware 순서상 safe HTTP summary에 포함되지 않는 일부 public-market 429와 CORS preflight
- N2: credential query 뒤의 정상 진단 query field도 보수적으로 함께 제거되는 동작

### Next Step

최종 diff/status와 문서 검증을 마친 뒤 working diff를 별도의 독립 review에 넘긴다.

### Out of Scope

Support ID, request/correlation ID 재설계, DB schema migration, account/support UI, 환경 격리 전면 구현, OAuth H6 및 AI H7 remediation, CI/monitoring vendor, Android build/sync, production deploy/restart/log 조회, 외부 console 변경, 대규모 refactor.

### Rollback

이번 worktree의 미커밋 plan/code/test/config diff만 파일별로 되돌리는 것이 rollback 경계다. DB/data migration과 외부 설정 변경은 없으며 다른 worktree를 건드리지 않는다.
