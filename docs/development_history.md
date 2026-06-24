# AlphaMate Development History

## 2026-06-21 quick verification script

- Added `release_readiness_report.bat` and `backend/scripts/owner_release_report.py` to print a non-secret Korean launch readiness report from the existing backend readiness checks.
- Added `docs/release_preparation_checklist.md` as a non-developer launch checklist for API keys, server setup, login, Google Play, AdMob, privacy policy, Android builds, operational logs, and final verification.
- Added `docs/project_owner_dashboard.md` as a non-developer project status dashboard that summarizes completed areas, remaining launch work, and recommended next steps.
- Added `scripts/verify_project.ps1` so local project quality checks can be run with one PowerShell command.
- The script runs backend tests, backend compile, frontend release-env tests, Android branding tests, AdMob policy tests, frontend lint, and frontend production build.
- Added `docs/quick_verify.md` with the command and scope.
- Added `verify_project.bat` for Command Prompt and double-click use, and made the PowerShell script stop when any native command returns a non-zero exit code.
- Added the review history interstitial AdMob variable to `frontend/.env.example` so the example matches `npm run release:check`.
- Added tests that keep backend and frontend release-check environment examples aligned with required settings.
- Added a tracked-file secret pattern scan to catch accidental API keys, private keys, service account JSON, and hard-coded password assignments before commit.
- Blocked Google Play Pro subscription token reuse across different user accounts, and added a DB unique index on subscription token hashes as a second guard.
- Added Google Play consumable consume retry tracking and subscription acknowledgement before enabling Pro access.
- Added mobile billing finalization policy tests so Android purchase transactions are not finished in-app after the server has already consumed or acknowledged them.
- Added Google Play purchase recovery from local mobile receipts so a completed Play purchase can be sent to the server again if entitlement delivery was interrupted.
- Added `verify_android_debug.bat` and `scripts/verify_android_debug.ps1` for the heavier Android Capacitor sync plus debug APK build check.
- Added a server-side operational event log for failed API actions, with secret-like fields redacted and `ALPHAMATE_EVENT_LOG_DB_PATH` required for production readiness.
- Added a client-side event reporting endpoint so Android ad and Google Play purchase failures can be stored in the same operational event log without exposing tokens.
- Added protected admin lookup for recent operational events with `ALPHAMATE_ADMIN_TOKEN`, plus release readiness checks for that token.
- Added protected operational event summary counts by level, event type, and path for faster troubleshooting.
- Added protected operational event retention cleanup so old server troubleshooting logs can be purged without touching current events.
- Added optional startup cleanup via `ALPHAMATE_EVENT_LOG_RETENTION_DAYS` so operational logs can follow a retention policy automatically.
- Added a lightweight per-IP rate limit for `/api/client-events` so client-side error reporting cannot flood the operational log database.
- Added a separate per-IP rate limit for protected admin operational log APIs to reduce brute-force and accidental polling risk.
- Required production readiness to reject short `ALPHAMATE_ADMIN_TOKEN` values while still keeping the token value out of diagnostics.
- Added configurable backend CORS origins with Capacitor WebView defaults so mobile app and deployed web clients can call the API without hard-coded localhost-only settings.
- Added lightweight `/healthz` and `/api/healthz` endpoints for deployment health checks without exposing readiness settings or secret names.
- Added operational event detail size limits so oversized client reports cannot bloat the server log database.
- Added `X-Request-ID` response headers and operational event request IDs so API failures can be correlated with user reports without exposing secrets.
- Added global frontend error and unhandled promise rejection reporting so unexpected app-side failures can reach the operational event log once per page load.
- Added admin operational event filtering by `request_id` so support can find a user-reported failure directly from the response header value.
- Added frontend API failure message request IDs so users can copy the support ID shown in an error message and admins can search the matching operational event.
- Added admin operational event filters for `user_id`, `path`, and `status_code` so support can narrow logs by affected account or API endpoint.
- Added admin operational event filters for `event_id`, `created_after`, and `created_before` so support can inspect a single log entry or a specific incident time window.
- Added the same operational event filters to the admin summary endpoint so support can summarize only the affected user, API, request, or time window.
- Added status-code and user aggregation to the admin operational event summary so support can quickly spot repeated quota, payment, rate-limit, or account-specific failures.
- Added `offset` pagination for admin operational event lookup and summary samples so support can inspect older log pages without increasing the page size.
- Added a frontend/Android owner release report that reuses the existing release environment validator without printing API keys, keystore passwords, or other secret values.
- Updated `release_readiness_report.bat` to show both backend readiness and frontend/Android readiness in one double-click report, with UTF-8 output for Korean text.
- Added `.env.release.example` and `frontend/.env.release.example` as production-focused templates so real launch keys can be filled outside Git without mixing in development helper tokens.
- Updated `release_readiness_report.bat` to automatically use `.env.release` and `frontend/.env.release` when those private release files exist locally.
- Added `prepare_release_env_files.bat` and `scripts/create_release_env_files.py` to create private `.env.release` files from templates without overwriting existing secret-filled files.
- Added AI review traffic protection: per-user request limiting, server-wide concurrent AI review limiting, and credit refund when an AI review returns an error.
- Added AI review idempotency keys so retrying the same short-window request does not run duplicate analysis or charge credits twice.
- Added configurable OpenAI timeout and short transient retry settings so temporary 429/5xx failures do not immediately burn a review attempt.
- Added frontend `Retry-After` error messaging so AI review rate-limit or busy-server responses tell users when to try again.
- Added server-side one-time journal and AI review batch size limits so oversized direct API requests cannot trigger excessive chart or AI work.
- Added server-side journal memo length limits so oversized text cannot inflate saved data or AI review payloads.
- Converted invalid journal trade input into clear HTTP 400 responses instead of uncaught server errors.
- Added server-side caps for journal trade and review-history query limits so oversized direct API reads cannot force excessive DB scans.
- Added a separate saved-journal analysis limit so review and chart endpoints analyze a bounded recent trade set instead of always reading 5000 saved rows.
- Added finite-number and non-negative fee/tax validation for journal trades so invalid numeric payloads are rejected before storage or analysis.

## 2026-06-21 frontend code splitting

- `TradingJournal` and `StockChart` are now loaded lazily from `App.jsx`.
- The production build no longer emits Vite's large chunk warning for the main app bundle.
- The app shows a small loading fallback while the journal or chart component is being fetched.

## 2026-06-21 개인정보처리방침 URL 배포 점검

- `/api/app/readiness`와 백엔드 release check가 `ALPHAMATE_PRIVACY_POLICY_URL`을 확인하도록 했다.
- 개인정보처리방침 URL은 공개 HTTPS 주소여야 readiness가 통과한다.
- 매매복기 배포 준비 상태 화면에 `개인정보처리방침` 항목을 추가했다.
- 앱 안의 `개인정보/AI 이용 안내`에서 설정된 개인정보처리방침 URL을 바로 열 수 있게 했다.
- `.env.example`에 복기 보관함 DB 경로와 개인정보처리방침 URL 예시를 보강했다.

## 2026-06-21 AI/개인정보 이용 안내

- `/api/me/data-summary`가 현재 개인정보/AI 동의 안내 버전을 함께 반환하도록 했다.
- 매매복기 계정 관리 영역에 `개인정보/AI 이용 안내` 접이식 안내를 추가했다.
- 안내에는 AI 복기 시 매매 기록, 메모, 차트 요약이 서버와 AI 제공업체로 전송된다는 점과 복기 보관함 저장/내보내기/삭제 범위를 표시했다.

## 2026-06-21 AI 복기 개인정보 동의 이력

- AI 복기 실행 시 로그인 계정에 최신 개인정보/매매 기록 전송 동의 버전과 시각을 저장하도록 했다.
- 계정 관리 영역에 `AI 동의 기록`을 표시해 사용자가 동의 기록 존재 여부를 확인할 수 있게 했다.
- 내 데이터 내보내기에는 기존 `user` 객체를 통해 동의 버전과 시각이 포함된다.

## 2026-06-20 운영 데이터 저장소 배포 검사

- 운영 백엔드 배포 검사에서 `ALPHAMATE_ACCOUNT_DB_PATH`, `ALPHAMATE_JOURNAL_DB_PATH`, `ALPHAMATE_ACCESS_DB_PATH`, `ALPHAMATE_REVIEW_HISTORY_DB_PATH`가 없으면 실패하도록 했다.
- `/api/app/readiness`와 매매복기 화면의 배포 준비 상태에 `데이터 저장소` 항목을 추가했다.
- 복기 보관함 추가 이후 `server_keeps_ai_review_history`가 매매 이력 저장 설정과 맞게 표시되도록 고쳤다.

## 2026-06-20 복기 보관함과 저장된 AI 복기

- 로그인 사용자가 `매매 이력 저장`을 켠 상태에서 일반/심층 AI 복기를 실행하면 결과가 `review_history` SQLite 저장소에 보관되도록 했다.
- 저장 항목에는 복기 유형, 종목, 매매 스냅샷, 최근 매매 스냅샷, 당시 차트 데이터, AI 복기 결과, 이용권 차감 정보를 함께 담는다.
- 매매복기 화면에 `매매복기 / 복기 보관함` 탭을 추가했고, 보관함에서는 저장된 복기 목록, 상세 복기 내용, 당시 차트와 B/S 마커를 다시 볼 수 있다.
- 계정 데이터 내보내기에는 복기 보관함 데이터가 포함되고, 계정 데이터 삭제 시 복기 보관함 데이터도 함께 삭제된다.
- 복기 보관함 첫 진입 시 세션당 1회 전면 광고를 시도한다. 광고 실패나 웹 환경에서는 저장 데이터 접근을 막지 않는다.
- 배포 검사에 `VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID`를 추가해 운영 빌드에서 Google 테스트 전면 광고 단위가 들어가지 않도록 했다.

이 문서는 개발자가 아닌 상태에서도 "무슨 일이 진행됐는지"를 나중에 따라볼 수 있게 남기는 작업 이력이다.

## 2026-06-14

### 매매복기와 AI 복기 저장점

- 매매복기 화면을 앱 안에 추가했다.
- 종목 검색, 수수료/세금 계산, 매매 차트, 매수/매도 표시를 붙였다.
- AI 복기를 `일반 복기`와 `심층 복기`로 나눴다.
- Pro, 광고 보상, 일반 복기 이용권, 심층 복기 이용권 정책을 정리했다.
- OpenAI API Key는 앱에 넣지 않고 서버에서만 쓰는 방향으로 정했다.

관련 커밋:

- `3e3f296` Add trading journal AI review access model
- `bb9d899` Document login and server DB design

### 로그인과 서버 DB 방향

- 카카오 로그인과 네이버 로그인을 모두 지원하는 방향으로 설계했다.
- 카카오/네이버는 사용자를 확인하는 로그인 수단이고, 복기권과 매매 이력은 AlphaMate 서버 DB에서 관리하기로 했다.
- 같은 사람이 카카오와 네이버를 모두 쓰는 경우에는 자동 병합하지 않고, 사용자가 직접 계정 연결을 확인하는 방식으로 정했다.
- 매매 이력 저장은 기본 꺼짐으로 두고, 사용자가 저장 기능을 켰을 때만 서버에 보관하는 방향으로 정했다.

관련 문서:

- `docs/superpowers/specs/2026-06-14-login-server-db-design.md`

### 개발용 이용권 DB 저장

- 기존 개발용 복기권/사용량은 서버 메모리에만 있어서 백엔드를 껐다 켜면 초기화됐다.
- 외부 카카오/네이버 키 없이도 진행 가능한 작업으로, 개발용 이용권 지갑을 SQLite DB에 저장하도록 바꿨다.
- 이제 개발 환경에서는 `backend/data/access.sqlite3`에 이용권과 사용량이 저장된다.
- 운영 배포 때는 이 구조를 PostgreSQL 같은 서버 DB로 옮기는 것이 다음 단계다.

확인한 테스트:

- 심층 복기 이용권 5회 구매
- 심층 복기 1회 사용
- 서버 코드 재시작 상황을 흉내낸 뒤 남은 이용권이 4회로 유지되는지 확인

### 서버 DB 기반 로그인/세션 뼈대

- 카카오/네이버 실제 키 없이도 개발을 이어갈 수 있도록 개발용 로그인 API를 만들었다.
- 개발용 로그인도 실제 구조와 비슷하게 `(provider, provider_user_id)`를 내부 사용자 ID에 연결한다.
- `provider`는 `kakao` 또는 `naver`를 받을 수 있다.
- 로그인하면 AlphaMate 자체 세션 토큰이 발급되고, `/api/me`로 현재 사용자를 확인할 수 있다.
- `/api/auth/logout`으로 세션을 폐기할 수 있다.
- 기존 복기권 시스템이 이제 `dev-token`뿐 아니라 AlphaMate 세션 토큰도 인식한다.
- 그래서 카카오 개발 사용자 A와 네이버 개발 사용자 B의 복기권/사용량이 서로 분리된다.

추가된 개발용 API:

- `POST /api/auth/dev-login`
- `GET /api/me`
- `POST /api/auth/logout`

저장 위치:

- `backend/data/accounts.sqlite3`: 사용자, 로그인 제공자 연결, 세션
- `backend/data/access.sqlite3`: 일반/심층 복기권과 사용량

아직 남은 일:

- 실제 카카오 개발자 콘솔 앱 키와 네이버 개발자 센터 Client ID/Secret을 받아서 토큰 검증을 붙여야 한다.
- 운영 배포 전에는 SQLite 대신 서버용 PostgreSQL 같은 DB로 옮기는 것이 좋다.

### 매매복기 화면의 개발용 로그인 확인 UI

- 매매복기 화면에 `로그인` 패널을 추가했다.
- `카카오`, `네이버` 버튼으로 개발용 로그인을 직접 테스트할 수 있다.
- 로그인하면 서버가 발급한 AlphaMate 세션 토큰을 브라우저에 저장하고, 이후 이용권 조회/구매/AI 복기 요청에 그 토큰을 사용한다.
- `카카오` 계정에서 충전한 이용권은 `네이버` 계정으로 바꿨을 때 보이지 않아야 한다.
- 실제 배포용 카카오/네이버 로그인 버튼은 나중에 각 개발자 콘솔 키를 받은 뒤 같은 자리에 연결한다.

### 사용자별 매매 이력 저장 옵션

- `매매 이력 저장` 체크박스를 로그인 패널에 추가했다.
- 저장 기능은 기본 꺼짐이고, 사용자가 켜야 서버에 매매 기록을 저장한다.
- 저장 기능을 켠 로그인 사용자는 매매 기록을 서버 DB에 저장하고 새로고침 후에도 다시 볼 수 있다.
- 카카오 개발 사용자와 네이버 개발 사용자의 저장 매매 기록은 서로 분리된다.
- 저장 기능을 끈 상태에서는 기존처럼 현재 화면에서만 1회성 복기를 한다.
- 저장 기능이 켜진 상태에서 `저장 기록 전체 삭제`를 누르면 현재 로그인 계정의 저장 매매 기록만 삭제된다.

확인한 테스트:

- 카카오 개발 사용자로 매매 기록 저장
- 네이버 개발 사용자로 조회했을 때 카카오 기록이 보이지 않음
- 다시 카카오 개발 사용자로 조회하면 저장 기록이 보임
- 카카오 개발 사용자 기록 전체 삭제 후 네이버 개발 사용자 기록은 유지됨

### 계정/데이터 관리 영역

- 매매복기 화면의 `로그인` 패널을 `계정/데이터 관리` 패널로 정리했다.
- 현재 로그인 상태, 연결 로그인, 저장된 매매 기록 수, AI 분석 기록 서버 저장 여부를 한곳에서 볼 수 있게 했다.
- `GET /api/me/data-summary` API를 추가해 현재 로그인 계정의 저장 데이터 요약만 내려주도록 했다.
- AI 복기 결과는 현재 정책상 서버에 이력으로 저장하지 않는다는 상태를 화면에 표시한다.
- 전체 삭제 버튼은 계속 현재 로그인 계정의 저장 매매 기록에만 적용된다.

확인한 테스트:

- 카카오 개발 사용자와 네이버 개발 사용자의 저장 기록을 각각 만든 뒤 카카오 요약 API가 카카오 기록 1건만 반환하는지 확인
- `/api/me/data-summary` 경로가 FastAPI 라우트에 등록되는지 확인

### 운영/개발 환경 분리 안전장치

- 운영 모드에서 개발용 로그인 API가 동작하지 않도록 막았다.
- 운영 모드에서 개발용 복기권 구매 API가 동작하지 않도록 막았다.
- 운영 모드에서는 `dev-token`, `dev-ad-reward`, `dev-pro-entitlement` 같은 개발용 토큰이 권한으로 인정되지 않는다.
- frontend production build 또는 `VITE_ALPHAMATE_ENV=production`에서는 개발용 로그인 버튼과 개발용 구매 버튼을 숨긴다.
- `.env.example`과 `frontend/.env.example`을 추가해 실제 키를 GitHub에 올리지 않고 어떤 환경변수가 필요한지 확인할 수 있게 했다.

확인한 테스트:

- `ALPHAMATE_ENV=production`에서 개발용 로그인 요청이 403으로 거부되는지 확인
- `ALPHAMATE_ENV=production`에서 개발용 복기권 구매 요청이 403으로 거부되는지 확인
- `ALPHAMATE_ENV=production`에서 `dev-token` 인증이 401로 거부되는지 확인

### 카카오/네이버 실제 로그인 서버 API 뼈대

- `POST /api/auth/login/kakao`와 `POST /api/auth/login/naver`를 추가했다.
- 앱 SDK나 웹 OAuth 흐름에서 받은 provider access token을 서버로 보내면, 서버가 provider 프로필 API로 사용자 ID를 확인한 뒤 AlphaMate 세션을 발급하는 구조다.
- 카카오/네이버 이메일은 원문 저장하지 않고 hash로만 저장하도록 계정 저장 로직을 정리했다.
- frontend production 화면에는 카카오/네이버 로그인 버튼 자리를 표시하되, 실제 모바일 SDK 연결 전까지는 비활성 상태로 둔다.

확인한 테스트:

- 카카오 access token 검증 응답을 흉내 내 AlphaMate 세션이 발급되는지 확인
- 네이버 access token 검증 응답을 흉내 내 AlphaMate 세션이 발급되는지 확인
- access token이 비어 있으면 400으로 거부되는지 확인
- `/api/auth/login/kakao`, `/api/auth/login/naver` 경로가 FastAPI 라우트에 등록되는지 확인

### OAuth authorization code 교환 API

- `POST /api/auth/login/kakao/code`와 `POST /api/auth/login/naver/code`를 추가했다.
- 앱이나 웹 로그인 흐름에서 받은 authorization code를 서버가 provider token endpoint로 보내 access token으로 교환한다.
- 교환된 access token으로 기존 provider 프로필 검증을 수행하고 AlphaMate 세션을 발급한다.
- 카카오/네이버 Client ID, Secret, Redirect URI는 `.env.example`에 placeholder로만 남기고 실제 값은 GitHub에 올리지 않는다.

확인한 테스트:

- 카카오 authorization code 교환 요청에 client id, secret, redirect uri, code가 올바르게 들어가는지 확인
- 네이버 authorization code 교환 요청에 client id, secret, redirect uri, code, state가 올바르게 들어가는지 확인
- provider 설정값이 없으면 503으로 거부되는지 확인
- `/api/auth/login/kakao/code`, `/api/auth/login/naver/code` 경로가 FastAPI 라우트에 등록되는지 확인

### 프론트 OAuth 로그인 시작/콜백 연결

- production 화면에서 카카오/네이버 로그인 버튼이 설정값이 있을 때 활성화되도록 바꿨다.
- 버튼을 누르면 provider 로그인 페이지로 이동할 authorization URL을 만든다.
- 로그인 시작 전에 state 값을 브라우저에 저장하고, callback으로 돌아온 state와 비교한다.
- callback URL에 `code`와 `state`가 있으면 서버의 `/api/auth/login/{provider}/code`로 보내 AlphaMate 세션을 받는다.
- `frontend/.env.example`에 공개 가능한 OAuth client 값과 redirect URI 예시를 추가했다.

아직 필요한 값:

- 카카오 개발자 콘솔의 REST API Key
- 네이버 개발자 센터의 Client ID
- 각 provider에 등록한 redirect URI
- backend 서버의 카카오/네이버 Secret 값

### OAuth 설정 진단과 테스트 가이드 정리

- `GET /api/auth/oauth-config`를 추가해 서버의 카카오/네이버 로그인 설정 준비 상태를 확인할 수 있게 했다.
- 이 API는 실제 secret 값을 노출하지 않고, 어떤 환경변수가 빠졌는지만 알려준다.
- 매매복기 화면은 배포 모드에서 실제 로그인 전 필요한 프론트 키와 서버 설정 누락 상태를 안내한다.
- 깨져 있던 `docs/manual_test_guide.md`를 한국어 UTF-8 문서로 다시 작성했다.

### Google Play 결제 준비 골격

- `GET /api/journal/products`가 복기권 상품, Pro 구독 상품, Google Play 설정 준비 상태를 함께 반환하도록 바꿨다.
- Google Play 상품 ID는 `.env`에서 바꿀 수 있고, 기본값은 내부 상품 ID와 같게 뒀다.
- `POST /api/journal/google-play-purchase`를 추가했다.
- 아직 Google Play Developer API 검증/consume/acknowledge 구현 전이므로, 이 endpoint는 실제 복기권을 지급하지 않고 501로 막는다.
- 서버 설정이 빠진 경우에는 503으로 막아, 가짜 결제가 복기권으로 바뀌지 않게 했다.

### Google Play 소모성 복기권 검증

- `POST /api/journal/google-play-purchase`가 Google Play Developer API로 소모성 상품 purchase token을 검증한 뒤 복기권을 지급하도록 바꿨다.
- 같은 purchase token은 SHA-256 해시로 DB에 기록해 한 번만 지급되게 했다.
- 일반/심층 복기권 같은 소모성 상품은 검증 성공 후 지급하고, Pro 구독 검증은 별도 월 구독 상태 저장 구조가 필요해 다음 단계로 남겼다.
- 실제 서비스 계정 JSON 값은 API 응답이나 DB에 저장하지 않고, 구매 토큰 원문도 저장하지 않는다.

### Google Play Pro 구독 검증

- `POST /api/journal/google-play-purchase`가 Pro 월 구독 상품도 처리하도록 확장했다.
- Google Play `purchases.subscriptionsv2.get` 응답의 구독 상태, 상품 ID, 만료 시간을 확인해 활성 구독일 때만 Pro 플랜으로 저장한다.
- Pro 구독 토큰 원문은 저장하지 않고 SHA-256 해시만 저장한다.
- 활성 Pro 구독 사용자는 별도 개발용 entitlement token 없이 월 일반 복기 150회, 심층 복기 5회 제공량을 우선 사용한다.
- 같은 구독 토큰이 만료/비활성 상태로 다시 검증되면 그 상태도 저장해 기존 Pro 권한이 계속 유지되지 않게 했다.

### Google Play RTDN 알림 수신

- `POST /api/journal/google-play-rtdn`를 추가해 Google Play Real-time Developer Notifications Pub/Sub push 메시지를 받을 수 있게 했다.
- endpoint는 `X-AlphaMate-RTDN-Token` 헤더가 `.env`의 `GOOGLE_PLAY_RTDN_SHARED_TOKEN`과 일치할 때만 처리한다.
- `.env`에 `GOOGLE_PLAY_RTDN_OIDC_AUDIENCE` 또는 `GOOGLE_PLAY_RTDN_OIDC_EMAIL`을 설정하면 Pub/Sub push의 `Authorization: Bearer <JWT>`도 검증한다.
- subscription notification을 받으면 알림 내용만 믿지 않고 Google Play 구독 API를 다시 호출해 저장된 Pro 상태를 갱신한다.
- 모르는 purchase token은 사용자와 연결할 수 없으므로 무시하고, 이미 저장된 구독 토큰 해시와 매칭되는 경우만 갱신한다.

### 앱 표시 이름 설정화

- 화면 왼쪽 상단의 앱 이름과 브라우저 탭 제목을 `VITE_APP_NAME`으로 설정할 수 있게 했다.
- 기본값은 기존 이름인 `AlphaMate`로 유지했다.
- 내부 저장소 키(`alphamate.*`)는 기존 사용자 데이터와 충돌하지 않도록 아직 바꾸지 않았다.

### 실제 로그인 준비 상태 카드

- 매매복기 계정 영역에 카카오/네이버 실제 로그인 준비 상태 카드를 추가했다.
- 개발 모드에서도 프론트 키, 서버 설정, Redirect URI를 확인할 수 있게 했다.
- 실제 로그인에 필요한 환경변수가 빠졌을 때 어떤 값을 채워야 하는지 화면에 표시한다.

### 로그인 버튼 아이콘

- 카카오/네이버 로그인 버튼에 provider 구분 아이콘 배지를 추가했다.
- 외부 이미지 파일 없이 CSS 기반 배지로 구현해 앱 빌드와 라이선스 부담을 줄였다.
- 나중에 공식 브랜드 자산을 적용해야 하면 이 배지 컴포넌트만 교체하면 된다.

### 로그인 공식 로고 자산

- 카카오/네이버 로그인 버튼의 임시 문자 배지를 SVG 로고 자산으로 교체했다.
- 카카오는 노란 버튼에 검은 말풍선 심볼, 네이버는 초록 버튼에 흰색 N 심볼로 로그인 제공자를 바로 구분할 수 있게 했다.
- 로고 자산은 `frontend/src/assets`에 분리해 두어 나중에 공식 가이드 변경 시 파일만 교체하면 된다.

### 불필요 템플릿 자산 정리

- Vite/React 기본 샘플 로고 SVG는 현재 앱에서 쓰지 않아 제거했다.
- 로그인 로고 자산만 실제 사용되는 프론트 자산으로 남겼다.

## 2026-06-18

### AdMob 보상형 광고 SSV 검증

- `GET /api/journal/admob-ssv`를 추가해 AdMob 보상형 광고 서버 측 검증 콜백을 받을 수 있게 했다.
- 서버는 AdMob 공개키로 콜백 서명을 검증하고, `transaction_id`를 기본키로 저장해 같은 광고 보상이 중복 지급되지 않게 했다.
- 검증된 광고 보상은 `admob_reward_events`에 `pending` 상태로 저장되고, 일반 복기 실행 시 1회 사용되면 `consumed`로 바뀐다.
- `ADMOB_REWARDED_AD_UNIT_ID`를 설정하면 서버가 의도한 광고 단위에서 온 보상만 인정한다.
- 개발용 `dev-ad-reward`는 개발 모드에서만 유지하고, 운영에서는 AdMob SSV 기록이 광고 보상의 기준이 되도록 했다.

### 광고 정책 설정값 노출

- `GET /api/journal/products` 응답에 AdMob 준비 상태와 광고 보상 정책을 추가했다.
- `ALPHAMATE_ADS_PER_ADVANCED_TICKET`로 심층 복기권 지급에 필요한 광고 시청 횟수를 서버에서 바꿀 수 있게 했다.
- `ALPHAMATE_FORCE_REWARDED_AD_CHAIN` 설정값을 추가했지만, 기본값은 여러 광고를 연속 강제하지 않는 `false`로 유지했다.

### Android 앱 래퍼 준비

- 기존 Vite/React frontend에 Capacitor v8 설정을 추가했다.
- `capacitor.config.json`은 앱 ID를 `com.mariocrat.stockanalyze`, 앱 표시 이름을 `AlphaMate`, 웹 빌드 폴더를 `dist`로 둔다.
- `npm run mobile:add:android`, `npm run mobile:sync`, `npm run mobile:open:android`, `npm run mobile:build` 스크립트를 추가했다.
- `frontend/android` 네이티브 프로젝트 골격을 생성하고 `npm run mobile:build`로 웹 자산 동기화까지 확인했다.
- 프로젝트 안의 `.tools` 폴더에 로컬 JDK와 Android SDK command-line tools를 준비했다. 이 도구 폴더는 PC 전용이라 `.gitignore`에 추가해 GitHub에는 올리지 않는다.
- Windows 경로에 한글이 포함되어 Android Gradle 플러그인의 경로 검사에 걸렸기 때문에 `frontend/android/gradle.properties`에 `android.overridePathCheck=true`를 추가했다.
- `frontend/android/local.properties`에는 이 PC의 Android SDK 위치를 적어 빌드가 가능하게 했지만, 이 파일은 원래 Android 프로젝트에서 로컬 전용으로 무시된다.
- `frontend/android`에서 `gradlew.bat assembleDebug`를 실행해 `frontend/android/app/build/outputs/apk/debug/app-debug.apk` 생성까지 확인했다.
- Play Store 서명, 앱 아이콘, 스플래시 이미지, AdMob SDK, Google Play Billing SDK 연결은 다음 단계로 남겼다.

### Android 앱 아이콘/스플래시 교체

- Capacitor 기본 앱 아이콘을 차트/상승 흐름을 표현하는 AlphaMate 전용 아이콘으로 교체했다.
- 앱 이름을 나중에 바꿀 수 있도록 아이콘과 스플래시에는 텍스트를 넣지 않고 심볼 중심으로 구성했다.
- Android 해상도별 launcher icon, round icon, foreground icon, portrait/landscape splash 이미지를 모두 새로 생성했다.
- `ic_launcher_background` 색상을 앱의 어두운 UI 톤에 맞춰 변경했다.
- `npm run mobile:build`와 `gradlew.bat assembleDebug`로 웹 자산 동기화와 Android 디버그 APK 빌드를 다시 확인했다.

### Android AdMob 보상형 광고 연결

- Capacitor 8과 맞는 `@capacitor-community/admob`을 추가했다.
- Android manifest에 AdMob application ID 메타데이터를 연결하고, 개발 빌드용 Google 테스트 앱 ID를 문자열 리소스로 넣었다.
- `frontend/src/mobile/admob.js`를 추가해 웹에서는 비활성, Android 앱에서는 보상형 광고를 실행하도록 분리했다.
- 보상형 광고 실행 시 로그인된 사용자 ID를 AdMob SSV `userId`로 넘겨 서버의 `/api/journal/admob-ssv` 보상 검증과 이어지게 했다.
- 매매복기 화면에 `광고 보고 일반 복기` 버튼과 모바일 광고 SDK 상태 표시를 추가했다.
- 테스트 광고는 SSV 콜백이 오지 않으므로, 실제 보상 지급 검증은 운영 AdMob 앱/광고 단위와 SSV 콜백 URL을 설정한 뒤 진행해야 한다.

### Android Google Play Billing SDK 탑재

- Capacitor 8을 지원하는 `capacitor-plugin-cdv-purchase`를 추가했다.
- 처음에는 Cordova 패키지명인 `cordova-plugin-purchase`를 확인했지만, README가 Capacitor 전용 설치 패키지로 `capacitor-plugin-cdv-purchase`를 안내해 전용 패키지로 교체했다.
- `npm run mobile:build`에서 AdMob과 Billing 플러그인 2개가 모두 Android 플러그인으로 인식되는 것을 확인했다.
- `gradlew.bat assembleDebug`로 Google Play Billing SDK가 포함된 Android 디버그 APK 빌드까지 확인했다.
- 실제 구매 버튼 연결은 Google Play Console 상품 ID, 라이선스 테스트 계정, 서버의 Google Play Developer API 설정이 준비된 뒤 진행해야 한다.

### 기존 로고 기반 Android 아이콘/스플래시 반영

- 사용자가 제공한 기존 `AlphaMate` 다크 로고를 `frontend/src/assets/app-logo-dark.png`에 보관했다.
- 런처 아이콘은 작은 화면에서도 읽히도록 원본 로고의 심볼 영역만 추출해 Android 해상도별 아이콘으로 다시 생성했다.
- 스플래시는 브랜드명이 보이도록 전체 로고를 투명 배경 처리해 portrait/landscape 해상도별 이미지에 반영했다.

### Google Play 구매 버튼 연결

- `frontend/src/mobile/billing.js`를 추가해 Google Play Billing 초기화, 상품 등록, 구매 token 추출을 매매복기 화면과 분리했다.
- 웹 번들이 무거워지지 않도록 Billing 플러그인은 모바일 구매가 필요할 때 동적 import로 로딩한다.
- 이용권 구매 버튼은 웹 개발 모드에서는 기존 개발용 충전 흐름을 유지하고, Android 앱에서는 Google Play Billing 구매 흐름을 실행한다.
- 구매 성공 시 Google Play purchase token을 서버의 `POST /api/journal/google-play-purchase`로 보내 서버 검증 후 이용권에 반영하도록 연결했다.
- 실제 결제 완료 검증은 Google Play Console 상품 ID, 라이선스 테스트 계정, 운영 서버의 Google Play Developer API 설정이 준비된 뒤 진행해야 한다.

### 배포 준비 상태 점검

- `GET /api/app/readiness`를 추가해 AI Key, 카카오/네이버 로그인, Google Play 결제, AdMob 보상 광고의 서버 설정 준비 상태를 한 번에 확인할 수 있게 했다.
- readiness 응답은 `ready` 여부와 누락된 환경변수 이름만 반환하고, API Key, client secret, Google 서비스 계정 JSON 원문은 반환하지 않는다.
- 매매복기 이용권 영역에 `배포 준비 상태` 표시를 추가해 웹/Android 환경별로 설정 필요 항목을 바로 볼 수 있게 했다.

### 배포 빌드 환경 안전 검사

- `frontend/scripts/validate-release-env.js`를 추가해 Android 배포 빌드 전에 개발용 설정이 남아 있는지 검사한다.
- `npm run release:check`는 `VITE_ALPHAMATE_ENV=production`, `VITE_ENABLE_DEV_TOOLS=false`, HTTPS API 주소, 운영 AdMob 보상형 광고 단위, Android package name을 확인한다.
- 현재 개발용 설정에서는 의도적으로 실패하고, 배포용 환경변수를 넣으면 통과하도록 테스트를 추가했다.

### Android release signing 준비

- Android release build가 `ALPHAMATE_ANDROID_KEYSTORE_FILE`, `ALPHAMATE_ANDROID_KEYSTORE_PASSWORD`, `ALPHAMATE_ANDROID_KEY_ALIAS`, `ALPHAMATE_ANDROID_KEY_PASSWORD` 환경변수로 서명 정보를 읽도록 연결했다.
- 실제 keystore 파일과 비밀번호는 Git에 저장하지 않도록 `.gitignore`에 `*.jks`, `*.keystore`를 추가했다.
- `npm run mobile:release:aab`를 추가해 배포 환경 검사, 모바일 빌드, Play Store 제출용 `app-release.aab` 생성을 한 번에 실행할 수 있게 했다.

### Android 앱 버전 관리

- Android `versionCode`, `versionName`이 `ALPHAMATE_ANDROID_VERSION_CODE`, `ALPHAMATE_ANDROID_VERSION_NAME` 환경변수를 읽도록 연결했다.
- `npm run release:check`에서 versionCode가 양의 정수인지, versionName이 `1.0.0` 같은 형식인지 검사한다.
- Play Store 업로드마다 `ALPHAMATE_ANDROID_VERSION_CODE`를 이전 업로드보다 큰 숫자로 올려야 한다는 안내를 문서에 추가했다.

### 앱 표시 이름 중앙화

- Android 런처 이름과 Activity title을 `ALPHAMATE_ANDROID_APP_NAME` 또는 `VITE_APP_NAME`으로 주입하도록 바꿨다.
- `strings.xml`에 고정된 `AlphaMate` 앱 이름을 제거해 나중에 브랜드명을 바꿀 때 Gradle/env 설정만 수정하면 되게 했다.
- `index.html`의 초기 브라우저 title도 `VITE_APP_NAME`을 쓰도록 바꿨다.
- `npm run test:android-branding`을 추가해 Android 쪽 앱 이름이 다시 하드코딩되지 않도록 검사한다.

### AdMob 운영 광고 단위 런타임 가드

- `frontend/src/mobile/admobPolicy.js`를 추가해 AdMob 보상형 광고 정책 판단을 분리했다.
- 운영 모드에서 Google 테스트 보상형 광고 단위가 남아 있으면 광고 실행을 막고, 런타임 상태도 `available: false`로 표시한다.
- 매매복기 화면의 배포 준비 상태도 `mobileAdStatus.available`을 기준으로 판단해 테스트 광고 단위가 운영 앱에서 준비 완료로 보이지 않게 했다.
- `npm run test:mobile-admob`을 추가해 운영 모드 테스트 광고 차단, 운영 실광고 허용, 개발 모드 테스트 광고 허용을 확인한다.

### Google Play 상품 ID 배포 준비 검사

- `ALPHAMATE_ENV=production`에서는 Google Play 상품 ID 매핑 환경변수가 모두 설정되어야 `google_play.ready`가 true가 되도록 바꿨다.
- 필요한 상품 ID 환경변수는 `GOOGLE_PLAY_BASIC_REVIEW_30_ID`, `GOOGLE_PLAY_BASIC_REVIEW_100_ID`, `GOOGLE_PLAY_ADVANCED_REVIEW_5_ID`, `GOOGLE_PLAY_ADVANCED_REVIEW_10_ID`, `GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID`, `GOOGLE_PLAY_PRO_MONTHLY_ID`다.
- 개발 모드에서는 기존처럼 내부 상품 ID 기본값을 쓸 수 있게 유지했다.
- `/api/app/readiness`와 `/api/journal/products` 응답에서 누락된 상품 ID 설정을 확인할 수 있다.

### 백엔드 배포 전 검사 명령

- `backend/core/release_check.py`를 추가해 서버 운영 배포에 필요한 환경변수를 한 번에 검사한다.
- `backend/scripts/validate_release_env.py`를 실행하면 `ALPHAMATE_ENV=production`, AI Key, 카카오/네이버 로그인, Google Play 결제, AdMob 보상형 광고 설정 누락을 확인한다.
- 실패 시에는 필요한 환경변수 이름만 출력하고, API Key나 Google 서비스 계정 JSON 원문은 출력하지 않는다.
- `tests/test_backend_release_check.py`를 추가해 설정 누락 실패와 전체 설정 성공 케이스를 확인한다.
- `backend/core/env.py`를 추가해 서버 설정 읽기 방식을 공통화하고, `ALPHAMATE_ENV_FILE`로 별도 env 파일을 지정할 수 있게 했다.

### Google Play 서비스 계정 설정 검증 강화

- Google Play readiness가 서비스 계정 설정의 존재 여부만 보지 않고 JSON 파싱, 필수 필드, private key 형식을 함께 검사하도록 보강했다.
- 서비스 계정 JSON이나 파일이 깨져 있으면 `google_play.ready`가 false가 되고, 필요한 설정 이름만 `missing_server_settings`에 표시된다.
- Google 인증 생성/갱신 실패가 raw 예외로 터지지 않도록 `503 Google Play service account credentials are invalid.`로 감싸도록 했다.

### 계정 데이터 삭제와 내보내기

- `DELETE /api/me/account-data`를 추가해 현재 로그인 계정의 저장 매매 기록, 복기권/구독 상태, 광고 보상 기록, 로그인 세션, 로그인 연결 정보를 함께 정리하도록 했다.
- 매매복기 화면의 계정 관리 영역에 `계정 데이터 삭제` 버튼을 추가했고, 삭제 후 로컬 로그인 상태와 복기 화면 상태를 초기화한다.
- `GET /api/me/export-data`를 추가해 현재 로그인 계정의 사용자 정보, 저장 매매 기록, 이용권 현황을 JSON으로 내려받을 수 있게 했다.
- 내보내기 응답에는 세션 토큰을 포함하지 않도록 테스트로 확인한다.
- `tests/test_account_store.py`, `tests/test_me_data_routes.py`에 계정 삭제와 내보내기 회귀 테스트를 추가했다.
