# AlphaMate 빠른 검증

커밋하거나 다른 PC/대화에서 이어가기 전에 프로젝트 루트에서 아래 파일을 실행합니다.

```powershell
.\verify_project.bat
```

프로젝트 폴더에서 `verify_project.bat`를 더블클릭해도 됩니다. 이 파일은 올바른 프로젝트 경로로 PowerShell 검증 스크립트를 실행하므로 긴 명령어를 외울 필요가 없습니다.
명령 프롬프트에서는 `verify_project.bat`처럼 입력해도 되고, PowerShell에서는 앞에 `.\`를 붙여야 합니다.

검증 항목:

- 백엔드 테스트
- 백엔드 컴파일 확인
- Git 추적 파일 비밀값 검사
- 프론트 출시 설정 테스트
- 프론트 Android 브랜딩 테스트
- 프론트 Android Billing Library 버전 테스트
- 프론트 모바일 결제 테스트
- 프론트 모바일 AdMob 테스트
- 프론트 사용자 오류 로그 테스트
- 프론트 API 오류 요청 ID 테스트
- 프론트 OAuth 앱 복귀 테스트
- 프론트 앱 뒤로가기 테스트
- 프론트 AI 복기 중복 요청 방지 테스트
- 프론트 스플래시 로딩 정책 테스트
- 프론트 차트 레이아웃 테스트
- 프론트 린트
- 프론트 운영 빌드

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
