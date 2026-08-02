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

Google Play 결제 운영에는 아래 값도 확인합니다.

- `GOOGLE_PLAY_PACKAGE_NAME=com.mariocrat.stockanalyze`
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`: 내려받은 JSON 파일의 내용을 한 줄 값으로 저장
- `GOOGLE_PLAY_RTDN_SHARED_TOKEN`: 32자 이상의 랜덤 비밀값
- `GOOGLE_PLAY_RTDN_OIDC_AUDIENCE=https://api.alphamate.co.kr/api/journal/google-play-rtdn`
- `GOOGLE_PLAY_RTDN_OIDC_EMAIL=alphamate-rtdn-push@alphamate-504303.iam.gserviceaccount.com`

## Google Play 실시간 결제 알림 설정

이 설정은 구독 취소·갱신·결제 실패를 앱을 다시 열기 전에도 서버가 알 수 있게 합니다. 알림 내용만으로 권한을 바꾸지 않고, 서버가 Google Play Developer API를 다시 조회해 실제 상태와 만료 시각을 확인합니다.

### 1. Google Cloud에서 알림 통로 만들기

1. Google Cloud Console에서 프로젝트 `alphamate-504303`을 선택합니다.
2. **API 및 서비스 > 라이브러리**에서 `Google Play Android Developer API`를 검색해 **사용**을 누릅니다.
3. **IAM 및 관리자 > 서비스 계정 > 서비스 계정 만들기**를 누릅니다.
4. 이름을 `alphamate-rtdn-push`로 입력하고 만듭니다.
5. **Pub/Sub > 주제 > 주제 만들기**를 누르고 ID를 `alphamate-play-rtdn`으로 만듭니다.
6. 만든 주제의 **권한**에서 `google-play-developer-notifications@system.gserviceaccount.com`을 추가하고 역할은 **Pub/Sub 게시자**로 선택합니다.
7. **Pub/Sub > 구독 > 구독 만들기**를 누릅니다.
8. 구독 ID는 `alphamate-play-rtdn-push`, 주제는 `alphamate-play-rtdn`, 전송 유형은 **푸시**를 선택합니다.
9. 엔드포인트는 아래처럼 입력합니다. 마지막 값은 Render의 `GOOGLE_PLAY_RTDN_SHARED_TOKEN`과 반드시 같아야 합니다.

```text
https://api.alphamate.co.kr/api/journal/google-play-rtdn?verification_token=Render와_같은_공유_토큰
```

10. **인증 사용**을 켜고 서비스 계정은 `alphamate-rtdn-push@alphamate-504303.iam.gserviceaccount.com`을 선택합니다.
11. 대상(Audience)은 `https://api.alphamate.co.kr/api/journal/google-play-rtdn`으로 입력합니다. 이 값에는 `verification_token`을 붙이지 않습니다.
12. Google Cloud의 **IAM**에서 Pub/Sub 서비스 에이전트 `service-프로젝트번호@gcp-sa-pubsub.iam.gserviceaccount.com`에 **서비스 계정 토큰 생성자** 역할을 줍니다. 프로젝트 번호는 Cloud Console의 프로젝트 정보에서 확인합니다.

### 2. Play Console에 주제 연결하기

1. Play Console에서 **AlphaMate > 수익 창출 > 수익 창출 설정**으로 이동합니다.
2. **실시간 개발자 알림**에서 아래 주제 이름을 입력합니다.

```text
projects/alphamate-504303/topics/alphamate-play-rtdn
```

3. 테스트 알림을 전송하고 오류가 없으면 **저장**을 누릅니다.

### 3. Render 값 확인하기

1. Render에서 **alphamate-api > Environment**를 엽니다.
2. `GOOGLE_PLAY_RTDN_SHARED_TOKEN`이 Pub/Sub push URL의 `verification_token`과 같은지 확인합니다.
3. `GOOGLE_PLAY_RTDN_OIDC_EMAIL`에 push 서비스 계정 이메일을 넣습니다.
4. `GOOGLE_PLAY_RTDN_OIDC_AUDIENCE`에 쿼리 문자열 없는 callback 주소를 넣습니다.
5. **Save Changes** 후 배포가 끝날 때까지 기다립니다.

구독 취소는 즉시 Pro를 끊지 않습니다. 서버는 Google Play가 반환하는 실제 `expiryTime`까지 혜택을 유지하고, 그 시각이 지난 뒤에만 비활성화합니다. 월간 상품도 달력상 고정 30일이 아니라 Google Play의 결제 주기를 따릅니다.

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

Render의 Health Check는 5초 timeout으로 민감합니다. 그래서 `render.yaml`은 `ALPHAMATE_WARM_CACHE_ON_STARTUP=false`로 시작 직후 전체 테마 계산을 실행하지 않습니다.

기간 수익률 캐시는 Persistent Disk의 `/var/data/alphamate/cache`에 저장되고, 외부 시세 요청은 최대 8개로 제한됩니다. 서버는 한국시간 매일 00:01에 한 번의 제한된 시세 수집으로 네 기간 캐시를 갱신하며, 종목별 일봉 전체를 메모리에 쌓지 않습니다. 캐시가 아직 없을 때 앱은 서버 요청을 오래 붙잡지 않고 업데이트 안내를 표시한 뒤 자동으로 다시 확인합니다.

배포 직후 캐시를 바로 준비하려면 관리자 토큰을 현재 PowerShell 세션의 환경변수에만 넣고 아래 명령을 한 번 실행합니다. 토큰을 문서나 Git에 적지 않습니다.

```powershell
$headers = @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
Invoke-RestMethod -Method Post -Uri 'https://api.alphamate.co.kr/api/admin/theme-cache/refresh' -Headers $headers
Invoke-RestMethod -Uri 'https://api.alphamate.co.kr/api/admin/theme-cache/status' -Headers $headers
```

`periods`의 `1D`, `1W`, `1M`, `1Y`가 모두 `ready: true`이면 초기 캐시 준비가 끝난 상태입니다.
