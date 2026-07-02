# Android 검증 스크립트 안내 보강

- `verify_android_debug.bat`, `verify_android_release.bat`가 사용하는 PowerShell 스크립트에 `Test-RequiredPath` 안내 함수를 추가했다.
- 로컬 JDK 또는 Android SDK 폴더가 없을 때 `docs\manual_test_guide.md`를 보라는 메시지를 함께 출력한다.
- 비개발자가 더블클릭으로 검증하다가 Java/SDK 환경 문제를 만나도 어느 문서를 확인해야 하는지 바로 알 수 있게 했다.
- `tests/test_android_release_verification.py`에 debug/release 검증 스크립트 안내 문구 회귀 테스트를 추가했다.
