# Google Play 등록 이미지

Play Console의 한국어 스토어 등록정보에 바로 사용할 수 있는 이미지입니다.

## 권장 앱 이름

`알파메이트 - 주식 테마·매매복기`

앱 안의 브랜드 표기는 기존대로 `AlphaMate`를 유지합니다.

## 업로드 파일

| Play Console 항목 | 파일 |
| --- | --- |
| 앱 아이콘 | `icon-512.png` |
| 그래픽 이미지 | `feature-graphic-1024x500.png` |
| 휴대전화 스크린샷 | `screenshots/01-theme-ranking-1080x1920.png` |
| 휴대전화 스크린샷 | `screenshots/02-theme-stocks-1080x1920.png` |
| 휴대전화 스크린샷 | `screenshots/03-chart-detail-1080x1920.png` |
| 휴대전화 스크린샷 | `screenshots/04-journal-input-1080x1920.png` |
| 휴대전화 스크린샷 | `screenshots/05-ai-review-1080x1920.png` |

`preview-contact-sheet.png`는 전체 구성을 한 번에 확인하기 위한 미리보기이며 Play Console에는 올리지 않습니다.

## 권장 소개 문구

짧은 설명:

> 테마 상승률과 종목 차트를 살펴보고, 내 매매를 AI와 함께 복기하세요.

첫 출시에서는 한국어 등록정보를 먼저 사용하고, 영문 등록정보는 실제 영문 UI를 제공할 때 추가하는 편이 안전합니다.

## 다시 만들기

실제 앱 화면을 `raw` 폴더에 같은 파일명으로 교체한 뒤 저장소 루트에서 실행합니다.

```powershell
python .\scripts\generate_play_store_assets.py
```
