# AlphaMate 빠른 검증

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

2026-10-15 source inventory는 manifest와 testcase declaration에서 재계산한다: Python direct **1070** (108 modules) = baseline **35 / 997 / 22** (A1/foundation/helper / migrated / OUT) + Stage 1 **16** 별도 cohort.
2026-09-23 historical baseline은 Python direct **464** = **35 / 393 / 22** + Stage 1 **14**였다.
Child probe **18**은 direct와 별도 집계합니다.
Node **23 entrypoint / 259 direct testcase**, `test:ai-chart-source`, `test:broker-import`, `test:canonical-review-renderer`, `test:mobile-bundle` 포함.
Manifest/source/execution 누락·중복·extra 및 예상 밖 skip은 실패입니다. Nested evidence는 direct에 중복 합산하지 않습니다.

일반 guarded module은 120초, coordinator self-test는 600초의 hard timeout을 유지합니다. 관측된 timeout module에만 별도 제한을 적용합니다: route 38-case mutation 회귀는 H4 계측 158.0초·공식 실행 234.4초에 근거해 360초, cache 14-case 회귀는 공식 실행 77.3초/120초 timeout·H4 계측 80.6초에 근거해 180초입니다. TimeoutExpired는 계속 실패이며 case coverage·환경/patch restoration·소유 root cleanup 판정은 완화하지 않습니다.

과거 closeout 기록 (historical baseline, 2026-09-23, 검증 HEAD `9fff3f3e84ce26f663f41619d37a4eb101bfbc32`): H4 test environment isolation closeout 완료. 공식 TestOnly exit code **0**; Python **464/464 PASS**, child probe **18/18 계약 PASS**, Node **17/17 entrypoint / 128/128 direct PASS**입니다. Expected negative raw ledger 6, probe contract mismatch 0, suite unexpected 0이며 restoration/cleanup 지표는 모두 true, repo pollution은 0입니다.

현재 source inventory는 Python 1070 direct / 18 child probe, Node 23 / 259입니다. Focused H4 evidence와 공식 전체 TestOnly 상태는 아래 TESTING 문서에서 구분해 확인합니다.

2026-10-05 Phase 2D-4: Phase 2C 및 Phase 2D-1/2/3는 사용자 통보로 독립 승인됐다. 새 frontend는 AI execute/history list/detail/account export에만 `X-Review-Display-Contract: review-display.v1`을 선언한다. 각 backend route의 첫 gate는 exact 단일 값만 통과하고 누락/오버전/malformed/중복은 고정 426 update-required로 거절한다. Unsupported는 replay lookup/charge/refund/model/provider/history write 0, cache 존재 시에도 content 0이다. Supported replay 및 whole-record history adapter는 유지하고 old-server snapshotless UI는 legacy summary로 fallback하지 않는다. 최종 focused Python 433/433, Node 69/69, Node coordinator 9/9와 inventory/보존 증거는 [TESTING](TESTING.md#phase-2d-4-client-display-compatibility-gate--2026-10-05) 및 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 독립 Phase 2D-4 검토 가능 상태이며 보고 후 대기한다. 전체 TestOnly/BuildChecks, browser/CSS/device/live network/private DB, DB migration/backfill, 배포/Play 및 Git mutation은 실행하지 않았다. 아래 이전 단계 기록은 historical evidence다.

2026-10-05 Phase 2D-3: Phase 2C/2D-1/2D-2는 독립 승인됐다. Live/history 본문과 chart document는 동일 CanonicalReviewRenderer로 승인 snapshot을 그대로 표시한다. JSON export도 snapshot을 보존한다. Invalid/missing snapshot은 고정 unavailable UI이며 legacy summary fallback은 없다. Focused Python 409/409, Node 62/62, Node coordinator 9/9와 실제 source inventory 증거는 [TESTING](TESTING.md#phase-2d-3-canonical-exact-renderer-production-transition--2026-10-05) 및 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 아래 Phase 2D-2 기록은 historical evidence다. 전체 TestOnly/BuildChecks, browser/CSS/device/live network/private DB는 실행하지 않았고 client version/header gate와 Phase 2D-4는 HOLD다.

2026-10-04 Phase 2D-2: Phase 2C 및 Phase 2D-1/P2는 독립 승인됐다. AI 완료 뒤 chart 재조회 대신 승인 snapshot의 chart surface만 표시하고 history/replay도 같은 source를 사용한다. 일반 pre-AI chart 조회는 유지한다. Focused production backend/frontend, adapter/Phase 2C/2B/coordinator/storage/docs 및 실제 inventory evidence는 [TESTING](TESTING.md#phase-2d-2-live-ai-review-chart-source--2026-10-04)과 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks와 Phase 2D-3 이후는 실행하지 않는다.

2026-10-04 Phase 2D-1 P2: 원본 summary/basic/advanced를 각각 exact schema shape/type으로 검증한 뒤 중복 key를 명시적으로 거절한다. 두 은폐 재현은 canonical body 유/무 모두 list/detail/export에서 fail-closed해야 한다. Focused adapter 39 cases 및 Phase 2C/coordinator/storage/docs, DB/호출 불변성 evidence는 [TESTING](TESTING.md#phase-2d-1-p2-semantic-section-admission--2026-10-04)과 [실행 계획](exec-plans/structured-trade-review.md)을 참조한다. Phase 2D-2는 진행하지 않는다.

2026-10-04 Phase 2D-1: Phase 2C 전체는 사용자 통보에 따라 독립 승인됐다. History list/detail/export는 전체 record 공통 read adapter와 SELECT-only read connection을 사용한다. 지원 legacy만 memory copy로 adapt하고 unsafe/unknown/corrupt는 고정 표시 불가로 반환하며 trade 복원을 차단한다. Focused 대상과 실제 결과는 [TESTING](TESTING.md#phase-2d-1-whole-record-history-read-adapter--2026-10-04)과 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks와 Phase 2D-2 이후 작업은 실행하지 않는다.

2026-10-04 Phase 2C 독립 검토 P2 수정: advanced prompt의 예약 MA 약어 출력 지시를 일봉의 5일/10일/20일 이동평균 및 분봉의 실제 봉 개수 표현으로 바꿉니다. A1 예약 규칙은 유지하고 자연어 정상 semantic과 MA20 반례를 production route로 검증합니다. Focused 결과는 [TESTING](TESTING.md#phase-2c-p2-promptadmission-consistency--2026-10-04)과 [실행 계획](exec-plans/structured-trade-review.md)에 기록합니다. Phase 2D HOLD입니다.

2026-10-04 Phase 2C-A3는 승인된 A1/A2 sealed body와 compatibility wire를 route/refund/replay/history/cache에 연결합니다. Strong 결과의 summary/canonical_text byte equality 가정을 제거하고, route metadata는 승인된 body/wire를 변경하지 않습니다. Opt-in 성공 history는 동일한 승인으로 저장/복원하고 error는 환급 1회·history 승인/저장 0을 유지합니다. Replay는 추가 model/charge/refund/history 생성 없이 승인된 content를 재사용합니다. 지정된 focused 증거는 [TESTING](TESTING.md#phase-2c-a3-routerefundreplayhistorycache--2026-10-04) 및 [실행 계획](exec-plans/structured-trade-review.md)을 참조하세요. Frontend production 변경은 없고 전체 TestOnly/BuildChecks는 실행하지 않습니다. 전체 Phase 2C 독립 검토는 대기하며 Phase 2D는 HOLD입니다.

2026-10-03 Phase 2C focused run: Python 298/298 across 20 explicit modules; React renderer 9/9, legacy parser 7/7, Node coordinator 9/9. The user-confirmed advanced fallback contract uses double-newline top-level boundaries; fixed section content and actual unchanged parser checks verify four paragraphs. Basic fallback and normal paths stay unchanged. Independent review is pending; Phase 2D is not performed. This is not a full TestOnly or BuildChecks run; see [TESTING](TESTING.md#phase-2c-focused-h4-evidence--2026-10-03).

2026-10-03 Phase 2B-3 focused run: Python 276/276 across 20 explicit modules, Node coordinator 9/9, canonical renderer 9/9. Guarded Python reports had unexpected violations 0 and restoration/patch restoration/cleanup true. This is not a full TestOnly or BuildChecks run; see [TESTING](TESTING.md#phase-2b-3-focused-h4-evidence--2026-10-03) for scope and limits.

raw `unittest discover`는 공식 경로가 아닙니다. Target import 전에 필요한 A1 boundary를 설치하는 승인 coordinator를 사용합니다.
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

PowerShell에서는 앞에 `.\`를 붙여야 합니다.

## 별도 Android 검증 (H4 TestOnly 아님)

Android 래퍼와 디버그 APK 빌드까지 확인하려면 프로젝트 루트에서 아래 파일을 실행합니다.

```powershell
.\verify_android_debug.bat
```

이 검증은 `npm run mobile:build`를 실행해 Capacitor 파일을 Android 프로젝트에 동기화하고 `frontend/android/app/build/outputs/apk/debug/app-debug.apk`를 빌드합니다.

Codex나 자동화에서 배치 파일의 `Press any key` 대기를 건너뛰려면 실행 전에 아래 값을 켭니다.

```powershell
$env:ALPHAMATE_NO_PAUSE='1'
.\verify_android_debug.bat
Remove-Item Env:\ALPHAMATE_NO_PAUSE
```

같은 값은 `release_readiness_report.bat`, `verify_android_release.bat`에도 사용할 수 있습니다. 더블클릭으로 직접 실행할 때는 설정하지 않아도 됩니다.

이 검증은 로컬 개발 품질 확인용입니다. 실제 서버 비밀값이 필요한 운영 출시 환경 검사는 `docs/manual_test_guide.md`의 백엔드/프론트 출시 검증 절차를 따릅니다.
