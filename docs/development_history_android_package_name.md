# Android 패키지명 applicationId 주입

- Android 빌드의 `applicationId`가 하드코딩된 값 대신 `VITE_GOOGLE_PLAY_PACKAGE_NAME` 환경값을 사용하도록 바꿨다.
- `package_name`, `custom_url_scheme` Android 문자열도 Gradle `resValue`로 같은 패키지명을 주입하게 해 Google Play 결제 요청 패키지명과 실제 앱 패키지명이 갈라지지 않게 했다.
- 네이티브 Java/Kotlin 소스 namespace는 기존 `com.mariocrat.stockanalyze`를 유지해 소스 경로 변경 없이 배포 앱 식별자만 바꿀 수 있게 했다.
- `frontend/scripts/android-branding.test.js`에 패키지명 주입 회귀 테스트를 추가했다.
