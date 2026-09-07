# StockBoda Testing

담당: 안전한 검증 환경, 명령의 부작용, 완료 증거.
근거: [verify_project.ps1](../scripts/verify_project.ps1), [frontend scripts](../frontend/package.json), [테스트 예시](../tests/test_me_data_routes.py).

## 먼저 실행 안전성을 확인한다

**현재 backend 전체 테스트와 Android debug wrapper는 격리된 기본 검증 경로가 아니다.**

일부 테스트는 사용하는 DB 전체를 임시 경로로 설정하지 않고 os.environ을 원복하지 않는다(H4). 공통 env loader와 매매 DB loader도 다르다(H3). 일반 cache의 `ALPHAMATE_CACHE_DIR`과 별개로 `journal_chart.py`는 `backend/.cache/yfinance`를 사용하며 module import 중 해당 디렉터리 생성과 yfinance cache 설정이라는 filesystem side effect가 발생할 수 있다. 따라서 `ALPHAMATE_ENV_FILE`이나 단일 cache 환경변수 하나를 설정하는 것으로 전체가 안전하게 격리되었다고 판단하지 않는다.

DB 기반 검증을 허용하기 전에 모든 연결 경로를 추적하고 아래 조건을 확보한다.

- 계정·권한·매매·복기·로그 DB 다섯 경로와 cache를 폐기 가능한 테스트 디렉터리로 지정하고 최종 해석 결과를 검사한다.
- process 환경과 root/backend 환경파일 fallback에서 운영 자격증명·데이터 경로가 들어오지 않게 한다. 비밀값은 출력하지 않는다.
- 테스트가 설정을 덮어쓰는 경우까지 검사하고 fixture 종료 시 원복한다. 테스트 순서나 다른 테스트 실행 여부에 의존하지 않게 한다.
- 외부 네트워크는 기본 차단하고 mock을 사용한다. 실제 서비스 검증은 대상·계정·상태 변경·비용을 확인한 별도 작업으로 분리한다.
- 애플리케이션 module import, lifespan, DB 조회 함수도 초기화·scheduler·schema 변경을 일으킬 수 있다.

이는 필요한 후속 구현 조건이며 현재 공통 fixture나 자동 네트워크 차단이 구현되어 있다는 뜻이 아니다. 조건을 확보하지 못하면 순수 함수·소스 검사로 제한하고 DB 기반 결과는 미검증으로 보고한다.

## Governance 문서 검증의 한계

기존 documentation tests는 새 governance 정본을 자동으로 검증하지 않으며, 일부는 기존 reference/historical 문구를 고정한다. Governance 변경은 링크·경로, 필수 section, 문서 간 상호참조와 별도 문서 검증으로 확인한다. 기존 문서 테스트가 통과해도 새 governance coverage가 보장되는 것은 아니다.

## 명령과 부작용

명령은 확인한 repository root 또는 명시한 frontend 디렉터리에서 실행한다. PowerShell의 npm.ps1 제한이 있으면 npm.cmd를 사용한다. 도구가 없을 때 임의 설치하지 말고 설치의 범위·권한을 확인한다.

| 명령 | 효과 / 사용 조건 |
| --- | --- |
| git --no-optional-locks status --short, git diff --check | Git 상태·공백 검사; 기존 diff도 포함됨 |
| .\.venv\Scripts\python.exe -B -m unittest tests.test_cors_config tests.test_rate_limit | 확인 시점의 순수 환경/메모리 테스트; 변경 전 테스트 본문 재확인 |
| .\.venv\Scripts\python.exe -B -m unittest tests.test_policy_documentation tests.test_quick_verify_docs tests.test_secret_scan_output | 문서·검증기 소스 계약 검사; 문서 작업에 사용 |
| .\.venv\Scripts\python.exe -B scripts\check_no_tracked_secrets.py | 추적 파일만 검사. 미추적 신규 문서와 전체 Git history는 별도 확인 |
| frontend에서 node --test scripts/<선택한 파일>.test.js | 파일별 부작용 확인. validate-release-env / validate-mobile-bundle 테스트는 임시 파일 생성 |
| frontend에서 npm.cmd run lint | lint; --fix 없이 실행 |
| .\.venv\Scripts\python.exe -m unittest discover -s tests | DB·임시 파일·환경 변경 가능. H3/H4 격리 조건 확보 전 일상 실행 금지 |
| verify_project.bat | 전체 테스트, bytecode, secret scan, frontend 검사·dist 생성. 문서 변경만을 위해 실행하지 않음 |
| frontend에서 npm.cmd run build | dist 생성; Android 출시 설정 검사나 .env.release 로딩을 뜻하지 않음 |
| Android 검증 wrapper | dist 생성, Capacitor sync, Gradle 및 APK/AAB 생성. 추적 Gradle 변경과 API 환경 확인 필요 |

명령 표의 .venv는 해당 worktree에 별도로 준비되어 있다는 전제다. 새 worktree에는 ignored runtime·의존성·private env·아티팩트가 자동으로 복사되지 않는다. 필요한 실행기를 확인하고 승인 없이 main의 설정·DB·도구 디렉터리를 복사하지 않는다. 기존 .venv/Node/JDK/SDK의 존재는 clean install이나 build 성공의 증거가 아니다. -B는 Python bytecode만 막으며 DB·네트워크 쓰기를 막지 않는다.

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
