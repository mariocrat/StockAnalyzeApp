# Mobile banner ads

- 무료 사용자에게만 Android native 하단 배너 광고를 표시하도록 `showAppBanner()`와 `removeAppBanner()`를 추가했다.
- Pro 구독자는 전역 광고 정책에서 배너, 복귀 전면, 자세히 보기 전면 광고가 모두 차단된다.
- 웹 실행 또는 AdMob SDK 미사용 환경에서는 배너 광고를 건너뛰고 화면 여백도 예약하지 않는다.
- 모바일 앱에서 배너가 표시될 때는 하단 64px 여백을 예약해 차트와 버튼이 광고에 가려지지 않도록 했다.
- 운영 배포 검사에 `VITE_ADMOB_BANNER_AD_UNIT_ID`를 추가해 Google 테스트 배너 단위나 placeholder가 남아 있으면 release check가 실패하게 했다.
