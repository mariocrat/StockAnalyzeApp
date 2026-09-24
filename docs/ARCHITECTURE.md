# StockBoda Architecture

담당: 구성요소·API/data flow·runtime 경계.
근거: [backend/main.py](../backend/main.py), [frontend package](../frontend/package.json), [Capacitor config](../frontend/capacitor.config.json), [Render Blueprint](../render.yaml).

## 구성요소와 연결

```text
React/Vite 웹 화면 또는 Android Capacitor WebView
  └─ VITE_API_BASE → FastAPI
       ├─ 외부 시세 조회 → 테마/종목/차트와 파일·메모리 cache
       ├─ Kakao/Naver → 내부 사용자/세션
       ├─ 매매 입력 → 일반 계산 또는 OpenAI AI 복기
       ├─ Google Play 검증/RTDN → 권한·주문·구독
       └─ AdMob SSV → 광고 보상
```

- [App.jsx](../frontend/src/App.jsx): 테마/종목 탐색, 차트 전환, 광고와 권한 표시.
- [TradingJournal.jsx](../frontend/src/components/TradingJournal.jsx): 입력·로그인·저장·복기함·결제·광고·export가 함께 연결됨.
- [backend/main.py](../backend/main.py): API 등록, 요청 제한, AI 실행 조합, 운영 이벤트, cache scheduler.
- [access_control.py](../backend/core/access_control.py): 이용권·구독·구매 원장·광고 검증.
- Android는 웹 빌드를 포장하며 [MainActivity](../frontend/android/app/src/main/java/com/mariocrat/stockanalyze/MainActivity.java)가 별도 App Open 광고 플러그인을 등록한다.

주요 파일이 여러 책임을 가진다. 기능 변경 때 실제 호출 경로와 상태 초기화를 확인한다. 관련 작업의 최소 경계부터 분리하며 일괄 refactor를 끼워 넣지 않는다.

## API와 사용자 데이터 흐름

| 경로군 | 데이터/책임 |
| --- | --- |
| /api/themes, /api/theme_stocks, /api/stock/*, /api/search, /api/macro | 외부 시장 데이터와 cache |
| /api/auth/*, /api/me | 공급자 로그인, 내부 세션, 설정 |
| /api/journal/review-once, charts-once | 요청 본문의 매매를 계산·차트화 |
| /api/journal/ai-review-once | 인증·동의·권한 차감 후 AI 호출, 설정에 따른 복기 저장 |
| /api/journal/trades, review-history | 사용자별 저장 데이터 |
| /api/me/export-data, account-data | 현재 사용자의 내보내기·삭제 |
| /api/journal/google-play-purchase, google-play-rtdn, admob-ssv | 외부 검증과 이용권/보상 반영 |
| /api/admin/*, /api/client-events | 운영 조회·변경 및 오류 보고 |

정확한 method/schema는 main.py의 route와 Pydantic 입력 모델에서 확인한다. 이 표는 완전한 API 명세가 아니다. 관리자 경로·callback·GET 요청도 상태를 변경할 수 있다.

계정/권한/매매/복기/로그는 DB 다섯 개로 분리되어 있다. 저장 opt-in, 데이터 소유권, 삭제·복구의 상세 책임은 [DATA](DATA.md), 인증과 외부 전송은 [SECURITY](SECURITY.md)에 둔다.

## Runtime과 환경

로컬 wrapper는 backend 8002, frontend 5174를 사용한다. 일반 npm dev 실행은 동일 포트를 보장하지 않는다. 프로세스·포트 소유자를 확인하고 기존 프로세스를 임의 종료하지 않는다.

Frontend API는 빌드 시 VITE_API_BASE로 정해지며 없으면 loopback fallback이 있다. Android debug가 개발 API를 의미하지 않는다. 환경별 실제 선택 경로는 [RELEASE](RELEASE.md)를 따른다.

Render Blueprint는 Python backend와 persistent disk를 정의한다. React 웹의 별도 hosting/deployment pipeline은 이 repository에서 확인하지 못했다. backend의 공개 landing/legal HTML과 React 앱 배포는 구분한다.

OAuth 티켓·rate limiter·AI idempotency cache·일부 lock은 프로세스 메모리에 있다. DB만 공유한다고 multi-worker/인스턴스 안전성이 확보되지 않는다. scale 변경은 별도 고위험 계획이 필요하다.

## 활성 구현과 호환성

현재 AI route는 [ai_review_v2.py](../backend/core/ai_review_v2.py)를 사용한다. ai_review.py 및 cache.py 같은 기존 파일의 존재만으로 활성 경로를 판단하지 말고 import/call site를 추적한다. Legacy GET /api/journal/ai-review는 410으로 닫혀 있다.

StockBoda는 표시 브랜드다. 기존 package/application ID, OAuth scheme과 관련 identifier, product ID, storage key, `ALPHAMATE_*` 기술 식별자는 호환성 계약일 수 있다. 변경이 작업 범위에서 명시적으로 승인되고 compatibility/migration 계획, rollback/recovery 계획, 관련 external configuration 검증 계획이 모두 있을 때만 변경한다. 그 외에는 기존 문자열을 그대로 보존한다.

조사한 코드에서 증권사 업로드/import 구현은 확인하지 못했다. 다른 worktree의 이름이나 계획을 감사 대상의 구현 증거로 사용하지 않는다.
