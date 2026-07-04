# 비공개 출시 설정 일치 보고서

- `prepare_private_release_setup.bat` 마지막 보고서에 서버/앱 출시 설정 일치 검사를 추가했다.
- 이제 원클릭 준비 흐름에서 `GOOGLE_PLAY_PACKAGE_NAME`과 `VITE_GOOGLE_PLAY_PACKAGE_NAME`, 카카오/네이버 Redirect URI, 보상형 AdMob 광고 단위 ID 불일치를 바로 볼 수 있다.
- 일치 보고서가 실패해도 템플릿 생성, 비밀값 후보 생성, Android upload key 준비 자체는 완료 처리한다. 사용자가 채워야 하는 값은 별도 설정 항목으로 안내한다.
- `tests/test_private_release_setup.py`에 일치 보고서 포함 회귀 테스트를 추가했다.
