# Android launcher icon alignment

- Android launcher icon, round icon, adaptive foreground icon의 로고 위치를 다시 중앙 정렬했다.
- 원본 `frontend/src/assets/app-logo-dark.png`에서 글자 영역을 제외한 A 로고만 추출해 각 해상도 아이콘에 같은 비율로 배치했다.
- `tests/test_android_icon_alignment.py`를 추가해 해상도별 `ic_launcher_foreground.png`의 실제 보이는 로고 중심이 캔버스 중심에서 벗어나지 않도록 확인한다.
