# Google Play 등록 이미지

Play Console의 한국어 스토어 등록정보에 바로 사용할 수 있는 이미지입니다.

## 권장 앱 이름

Google Play 한국어 등록명은 `스톡보다`입니다.

앱 내부 브랜드 표기는 `StockBoda`를 사용합니다. `주식 테마·매매복기`는 설명/마케팅 문구로만 사용하며 앱 이름에 포함하지 않습니다.

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

실제 모바일 CSS viewport를 사용하고 DPR 2~3으로 충분한 픽셀 해상도를 확보해 `raw` 폴더에 같은 파일명으로 저장합니다. 현재 기준은 CSS viewport 390×844, DPR 3이며 결과 PNG는 1170×2532입니다. viewport 자체를 1080×1920으로 설정하거나 화면 비율을 늘이거나 줄이지 않습니다. 최종 이미지는 원본 비율을 유지한 crop/resize만 사용하며, AI 복기 화면을 합성하지 않습니다.

캡처 전에는 `OPENAI_API_KEY`를 Git 파일이 아닌 현재 사용자 또는 프로세스 환경변수로 설정하고, 실제 Android 기기에서 production 앱 화면을 준비합니다. 캡처 raw를 교체한 뒤 저장소 루트에서 다음 명령으로 최종 이미지와 contact sheet를 생성합니다.

```powershell
python .\scripts\generate_play_store_assets.py
```
