# Private release setup alignment report

- `prepare_private_release_setup.bat`의 마지막 보고서에 서버/앱 출시 설정 일치 검사를 추가했다.
- 이제 원클릭 준비 흐름에서도 `GOOGLE_PLAY_PACKAGE_NAME`과 `VITE_GOOGLE_PLAY_PACKAGE_NAME`, 카카오/네이버 Redirect URI 불일치를 바로 볼 수 있다.
- alignment 보고서가 실패해도 템플릿 생성, 비밀값 후보 생성, Android upload key 준비 자체는 완료 처리되며, 사용자가 채워야 할 외부 설정으로 안내된다.
- `tests/test_private_release_setup.py`에 alignment 보고서 포함 회귀 테스트를 추가했다.
