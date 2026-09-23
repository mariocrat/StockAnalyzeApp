# StockBoda Testing

담당: 안전한 검증 환경, 명령의 부작용, 완료 증거.
근거: [wrapper](../scripts/verify_project.ps1), [coordinator](../tests/run_isolated_tests.py), [manifest](../tests/test_inventory.json).

## 공식 H4 TestOnly

Mode는 반드시 명시합니다. 생략 또는 잘못된 값은 test/build 시작 전에 실패합니다.
Python 3.11+와 Node 24+의 승인된 기존 실행기를 **절대경로**로 지정합니다.
PATH fallback이나 worktree .venv 자동 선택은 없습니다. 실행기 부재·상대경로·버전/기능 비호환은 사전 실패합니다.
실행기 및 필요한 Python 의존성 준비는 별도 승인 작업이며 wrapper는 설치하지 않습니다.

```powershell
& "<worktree>\scripts\verify_project.ps1" `
  -Mode TestOnly `
  -PythonPath "<approved absolute python.exe>" `
  -NodePath "<approved absolute node.exe>"
```

위 placeholder는 실제 승인된 경로로 대체합니다. 특정 PC 경로는 계약이 아닙니다.
BAT도 동일한 인자를 그대로 전달합니다. 호출 CWD에 의존하지 않으며 PowerShell exit code를 보존합니다.
Mode 없는 더블클릭 실행은 실패합니다.

```powershell
.\verify_project.bat -Mode TestOnly -PythonPath "<approved absolute python.exe>" -NodePath "<approved absolute node.exe>"
```

TestOnly 호출 구조:
1. 두 실행기의 격리된 compatibility probe.
2. 지정 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py --all`.
3. 같은 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py --node-all --node-executable <approved absolute node.exe>`.
Python coordinator와 module child는 모두 `-I -X utf8`로 실행되어 UTF-8 stdout/stderr를 사용합니다.

Python direct **464** = 기존 H4 **35 / 393 / 22** (A1/foundation/helper / migrated / OUT) + Stage 1 **14** 별도 cohort.
Child probe **18**은 direct와 별도 집계합니다.
Node **17 entrypoint / 128 direct testcase**, `test:mobile-bundle` 포함.
Manifest/source/execution 누락·중복·extra 및 예상 밖 skip은 실패입니다. Nested evidence는 direct에 중복 합산하지 않습니다.

Raw `unittest discover`는 공식 경로가 아닙니다. Target import 전에 필요한 A1 boundary를 설치하는 승인 coordinator를 사용합니다.
`tests/run_phase_a_tests.py`는 deprecated이며 target import 전 **exit 2**로 종료합니다.
`tests/diagnose_phase_a_probe.py`는 공식 inventory/실행 대상이 아닙니다.

TestOnly 중 실제 private env/credential/HOME/keystore 접근, external provider/network/DNS,
npm install/package download, production build, Gradle/keytool, deploy/signing은 금지됩니다.
Child env는 정제하고 HOME/TEMP는 test-owned 경로를 사용합니다. Repo/persistent write는 허용하지 않습니다.
Test infrastructure의 명시적 Python/Node child와 승인된 synthetic socketpair 계약은 유지합니다.
Billing fixture는 integrity 검증된 13.17.2 배포물의 고정 source snapshot이며 runtime download는 없습니다.
이는 실제 설치된 plugin이나 Android 산출물 검증을 대신하지 않습니다.

## BuildChecks는 별도 경로

```powershell
& "<worktree>\scripts\verify_project.ps1" -Mode BuildChecks -PythonPath "<approved absolute python.exe>" -NodePath "<approved absolute node.exe>"
```

BuildChecks에만 기존 네 검사를 둡니다:

- Backend compile check: `python -m compileall backend` (bytecode 쓰기).
- Tracked secret scan: `scripts/check_no_tracked_secrets.py` (추적 파일 검사).
- Frontend lint: 승인 Node 옆의 `npm.cmd run lint`.
- Frontend production build: 같은 `npm.cmd run build` (dist 생성).

기존 VITE_APP_NAME 미설정 시 StockBoda 기본값은 유지하고 CWD/env를 종료 시 복구합니다.
기존 테스트 단계는 TestOnly로 이동했으며 BuildChecks 통과는 테스트 통과가 아닙니다.
BuildChecks는 H4 격리 경계가 아니고 host env 및 기존 dependency tree를 사용할 수 있습니다.
npm lifecycle/build 설정의 부작용을 먼저 검토해야 하며 필요한 의존성 부재 시 임의 설치하지 않습니다.
이 wrapper는 release/deploy/signing 승인이나 Android build 경로가 아닙니다.
기존 일반 Vite build를 release 전용 workflow로 확장하지 않았습니다.

## 검증 상태와 범위

**H4 test environment isolation closeout complete.** 공식 전체 TestOnly는 exit code **0**, 전체 PASS로 최종 승인됐고 closeout 문서화와 최종 확인도 완료됐습니다.

- Python direct **464 PASS** (FAIL/ERROR/SKIP 0); missing/duplicate/extra/unexpected skip 모두 0.
- H4 classification은 A1/foundation/helper **35**, migrated A2+B1+B2+C+D **393**, OUT **22**이며, Stage 1 신규 cohort **14**를 별도로 더해 464입니다.
- Child probe **18/18 계약 PASS**. Expected negative raw ledger **6 (4+1+1)**, probe contract mismatch **0**, suite-level unexpected **0**.
- Node entrypoint **17/17 PASS**, direct testcase **128 PASS** (FAIL/SKIP 0); missing/duplicate/extra/unexpected skip 모두 0.
- `restored`, `patches_restored`, `cleanup` 모두 true; Node temp cleanup 성공, test-owned temp 잔여와 repo pollution은 0입니다.

Stage 1/2 및 Foundation isolation 의미는 유지됐습니다. BuildChecks는 이번 H4 TestOnly에 포함되지 않았으며, 별도 실행·승인을 의미하지 않습니다.
Android debug/release wrapper와 임의 raw module 실행에 H4 TestOnly 보장이 자동 적용되지 않습니다. -B는 bytecode만 막으며 DB/network 격리를 대신하지 않습니다.

축소 문서 검증은 승인 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py tests.test_quick_verify_docs`를 사용합니다. Wrapper synthetic 검증은 `tests/verify_project_wrapper_regression.ps1`에 명시적 PythonPath/NodePath를 전달하며, 실제 coordinator 대신 synthetic dispatch를 검사합니다.

## 변경별 검증 수준

| 변경 | 최소 확인 |
| --- | --- |
| 문서/AGENTS | 관련 문서 테스트, 링크·경로·명령 존재, 신규 파일 포함 secret 검사, diff/status |
| 환경/포트/CORS | 설정 누락·충돌·fallback, 최종 API/DB 선택, 실제 교차 출처 HTTP와 응답 헤더 |
| API/인증 | 소유권·익명·잘못된 세션·권한 거절, 실제 HTTP 입력/오류 응답 |
| 데이터/schema/삭제 | 이전 schema→현재, 다른 사용자 보존, 단계별 실패·재시도, 복원 |
| AI/권한/결제 | 중복·거절 후 재시도·차감/환급·서버 재시작, 외부 응답 mock과 별도 실서비스 검증 |
| Android UI/로그인/광고 | 정책 테스트와 최종 패키지 확인, 기기 화면·수명주기·외부 연동 |
| Release | RELEASE.md의 아티팩트·버전·서명·환경·배포 revision 증거 |

현재 Node 테스트에는 소스 문자열 검사도 있다. 문자열 존재는 React 렌더링·이벤트 순서·native plugin 작동 증거가 아니다. Java 기본 테스트도 package/샘플 확인 수준이다.

실제 HTTP client 기반 통합 테스트는 감사에서 발견하지 못했다. M6의 X-Request-ID/Retry-After CORS 노출처럼 직접 함수 호출이 놓치는 동작을 별도로 검증해야 한다.

## 반드시 분리해서 남길 미검증 영역

- OAuth: 취소, state/만료/중복 티켓, 앱 종료 후 복귀, cold start, 다른 URI scheme, 공급자 실제 설정.
- 결제: 보류·취소·중복 콜백, 구매 중 종료, 네트워크 단절, 계정 전환, consume/acknowledge 재시도, RTDN·환불.
- 광고: 각 광고 형식, Pro 숨김, keyboard/전체화면/뒤로가기, SSV 지연·중복, 테스트 ID와 실제 지급 차이.
- 데이터: 저장 on/off, 계정 전환, 삭제 중 실패/동시 요청, export 한도, 기기 파일 저장·backup.
- 운영: disk full/locked, 이전 schema, 복원, API timeout, process restart, proxy rate limit.

결과에는 명령, 실행 위치, 기준 revision, 통과/실패/미실행, 검증 수준, 남은 제약을 남긴다. 최신 device/external 증거가 없으면 완료를 주장하지 않는다. 과거 감사 결과와 현재 작업에서 새로 실행한 검증을 구분한다. 검증 기록은 사용자에게 승인받은 범위의 계획이나 최종 보고에 남긴다.
