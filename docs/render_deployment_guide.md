# Render 배포 가이드

이 문서는 비개발자가 Render 화면에서 직접 항목을 하나씩 고르지 않도록 만든 안내입니다. 저장소 루트의 `render.yaml` Blueprint가 백엔드 서비스, Starter 플랜, 1GB Persistent Disk, SQLite 저장 경로, Health Check, 비밀값 입력 방식을 대신 정의합니다.

## Render에서 누르는 순서

1. Render에 로그인합니다.
2. Dashboard에서 **New +** 버튼을 누릅니다.
3. **Blueprint** 또는 **New Blueprint Instance**를 선택합니다.
4. GitHub 저장소 `mariocrat/StockAnalyzeApp`을 연결합니다.
5. Render가 저장소 루트의 `render.yaml`을 찾으면 내용을 확인합니다.
6. 서비스 이름이 `alphamate-api`, Plan이 `starter`, Region이 `Singapore`인지 확인합니다.
7. 비밀값 입력 화면에서 `sync: false`로 표시되는 항목을 채웁니다.
8. **Apply** 또는 **Deploy** 버튼을 누릅니다.
9. 배포가 끝나면 Render 서비스 URL의 `/healthz`가 정상 응답하는지 확인합니다.
10. Cloudflare DNS에서 `api.alphamate.co.kr`을 Render 서비스로 연결합니다.

## Render에 나중에 직접 넣어야 하는 비밀값

실제 비밀값은 GitHub 파일에 절대 넣지 않습니다. Render 화면의 Environment 탭에서만 입력합니다.

- `OPENAI_API_KEY`
- `KAKAO_CLIENT_ID`
- `KAKAO_CLIENT_SECRET`
- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`
- `GOOGLE_PLAY_RTDN_OIDC_EMAIL`
- `ADMOB_REWARDED_AD_UNIT_ID`

`ALPHAMATE_ADMIN_TOKEN`과 `GOOGLE_PLAY_RTDN_SHARED_TOKEN`은 Blueprint에서 `generateValue: true`로 설정되어 Render가 랜덤 값을 만들 수 있게 했습니다.

## SQLite 저장 위치

Render Persistent Disk는 `/var/data/alphamate`에 붙습니다. 모든 SQLite DB는 이 디스크 아래를 사용합니다.

- `/var/data/alphamate/accounts.sqlite3`
- `/var/data/alphamate/access.sqlite3`
- `/var/data/alphamate/trades.sqlite3`
- `/var/data/alphamate/review_history.sqlite3`
- `/var/data/alphamate/event_log.sqlite3`

## Postgres 전환 검토 기준

초기 운영은 SQLite + Render Persistent Disk로 시작합니다. 다음 신호가 보이면 Postgres 전환을 미리 준비합니다.

- Render Logs에 `database is locked`, `sqlite`, `timeout` 오류가 반복됩니다.
- 로그인, 결제, AI 복기 요청에서 5xx 오류가 늘어납니다.
- 서버 인스턴스를 2개 이상으로 늘리고 싶어집니다.
- 복기 이력과 결제 기록 백업/복구 중요도가 커집니다.
- 하루 AI 복기 요청이 수백 건 이상으로 올라갑니다.
- Render Metrics에서 응답 시간이 계속 길어집니다.

Postgres 전환은 데이터가 돈과 연결되기 전에 별도 작업으로 진행하는 것이 안전합니다.

## 현재 Blueprint가 잡은 운영 주소

- 운영 웹 주소: `https://alphamate.co.kr`
- 운영 API 주소: `https://api.alphamate.co.kr`
- 개인정보처리방침: `https://alphamate.co.kr/privacy`
- 카카오 Redirect URI: `https://api.alphamate.co.kr/api/auth/kakao/callback`
- 네이버 Callback URL: `https://api.alphamate.co.kr/api/auth/naver/callback`
- Health Check Path: `/healthz`

## 배포 후 확인

배포가 끝나면 Render Shell 또는 브라우저에서 아래 주소를 확인합니다.

```text
https://api.alphamate.co.kr/healthz
```

정상이라면 JSON 응답이 나오고, Render의 Health Check도 통과해야 합니다.