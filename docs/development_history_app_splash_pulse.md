# App splash pulse overlay

- 앱 시작 직후 centered `app-icon.png`를 보여주는 웹 스플래시 오버레이를 추가했다.
- 로고에는 `app-splash-pulse` 애니메이션으로 심장 박동처럼 살짝 커졌다 작아지는 효과를 적용했다.
- 약 1.15초 후 fade-out을 시작하고 약 1.45초 후 DOM에서 제거한다.
- `prefers-reduced-motion: reduce`에서는 pulse 애니메이션을 끈다.
- `tests/test_app_splash_ui.py`로 스플래시 컴포넌트, CSS 애니메이션, asset 존재를 확인한다.
