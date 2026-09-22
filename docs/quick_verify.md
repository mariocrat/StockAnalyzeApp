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
2. 지정 Python으로 `-I -B tests/run_isolated_tests.py --all`.
3. 같은 Python으로 `-I -B tests/run_isolated_tests.py --node-all --node-executable <approved absolute node.exe>`.

Python direct **464** = 기존 H4 **35 / 393 / 22** (A1/foundation/helper / migrated / OUT) + Stage 1 **14** 별도 cohort.
Child probe **18**은 direct와 별도 집계합니다.
Node **17 entrypoint / 128 direct testcase**, `test:mobile-bundle` 포함.
Manifest/source/execution 누락·중복·extra 및 예상 밖 skip은 실패입니다. Nested evidence는 direct에 중복 합산하지 않습니다.

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
