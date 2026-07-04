# AlphaMate 수동 테스트 가이드

개발자가 아니어도 현재 앱에서 꼭 확인해야 할 흐름만 정리한 문서입니다.

## 1. 앱 실행

1. `run_app.bat`를 실행합니다.
2. 브라우저에서 `http://127.0.0.1:5174/`를 엽니다.
3. 왼쪽 메뉴에서 `매매복기` 화면으로 이동합니다.

## 1-1. 앱 이름 바꾸기

앱 이름을 나중에 바꾸고 싶으면 `frontend/.env`에 아래 값을 넣습니다.

```env
VITE_APP_NAME=새앱이름
```

이 값은 왼쪽 상단 앱 이름과 브라우저 탭 제목에 적용됩니다. 내부 저장 데이터 키는 기존 사용자 데이터 보호를 위해 당장 바꾸지 않습니다.

## 2. 개발용 로그인 확인

실제 카카오/네이버 키가 없어도 계정 분리와 복기권 차감 구조를 확인하기 위한 테스트입니다.

1. `계정/데이터 관리` 영역에서 `카카오` 버튼을 누릅니다.
2. 로그인 상태가 카카오 개발 계정처럼 표시되는지 확인합니다.
3. `이용권 현황`에서 개발용 복기권 구매 버튼을 눌러 잔여 수량이 늘어나는지 확인합니다.
4. `네이버` 버튼을 눌러 네이버 개발 계정으로 바꿉니다.
5. 카카오 계정에서 충전한 복기권이나 저장 기록이 네이버 계정에 섞이지 않는지 확인합니다.
6. 다시 `카카오` 버튼을 누르면 카카오 계정의 상태가 유지되는지 확인합니다.

정상 결과:

- 카카오와 네이버는 서로 다른 사용자로 보입니다.
- 복기권, 저장된 매매 기록, 계정 요약은 로그인한 사용자별로 분리됩니다.

## 3. 실제 카카오/네이버 로그인 준비 확인

실제 로그인은 아래 값이 모두 준비되어야 테스트할 수 있습니다.

frontend `.env`:

- `VITE_KAKAO_REST_API_KEY`
- `VITE_KAKAO_REDIRECT_URI`
- `VITE_NAVER_CLIENT_ID`
- `VITE_NAVER_REDIRECT_URI`

root `.env` 또는 backend `.env`:

- `KAKAO_CLIENT_ID`
- `KAKAO_CLIENT_SECRET` 또는 카카오 설정에 따라 생략 가능
- `KAKAO_REDIRECT_URI`
- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `NAVER_REDIRECT_URI`

확인 방법:

1. `매매복기` 화면을 엽니다.
2. `계정/데이터 관리` 아래의 `실제 로그인 준비` 카드를 확인합니다.
3. 카드에서 프론트 키, 서버 설정, Redirect URI 상태를 확인합니다.
4. 서버 설정이 빠져 있으면 `KAKAO_CLIENT_ID`, `NAVER_CLIENT_ID`처럼 필요한 환경변수 이름이 표시됩니다.
5. 모든 값이 있으면 실제 로그인 버튼을 눌렀을 때 각 provider 로그인 페이지로 이동합니다.
6. 개발 모드에서는 위쪽 카카오/네이버 버튼이 개발용 계정 전환 버튼입니다. 실제 로그인 테스트는 `VITE_ALPHAMATE_ENV=production` 또는 `VITE_ENABLE_DEV_TOOLS=false`로 실행한 뒤 확인합니다.

## 4. 매매 이력 저장 확인

1. 개발용 또는 실제 계정으로 로그인합니다.
2. `매매 이력 저장` 체크박스를 켭니다.
3. 매매 기록을 하나 입력하고 저장합니다.
4. `계정/데이터 관리`의 저장된 매매 기록 수가 늘어나는지 확인합니다.
5. 새로고침 후 기록이 남아 있는지 확인합니다.
6. 다른 계정으로 로그인했을 때 이전 계정의 기록이 보이지 않는지 확인합니다.
7. `저장 기록 전체 삭제`를 누르면 현재 로그인한 계정의 기록만 삭제되는지 확인합니다.
8. `내 데이터 내보내기`를 누르면 현재 로그인 계정의 저장 기록과 이용권 현황 JSON 파일이 내려받아지는지 확인합니다.
9. `계정 데이터 삭제`를 누르면 현재 로그인 계정의 저장 기록, 복기권/구독 상태, 광고 보상 기록, 로그인 연결 정보가 정리되고 로그아웃 상태로 바뀌는지 확인합니다.

## 5. 일반/심층 복기 확인

1. 매매 기록을 입력합니다.
2. `AI 분석` 개인정보 및 매매 기록 전송 동의를 체크합니다.
3. `일반 복기`를 실행합니다.
4. 결과가 한 줄 총평, 잘한 점, 아쉬운 점, 다음 체크리스트 3개 중심으로 짧게 나오는지 확인합니다.
5. `심층 복기`를 실행합니다.
6. 심층 복기권이 없으면 구매 또는 광고 보상 안내가 나오는지 확인합니다.

## 6. 개발 데이터 초기화

개발 중 계정/복기권/매매 기록 상태가 꼬이면 backend를 끈 뒤 아래 파일을 삭제하고 다시 실행합니다.

- `backend/data/accounts.sqlite3`
- `backend/data/access.sqlite3`
- `backend/data/trades.sqlite3`

이 파일들은 개발용 로컬 DB이며 GitHub에는 올리지 않습니다.

## 7. 배포 전 안전 확인

1. `frontend` 폴더에서 `npm run build`를 실행합니다.
2. `frontend/dist` 안에 `dev-token`, `dev-ad-reward`, `dev-pro-entitlement` 문자열이 없는지 확인합니다.
3. backend에서 `ALPHAMATE_ENV=production`일 때 개발용 로그인과 개발용 복기권 구매가 거부되는지 확인합니다.
4. 실제 API Key와 provider secret은 `.env` 또는 서버 secret manager에만 넣고 GitHub에는 올리지 않습니다.

## 7-1. Codex 인앱 브라우저 제어가 막힐 때

Codex에서 인앱 브라우저 제어가 `CreateProcessAsUserW failed: 5` 같은 Windows 권한 오류로 실패할 수 있습니다. 이 경우 앱 코드 문제가 아니라 Codex의 브라우저 제어 보조 실행기가 Windows 세션에서 새 프로세스를 만들지 못하는 상태입니다.

확인 순서:

1. Codex 앱을 완전히 종료한 뒤 다시 실행합니다.
2. 같은 URL을 다시 열어봅니다.
3. 계속 실패하면 Codex 앱 업데이트 여부를 확인합니다.
4. 그래도 실패하면 앱 자체 확인은 아래 HTTP/API 검증으로 대체합니다.

대체 확인:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5174/?view=journal`&oauth_provider=kakao
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8002/api/auth/oauth-config
```

두 요청이 `200`이면 프론트와 백엔드는 살아 있는 상태입니다.

## 8. Google Play 결제 준비 확인

현재는 Google Play 소모성 복기권 검증 코드가 들어간 상태입니다. 실제 결제 테스트는 Google Play Console 상품 ID와 서비스 계정 설정이 필요합니다.

배포 준비 상태 API:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8002/api/app/readiness
```

확인할 내용:

- `overall_ready`가 서버 설정 전체 준비 여부를 표시합니다.
- `sections.ai`, `sections.login`, `sections.google_play`, `sections.admob`에서 항목별 준비 상태를 확인합니다.
- 응답에는 API Key, client secret, Google 서비스 계정 JSON 원문이 포함되면 안 됩니다.

1. backend가 켜진 상태에서 `http://127.0.0.1:8002/api/journal/products`를 엽니다.
2. `consumables`에 일반/심층 복기권 상품이 보이는지 확인합니다.
3. `subscriptions`에 Pro 월 구독 상품이 보이는지 확인합니다.
4. `google_play.missing_server_settings`에 빠진 서버 설정이 표시되는지 확인합니다.
5. Android 앱에서는 이용권 구매 버튼이 Google Play Billing SDK를 열고, 구매 token을 `POST /api/journal/google-play-purchase`로 보내 서버 검증을 요청합니다.
6. Google Play 구매 요청 endpoint는 실제 Google Play purchase token이 검증된 경우에만 복기권을 지급합니다.

운영 모드에서 필요한 Google Play 상품 ID 환경변수:

- `GOOGLE_PLAY_BASIC_REVIEW_30_ID`
- `GOOGLE_PLAY_BASIC_REVIEW_100_ID`
- `GOOGLE_PLAY_ADVANCED_REVIEW_5_ID`
- `GOOGLE_PLAY_ADVANCED_REVIEW_10_ID`
- `GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID`
- `GOOGLE_PLAY_PRO_MONTHLY_ID`

정상 결과:

- 상품 ID와 가격/수량은 보입니다.
- `ALPHAMATE_ENV=production`에서는 위 상품 ID가 모두 설정되어야 `google_play.ready`가 true가 됩니다.
- 서비스 계정 secret 값은 응답에 보이지 않습니다.
- 서비스 계정 설정이 없거나 잘못되면 503으로 막히고 복기권이 충전되지 않습니다.
- 같은 purchase token을 다시 보내도 복기권은 한 번만 충전됩니다.
- Pro 구독은 Google Play subscription token이 검증되고 만료 시간이 유효할 때만 Pro 상태로 반영됩니다.
- 같은 subscription token이 만료/비활성 상태로 다시 검증되면 Pro 상태가 해제되어야 합니다.
- 웹 화면에서는 실제 Google Play 결제가 열리지 않습니다. 개발 모드에서는 기존 개발용 충전 흐름으로 버튼 동작을 확인하고, 실제 결제는 Android 앱과 Play Console 라이선스 테스트 계정으로 확인해야 합니다.
- `GOOGLE_PLAY_RTDN_SHARED_TOKEN`을 설정한 뒤 Pub/Sub push가 `POST /api/journal/google-play-rtdn`로 들어오면 서버가 Google Play API를 다시 조회해 Pro 상태를 갱신해야 합니다.
- 배포 전에는 Google Play Console 테스트 결제, 서비스 계정 권한, Pub/Sub push 인증을 함께 확인해야 합니다.
- Pub/Sub 인증 push를 쓰는 경우 `GOOGLE_PLAY_RTDN_OIDC_AUDIENCE`, `GOOGLE_PLAY_RTDN_OIDC_EMAIL`을 설정해 JWT 검증이 켜지는지 확인합니다.

## AdMob 보상형 광고 확인

현재 서버에는 AdMob SSV 콜백을 검증하고 보상을 1회 기록/차감하는 구조가 들어간 상태입니다. 실제 광고 테스트는 AdMob 광고 단위와 모바일 앱 SDK 연결이 필요합니다.

확인할 항목:

1. 운영 서버 `.env`에 `ADMOB_REWARDED_AD_UNIT_ID`를 설정합니다.
2. AdMob 콘솔의 보상형 광고 SSV 콜백 URL을 `https://서버주소/api/journal/admob-ssv`로 설정합니다.
3. 모바일 앱에서 로그인된 AlphaMate 사용자 ID를 AdMob SSV의 `user_id`로 전달해야 합니다.
4. 광고 시청 후 서버 DB의 `admob_reward_events`에 `pending` 보상이 1건 생기는지 확인합니다.
5. 일반 복기를 1회 실행하면 해당 보상이 `consumed`로 바뀌고, 같은 `transaction_id`는 다시 지급되지 않아야 합니다.

개발 PC의 웹 화면만으로는 실제 AdMob 광고 시청을 완전히 검증할 수 없습니다. Android 앱에는 `@capacitor-community/admob` 기반 보상형 광고 연결이 들어가 있으며, 웹 화면에서는 네이티브 광고가 실행되지 않습니다.

주의:

- Android AdMob 앱 ID는 `VITE_ADMOB_ANDROID_APP_ID`로 빌드 때 주입됩니다.
- `frontend/.env`의 `VITE_ADMOB_REWARDED_AD_UNIT_ID`가 비어 있으면 Google 테스트 보상형 광고 단위를 사용합니다.
- 테스트 광고는 AdMob SSV 콜백을 보내지 않으므로 서버의 실제 보상 지급까지 검증할 수 없습니다.
- 실제 보상 지급 검증은 운영 AdMob 앱 ID, 운영 보상형 광고 단위, SSV 콜백 URL을 모두 설정한 뒤 실제 광고 단위로 확인해야 합니다.
- 출시 전에는 `npm run release:check`로 테스트 앱 ID와 테스트 광고 단위가 남아 있지 않은지 확인해야 합니다.

광고 정책 설정:

- `ALPHAMATE_ADS_PER_ADVANCED_TICKET=5`: 광고 5회 시청 시 주간 심층 복기권 1장 지급
- `ALPHAMATE_FORCE_REWARDED_AD_CHAIN=false`: 여러 보상형 광고를 연속으로 강제하지 않음
- `GET /api/journal/products`에서 `admob.ready`, `settings.ad_policy` 값을 확인할 수 있습니다.

## 백엔드 배포 전 환경 검사

서버를 운영 모드로 배포하기 전에는 아래 명령으로 AI Key, 로그인, Google Play, AdMob 설정 누락을 한 번에 확인합니다.

```powershell
cd D:\Project\Vibe\StockAnalyze
.\.venv\Scripts\python.exe backend\scripts\validate_release_env.py
```

정상일 때:

```text
백엔드 출시 환경 검사를 통과했습니다.
```

설정이 빠져 있거나 Google Play 서비스 계정 JSON/private key 형식이 잘못되면 `ALPHAMATE_ENV`, `OPENAI_API_KEY`, `KAKAO_CLIENT_ID`, `GOOGLE_PLAY_*`, `ADMOB_REWARDED_AD_UNIT_ID`, `ALPHAMATE_PRIVACY_POLICY_URL`처럼 필요한 환경변수 이름만 표시합니다. API Key나 Google 서비스 계정 JSON 원문은 출력하면 안 됩니다.

`ALPHAMATE_PRIVACY_POLICY_URL`은 Play Store에 등록할 공개 HTTPS 개인정보처리방침 주소입니다. 실제 배포 전에는 앱 안의 `개인정보/AI 이용 안내` 문구와 이 URL의 정책 문서 내용이 서로 어긋나지 않는지 확인합니다.

운영용 환경변수를 별도 파일에 둘 경우 `ALPHAMATE_ENV_FILE=D:\secure\alphamate-backend.env`처럼 지정한 뒤 같은 명령을 실행할 수 있습니다.

운영 장애 확인용 로그는 `ALPHAMATE_EVENT_LOG_DB_PATH`에 지정한 SQLite DB의 `operational_events` 테이블에 저장됩니다. 로컬 개발 기본값은 `backend/data/event_log.sqlite3`입니다. 실패한 `/api/...` 요청의 method, path, status code, 사용자 ID, 메시지를 확인할 수 있고, token/secret/password/private key처럼 비밀값으로 보이는 필드는 저장 전에 가려집니다.

모바일 앱에서 AdMob 보상형 광고나 Google Play 결제 처리 중 실패가 나면 프론트가 `POST /api/client-events`로 실패 정보를 보냅니다. 이 보고 자체가 실패해도 사용자의 원래 작업을 추가로 막지 않으며, 결제 token이나 세션 token 같은 값은 프론트와 서버 양쪽에서 가려집니다.

프론트 화면에서 예상하지 못한 JavaScript 오류나 처리되지 않은 Promise 오류가 발생해도 같은 `POST /api/client-events` 경로로 보고됩니다. 같은 페이지 로딩 중 같은 종류의 전역 오류는 한 번만 보고해 로그 폭주를 줄입니다.

운영 로그 details는 비밀값을 가릴 뿐 아니라, 긴 문자열과 큰 배열/객체도 저장 전에 잘라냅니다. 장애 원인 파악에 필요한 요약 정보만 남기고 로그 DB가 커지는 일을 줄이기 위한 장치입니다.

API 응답에는 `X-Request-ID` 헤더가 붙습니다. 사용자가 오류 화면을 제보할 때 이 값을 함께 받으면 운영 로그의 `request_id`와 맞춰 어떤 요청이 실패했는지 찾기 쉽습니다. 앱이나 프론트가 직접 `X-Request-ID`를 보내면 안전한 형식일 때 같은 값을 이어 씁니다.

프론트에서 API 실패 메시지를 표시할 때 `X-Request-ID`가 있으면 메시지 끝에 `(문의용 ID: ...)`가 붙습니다. 사용자가 문의할 때 이 값을 알려주면 아래 `request_id` 조회로 같은 실패 로그를 찾을 수 있습니다.

특정 요청 ID만 조회하려면 관리자 로그 API에 `request_id`를 같이 넘깁니다.

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?request_id=요청ID' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

사용자 또는 API 기준으로 좁혀 보려면 `user_id`, `path`, `status_code`도 함께 사용할 수 있습니다.

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?user_id=사용자ID&path=/api/journal/google-play-purchase&status_code=402' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

특정 로그 한 건이나 장애가 발생한 시간대만 보려면 `event_id`, `created_after`, `created_before`를 사용합니다. 시간 값은 운영 로그의 `created_at`처럼 ISO 형식으로 넣습니다.

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?created_after=2026-06-22T10:00:00%2B00:00&created_before=2026-06-22T11:00:00%2B00:00' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

서버 관리자만 최근 운영 로그를 조회하려면 운영 서버에 `ALPHAMATE_ADMIN_TOKEN`을 32자 이상의 긴 랜덤 값으로 설정한 뒤 아래처럼 호출합니다. 이 토큰은 앱이나 frontend `.env`에 넣으면 안 됩니다.

```powershell
$env:ALPHAMATE_ADMIN_TOKEN='서버에_설정한_관리자_토큰'
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?limit=50&level=error' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

다음 페이지의 오래된 로그를 보려면 `offset`을 사용합니다. 예를 들어 `limit=50&offset=50`은 첫 50건 다음의 로그를 조회합니다.

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?limit=50&offset=50' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

최근 로그를 하나씩 보기 전에 어떤 오류가 많은지 먼저 보려면 요약 API를 호출합니다. 요약 API도 위의 `request_id`, `user_id`, `path`, `status_code`, `event_id`, `created_after`, `created_before` 필터를 똑같이 사용할 수 있습니다. 응답에는 level, event type, path뿐 아니라 status code와 사용자별 집계도 포함됩니다.

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events/summary?limit=500' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events/summary?path=/api/journal/google-play-purchase&status_code=402' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

오래된 운영 로그를 정리하려면 아래처럼 보관기간을 일 단위로 지정합니다. 실수 방지를 위해 7일 미만은 거부되며, 보통은 90일 이상을 권장합니다.

```powershell
Invoke-RestMethod -Method Delete -Uri 'https://your-api.example.com/api/admin/operational-events/retention?retention_days=90' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

서버 시작 시 자동으로 같은 정책을 적용하려면 운영 서버 환경변수에 `ALPHAMATE_EVENT_LOG_RETENTION_DAYS=90`처럼 설정합니다. 이 값이 없으면 자동 삭제는 실행하지 않습니다.

클라이언트 오류 보고 API는 IP별 분당 기본 60회로 제한됩니다. 운영 환경에서 필요하면 `ALPHAMATE_CLIENT_EVENT_RATE_LIMIT_PER_MINUTE` 값으로 조정합니다.

관리자 운영 로그 API는 IP별 분당 기본 30회로 제한됩니다. 운영 환경에서 필요하면 `ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE` 값으로 조정하되, 관리자 토큰은 계속 서버 secret으로만 보관합니다.

운영 서버에서 웹 또는 Android WebView가 API를 호출해야 하면 `ALPHAMATE_CORS_ORIGINS`에 허용할 주소를 쉼표로 넣습니다. 예: `https://your-app.example.com,capacitor://localhost`

서버 생존 여부만 확인하는 모니터링에는 `/healthz` 또는 `/api/healthz`를 사용합니다. 이 응답은 `{"ok": true, "service": "alphamate-api"}`처럼 최소 정보만 반환하고, 설정 누락이나 secret 이름은 반환하지 않습니다.

## 9. Android 앱 래퍼, APK, Play Store AAB 빌드 확인

현재 frontend에는 Capacitor 앱 래퍼와 Android 프로젝트 골격이 들어간 상태입니다. 이 PC에서는 프로젝트 안의 `.tools` 폴더에 JDK와 Android SDK command-line tools를 받아 디버그 APK 빌드까지 확인했습니다. `.tools`는 PC 전용 도구라 GitHub에는 올리지 않습니다.

디버그 APK 확인:

1. `frontend/.env`에서 배포용 앱은 `VITE_API_BASE=https://서버주소`, `VITE_ALPHAMATE_ENV=production`, `VITE_ENABLE_DEV_TOOLS=false`로 둡니다.
2. `frontend` 폴더에서 `npm run release:check`를 실행해 localhost API, 개발도구, 테스트 광고 단위가 남아 있지 않은지 확인합니다.
3. 웹 변경사항을 Android 프로젝트에 반영할 때는 `npm run mobile:sync` 또는 `npm run mobile:build`를 실행합니다.
4. Android Studio로 열 때는 `npm run mobile:open:android`를 실행합니다.
5. APK 빌드는 아래처럼 로컬 JDK/SDK 환경변수를 잡은 뒤 `frontend/android`에서 실행합니다.

```powershell
$env:JAVA_HOME='D:\Project\Vibe\StockAnalyze\.tools\jdk\jdk-21.0.11+10'
$env:ANDROID_HOME='D:\Project\Vibe\StockAnalyze\.tools\android-sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
$env:Path="$env:JAVA_HOME\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
cd D:\Project\Vibe\StockAnalyze\frontend\android
.\gradlew.bat assembleDebug
```

정상 빌드 결과물은 아래 위치에 생깁니다.

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

Play Store 제출용 AAB 확인:

1. 실제 upload key keystore 파일을 GitHub 밖의 안전한 폴더에 둡니다.
2. PowerShell에서 아래 값을 실제 값으로 설정합니다. 비밀번호와 keystore 파일은 Git에 올리면 안 됩니다.

```powershell
$env:VITE_APP_NAME='AlphaMate'
$env:ALPHAMATE_ANDROID_APP_NAME='AlphaMate'
$env:ALPHAMATE_ANDROID_VERSION_CODE='1'
$env:ALPHAMATE_ANDROID_VERSION_NAME='1.0.0'
$env:ALPHAMATE_ANDROID_KEYSTORE_FILE='D:\secure\alphamate-upload.jks'
$env:ALPHAMATE_ANDROID_KEYSTORE_PASSWORD='키스토어_비밀번호'
$env:ALPHAMATE_ANDROID_KEY_ALIAS='alphamate-upload'
$env:ALPHAMATE_ANDROID_KEY_PASSWORD='키_비밀번호'
```

3. Play Store에 새 빌드를 올릴 때마다 `ALPHAMATE_ANDROID_VERSION_CODE`는 이전 업로드보다 큰 숫자로 올립니다.
4. `frontend` 폴더에서 `npm run mobile:release:aab`를 실행합니다.

정상 빌드 결과물은 아래 위치에 생깁니다.

```text
frontend/android/app/build/outputs/bundle/release/app-release.aab
```

`frontend/android/local.properties`는 이 PC의 SDK 위치만 적는 파일이라 GitHub에는 올리지 않습니다. 새 PC에서 다시 빌드할 때는 Android Studio를 설치하거나, 같은 방식으로 `.tools`에 JDK/SDK를 다시 준비하면 됩니다.

현재 프로젝트에는 앱 아이콘, 스플래시 이미지, AdMob SDK, Google Play Billing SDK, 환경변수 기반 release signing 연결이 들어가 있습니다. 실제 Google Play Console/AdMob 운영 계정 테스트는 별도 준비가 필요합니다.

Google Play 결제 후 앱 종료, 네트워크 끊김, 서버 일시 장애 때문에 복기권이 바로 반영되지 않으면 매매복기 화면의 `Google Play 구매 복구` 버튼을 누릅니다. 이 버튼은 Android 앱에서만 보이며, 로그인한 사용자 기준으로 Google Play 로컬 영수증을 다시 읽어 서버 검증을 재시도합니다. 서버는 같은 purchase token이 다시 들어와도 중복 지급하지 않고 필요한 consume/acknowledge 재시도만 수행해야 합니다.
## 복기 보관함 확인

1. 매매복기 화면에서 카카오 또는 네이버 개발 계정으로 로그인합니다.
2. `매매 이력 저장`을 켭니다.
3. 종목과 매매 기록을 1건 이상 입력하고 AI 분석 동의 체크 후 `일반 복기` 또는 `심층 복기`를 실행합니다.
4. 상단의 `복기 보관함` 탭을 누릅니다.
5. 저장된 복기 목록이 보이고, 항목을 누르면 당시 차트와 AI 복기 내용이 함께 보이는지 확인합니다.
6. 같은 앱 세션에서 보관함 안의 다른 복기를 눌러도 전면 광고가 반복 진입처럼 과하게 뜨지 않는지 확인합니다.
7. `내 데이터 내보내기` 파일에 `review_history`가 포함되는지 확인합니다.
8. `계정 데이터 삭제` 후 다시 로그인하면 복기 보관함이 비어 있는지 확인합니다.

# Operational Notes

- Client event reports are limited to 60 requests per minute by default. `ALPHAMATE_CLIENT_EVENT_RATE_LIMIT_PER_MINUTE` can tune this value, but the server caps it at 600 per minute.
- Admin operational event APIs are limited to 30 requests per minute by default. `ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE` can tune this value, but the server caps it at 300 per minute.
