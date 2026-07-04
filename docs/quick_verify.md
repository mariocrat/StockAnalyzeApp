# AlphaMate 빠른 검증

커밋하거나 다른 PC/대화에서 이어가기 전에 프로젝트 루트에서 아래 파일을 실행합니다.

```cmd
verify_project.bat
```

프로젝트 폴더에서 `verify_project.bat`를 더블클릭해도 됩니다. 이 파일은 올바른 프로젝트 경로로 PowerShell 검증 스크립트를 실행하므로 긴 명령어를 외울 필요가 없습니다.

검증 항목:

- 백엔드 테스트
- 백엔드 컴파일 확인
- Git 추적 파일 비밀값 검사
- 프론트 출시 설정 테스트
- 프론트 Android 브랜딩 테스트
- 프론트 모바일 결제 테스트
- 프론트 모바일 AdMob 테스트
- 프론트 사용자 오류 로그 테스트
- 프론트 API 오류 요청 ID 테스트
- 프론트 AI 복기 중복 요청 방지 테스트
- 프론트 린트
- 프론트 운영 빌드

Android 래퍼와 디버그 APK 빌드까지 확인하려면 프로젝트 루트에서 아래 파일을 실행합니다.

```cmd
verify_android_debug.bat
```

이 검증은 `npm run mobile:build`를 실행해 Capacitor 파일을 Android 프로젝트에 동기화하고 `frontend/android/app/build/outputs/apk/debug/app-debug.apk`를 빌드합니다.

이 검증은 로컬 개발 품질 확인용입니다. 실제 서버 비밀값이 필요한 운영 출시 환경 검사는 `docs/manual_test_guide.md`의 백엔드/프론트 출시 검증 절차를 따릅니다.
