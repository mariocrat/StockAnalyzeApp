# Quick verification 문서 동기화

- `docs/quick_verify.md`의 `verify_project.bat` 검사 항목을 실제 `scripts/verify_project.ps1`의 `Run-Step` 이름과 맞췄다.
- 모바일 결제, 클라이언트 이벤트 로그, API 오류 request ID, AI 복기 idempotency 테스트가 문서에서 빠지지 않게 했다.
- `tests/test_quick_verify_docs.py`를 추가해 검증 스크립트 단계가 늘어나면 빠른 검증 문서도 함께 갱신되도록 했다.
