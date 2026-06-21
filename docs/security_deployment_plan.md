# AlphaMate 보안/배포 설계 메모

## 권장 결론

- 모바일 앱에는 OpenAI/Gemini API Key를 절대 넣지 않는다.
- 앱은 광고 시청 완료와 매매복기 데이터를 서버에 보내고, 서버가 AI API를 호출한다.
- 매매복기 원장은 기본적으로 서버 DB에 저장하지 않는다.
- 사용자가 저장 기능을 명시적으로 켜기 전까지는 1회성 분석으로 처리한다.
- 카카오/네이버 같은 간편 인증은 광고 보상 남용 방지, 사용량 제한, 사용자별 비용 통제를 위해 도입한다.

## 권장 흐름

1. 앱에서 사용자가 매매 기록을 입력한다.
2. 사용자가 AI 분석 버튼을 누른다.
3. 앱에서 보상형 광고를 표시한다.
4. 앱은 광고 완료 토큰, 사용자 로그인 토큰, 매매 기록을 서버로 보낸다.
5. 서버는 사용자 인증, 광고 보상 검증, 이용권 잔여량, 요청 제한, 비용 한도를 확인한다.
6. 서버가 OpenAI/Gemini API를 호출한다.
7. 서버는 분석 결과만 앱에 반환하고 매매 원장은 저장하지 않는다.

## 현재 코드에 추가한 배포형 1회성 API

- `POST /api/journal/review-once`
- `POST /api/journal/ai-review-once`
- `POST /api/journal/charts-once`

위 API는 요청 본문으로 받은 매매 기록만 분석하고 SQLite에 저장하지 않는다.

## 아직 필요한 배포 보안 작업

- 사용자 인증: 카카오 로그인, 네이버 로그인, 또는 OIDC 기반 간편 로그인
- 계정 매핑: `(provider, provider_user_id)`를 내부 사용자 ID에 연결하고, 카카오/네이버 계정 연결은 사용자 확인 후 처리
- 사용자별 권한 저장소: 이용권, Pro 상태, 광고 보상, 일/월 사용량을 서버 DB에 저장
- 광고 보상 검증: AdMob 서버 측 검증 또는 서버 자체 보상 검증
- 사용량 제한: 사용자별, 기기별, IP별 일/월 제한
- 비용 제한: OpenAI/Gemini 월 예산과 사용자별 호출 수 제한
- HTTPS 강제
- 서버 비밀값 관리: `.env`가 아닌 Cloud Secret Manager류 사용 권장
- 앱 정상성 검증: Play Integrity API 검토
- 서버 로그 마스킹: 매매 기록, API Key, Authorization 헤더 로그 금지
- 데이터 삭제 정책: 기본은 1회성 분석 후 원문 즉시 폐기, 매매 이력 저장은 사용자 동의 기반으로 분리

## 개인정보처리방침 초안 문구

> AlphaMate는 사용자가 입력한 매매 기록, 종목명, 체결 가격, 수량, 메모를 매매복기 및 AI 분석 제공 목적으로 처리합니다.
> AI 분석을 요청하는 경우 해당 입력 데이터와 차트 지표가 AI 분석 제공업체(OpenAI 또는 Google 등)에 전송될 수 있습니다.
> 회사는 기본적으로 매매복기 원문을 서버에 저장하지 않으며, 분석 요청 처리 후 즉시 폐기합니다.
> 사용자가 매매 이력 저장 기능을 켜는 경우, 해당 기록은 사용자 계정별로 저장되며 사용자는 앱에서 열람, 수정, 내보내기, 삭제할 수 있습니다.
> 다만 서비스 안정성, 부정 이용 방지, 광고 보상 검증, 오류 분석을 위해 최소한의 접속 기록, 인증 식별자, 요청 시각, 처리 결과 상태를 일정 기간 보관할 수 있습니다.
> 사용자는 AI 분석 요청 전 개인정보 및 민감한 투자 메모가 외부 AI 서비스로 전송될 수 있음을 확인하고 동의해야 합니다.

## Google Play Data safety 작성 방향

- AI 분석 요청 시 매매 데이터가 기기 밖 서버로 전송되므로 데이터 수집/처리에 해당한다.
- Google Play는 앱이 수집, 공유, 보호하는 사용자 데이터와 SDK가 처리하는 데이터까지 개발자가 정확히 신고해야 한다.
- 일시 처리(ephemeral processing)라도 기기 밖으로 전송되면 Data safety form에서 검토 대상이다.
- AdMob SDK 사용으로 광고 식별자 및 광고 관련 데이터 처리가 발생할 수 있으므로 AdMob/Google SDK 안내에 맞춰 신고해야 한다.

## 주의

이 문서는 개발 설계용 초안이며 법률 자문이 아니다. 실제 Play Store 배포 전 개인정보보호법, 전자상거래/광고 정책, Google Play 정책 기준으로 최종 법률 검토가 필요하다.

## 2026-06-13 개발용 AI 접근 관문

현재 코드는 배포 구조를 미리 맞추기 위해 `POST /api/journal/ai-review-once` 앞에 개발용 접근 관문과 개발용 이용권 지갑을 둔다.

- 앱은 AI 분석 요청 전에 개인정보/매매 기록 전송 동의를 받아야 한다.
- 앱은 `Authorization: Bearer <token>` 헤더를 보낸다.
- 앱은 요청 본문에 `ad_reward_token`과 `privacy_consent: true`를 함께 보낸다.
- 서버는 인증 토큰, 광고 보상 토큰, 동의 여부, 이용권 잔여량을 확인한 뒤 OpenAI API를 호출한다.
- 기본 개발값은 `dev-token`, `dev-ad-reward`이며, `ALPHAMATE_ENV=production`이면 개발 토큰은 비활성화된다.
- 현재 개발용 지갑은 메모리 기반이라 서버 재시작 시 초기화된다. 운영 배포에서는 DB 또는 Redis로 교체해야 한다.

개발 환경 변수:

```env
OPENAI_API_KEY=실제_OpenAI_Key
OPENAI_BASIC_REVIEW_MODEL=gpt-5.4-mini
OPENAI_ADVANCED_REVIEW_MODEL=gpt-5.5
ALPHAMATE_ENV=development
ALPHAMATE_DEV_AUTH_TOKEN=dev-token
ALPHAMATE_DEV_AD_REWARD_TOKEN=dev-ad-reward
ALPHAMATE_DEV_PRO_ENTITLEMENT_TOKEN=dev-pro-entitlement
ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC=false
```

프론트 개발 환경 변수:

```env
VITE_DEV_AUTH_TOKEN=dev-token
VITE_DEV_AD_REWARD_TOKEN=dev-ad-reward
VITE_DEV_ACCESS_PLAN=free
VITE_DEV_PRO_ENTITLEMENT_TOKEN=dev-pro-entitlement
```

운영 배포 때 교체해야 하는 부분:

- `dev-token` 인증은 카카오/네이버 로그인 또는 OIDC 토큰 검증으로 교체한다.
- `dev-ad-reward` 검증은 AdMob 보상형 광고 서버 측 검증으로 교체한다.
- `dev-pro-entitlement`와 개발용 구매 처리는 Google Play Billing 서버 검증으로 교체한다.
- 현재 메모리 기반 이용권/사용량 관리는 DB 또는 Redis로 교체한다.
- OpenAI API Key는 앱이나 프론트가 아니라 서버 환경변수/Secret Manager에만 둔다.
- 서버 로그에는 매매 기록, 메모, Authorization 헤더, AI Key를 남기지 않는다.

## 2026-06-15 운영/개발 환경 분리 안전장치

- `ALPHAMATE_ENV=production`이면 개발용 로그인 API가 거부된다.
- `ALPHAMATE_ENV=production`이면 개발용 복기권 구매 API가 거부된다.
- `ALPHAMATE_ENV=production`이면 `dev-token`, `dev-ad-reward`, `dev-pro-entitlement` 같은 개발용 토큰은 인증/광고/Pro 권한으로 인정되지 않는다.
- frontend production build 또는 `VITE_ALPHAMATE_ENV=production`에서는 개발용 카카오/네이버 로그인 버튼과 개발용 복기권 구매 버튼을 숨긴다.
- 실제 OpenAI API Key는 `.env.example`에 예시만 두고, 실제 값은 서버 `.env` 또는 배포 환경의 Secret Manager에만 둔다.
- frontend에는 `VITE_*` 값만 들어가므로 OpenAI API Key, 카카오/네이버 Secret, Google Play 서비스 계정 키를 넣으면 안 된다.

## 2026-06-16 카카오/네이버 로그인 서버 API 뼈대

- `POST /api/auth/login/kakao`는 카카오 access token을 받아 `https://kapi.kakao.com/v2/user/me`로 사용자 ID를 확인한다.
- `POST /api/auth/login/naver`는 네이버 access token을 받아 `https://openapi.naver.com/v1/nid/me`로 사용자 ID를 확인한다.
- provider 사용자 ID가 확인되면 AlphaMate 내부 사용자와 연결하고 자체 세션 토큰을 발급한다.
- 이메일은 계정 연결 보조 정보로만 쓰고 원문 대신 hash로 저장한다.
- 아직 남은 작업은 모바일 앱 SDK 또는 웹 OAuth authorize/code 교환 흐름에서 access token을 받아 서버 API로 전달하는 부분이다.

## 2026-06-16 OAuth authorization code 교환 API

- `POST /api/auth/login/kakao/code`는 카카오 authorization code를 `https://kauth.kakao.com/oauth/token`에서 access token으로 교환한 뒤 AlphaMate 세션을 발급한다.
- `POST /api/auth/login/naver/code`는 네이버 authorization code를 `https://nid.naver.com/oauth2.0/token`에서 access token으로 교환한 뒤 AlphaMate 세션을 발급한다.
- 카카오는 `KAKAO_CLIENT_ID`, 선택적으로 `KAKAO_CLIENT_SECRET`, 그리고 `KAKAO_REDIRECT_URI` 또는 요청 본문의 `redirect_uri`가 필요하다.
- 네이버는 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, 그리고 `NAVER_REDIRECT_URI` 또는 요청 본문의 `redirect_uri`, `state`가 필요하다.
- 실제 운영에서는 redirect URI와 state를 서버가 발급/검증하는 방식으로 더 강화해야 한다.

## 2026-06-16 프론트 OAuth 연결부

- frontend production 화면에서 `VITE_KAKAO_REST_API_KEY` 또는 `VITE_NAVER_CLIENT_ID`가 있으면 provider 로그인 버튼이 활성화된다.
- 로그인 시작 시 브라우저에서 state 값을 생성해 `localStorage`에 저장하고 provider authorization URL로 이동한다.
- callback으로 돌아온 `code`와 `state`는 저장된 state와 비교한 뒤 backend code-login API로 전달한다.
- frontend에 들어가는 값은 공개 client id/key와 redirect URI뿐이다.
- provider client secret, OpenAI API Key, Google Play 서비스 계정 키는 frontend에 넣지 않는다.

## 2026-06-16 OAuth 설정 진단

- `GET /api/auth/oauth-config`는 카카오/네이버 로그인에 필요한 서버 환경변수가 설정됐는지 boolean과 누락 목록만 반환한다.
- 이 endpoint는 실제 client secret 값을 절대 반환하지 않는다.
- frontend는 이 상태를 읽어 실제 로그인 전 빠진 설정을 사용자에게 안내한다.
- 운영에서는 이 진단 정보가 과도한 내부 정보를 노출하지 않도록 현재처럼 변수명 수준의 누락 안내까지만 유지한다.

## 2026-06-16 Google Play 결제 검증 준비

- `GET /api/journal/products`는 공개 가능한 상품 ID, 가격, 수량, Google Play 준비 상태만 반환한다.
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` 또는 `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` 값 자체는 응답에 포함하지 않는다.
- `POST /api/journal/google-play-purchase`는 소모성 복기권에 대해 서버에서 purchase token을 Google Play에 검증한 뒤에만 지급한다.
- purchase token 원문은 저장하지 않고 SHA-256 해시만 저장해 중복 지급을 막는다.
- 소모성 상품은 먼저 `consume_pending` 상태로 지급 기록을 남긴 뒤 consume 요청을 수행한다. consume 실패 시에도 이용권을 중복 지급하지 않고, 같은 purchase token이 다시 제출되면 consume만 재시도한다.
- Pro 구독은 `purchases.subscriptionsv2.get`으로 구독 토큰을 검증하고, 활성 상태와 만료 시간이 유효할 때만 Pro 플랜으로 저장한다.
- Pro 구독이 미확인 상태면 Google Play subscription acknowledge가 성공한 뒤에만 Pro 권한을 활성화한다.
- 저장 시 구독 토큰 원문은 남기지 않고 SHA-256 해시, 상품 ID, 상태, 만료 시간, 최신 주문 ID만 남긴다.
- 만료/비활성 구독 검증 결과도 저장해 기존 Pro 상태가 남아 비용이 새는 일을 막는다.
- 앱의 `Google Play 구매 복구`는 로컬 영수증에 남은 purchase token을 서버에 다시 제출하는 보조 흐름이다. 서버는 token hash로 중복 지급을 막아야 하며, 복구 요청도 최초 구매 요청과 같은 서버 검증을 반드시 통과해야 한다.
- Google Play RTDN Pub/Sub push endpoint는 공유 토큰 헤더가 맞을 때만 처리하며, 알림 수신 후 Google Play API를 다시 조회해 구독 상태를 갱신한다.
- 운영 배포에서는 `GOOGLE_PLAY_RTDN_OIDC_AUDIENCE`와 `GOOGLE_PLAY_RTDN_OIDC_EMAIL`을 설정해 Pub/Sub push JWT의 audience, email, 서명을 검증한다.
- `ALPHAMATE_ENV=production`에서는 Play Console에 등록한 상품 ID 환경변수 6개가 모두 설정되어야 Google Play readiness가 통과한다.
- 서버 배포 전 `backend\scripts\validate_release_env.py`를 실행해 필요한 환경변수 이름만 확인하고 secret 원문이 출력되지 않는지 확인한다.
- Google Play 서비스 계정은 JSON 파싱, 필수 필드, private key 형식까지 readiness에서 검사해 깨진 키로 배포되지 않게 한다.

## 2026-06-18 AdMob 보상형 광고 SSV 검증 상태

- 앱에서 광고를 봤다는 클라이언트 값을 그대로 믿지 않고, AdMob이 서버로 보내는 SSV 콜백을 기준으로 광고 보상을 인정한다.
- `GET /api/journal/admob-ssv`는 Google AdMob 공개키로 ECDSA 서명을 검증하고, `transaction_id` 중복을 막아 광고 보상이 반복 지급되지 않게 한다.
- `ADMOB_REWARDED_AD_UNIT_ID`를 운영 서버에 설정해 의도한 보상형 광고 단위만 인정해야 한다.
- AdMob SSV 공개키는 최대 24시간 캐시하고, 키 회전에 맞춰 다시 가져오도록 했다.
- 운영 배포 전 모바일 앱에는 AdMob SDK, 보상형 광고 단위, SSV 콜백 URL, 로그인된 사용자 ID 전달이 연결되어야 한다.
## 2026-06-20 복기 보관함 보안/배포 메모

- 사용자가 `매매 이력 저장`을 켠 상태에서 AI 복기를 실행하면 매매 스냅샷, 당시 차트 데이터, AI 복기 결과가 계정별 복기 보관함에 저장된다.
- 저장된 복기 데이터는 계정 데이터 내보내기와 계정 데이터 삭제 범위에 포함된다.
- AI Key는 계속 프론트엔드에 넣지 않고 서버 환경변수로만 관리해야 한다. 복기 보관함은 저장된 결과를 읽는 기능일 뿐, Key를 앱에 노출하지 않는다.
- 복기 보관함 진입 전면 광고는 `VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID`로 분리했다. 운영 배포 전 Google 테스트 광고 단위가 남아 있으면 `npm run release:check`에서 실패해야 한다.
- 광고 로딩 실패나 웹 환경에서는 사용자의 저장 데이터 접근을 막지 않는다. 광고 수익화보다 사용자가 보관한 데이터 접근권을 우선한다.
## 2026-06-21 AI 복기 동의 기록

- AI 복기 동의는 `ALPHAMATE_PRIVACY_CONSENT_VERSION` 값과 UTC 시각으로 계정에 저장된다.
- 동의 이력은 최신 상태만 저장하며, 계정 데이터 내보내기와 계정 삭제 범위에 포함된다.
- 개인정보처리방침 문구를 바꾸는 경우 `ALPHAMATE_PRIVACY_CONSENT_VERSION`도 함께 올려야 한다.
- 매매복기 계정 관리 화면은 현재 동의 안내 버전과 AI/개인정보 이용 안내를 보여준다.
- 안내 문구가 실제 개인정보처리방침과 달라지지 않도록, 배포 전 정책 문구와 앱 내 안내를 함께 검토해야 한다.

## 2026-06-21 개인정보처리방침 URL 점검

- 운영 배포 전 `ALPHAMATE_PRIVACY_POLICY_URL`에 공개 HTTPS 개인정보처리방침 주소를 설정해야 한다.
- `/api/app/readiness`와 `backend/scripts/validate_release_env.py`는 이 값이 없거나 HTTPS 주소가 아니면 실패한다.
- Play Store 등록 정보의 개인정보처리방침 URL, 앱 내 `개인정보/AI 이용 안내`, 서버의 `ALPHAMATE_PRIVACY_CONSENT_VERSION`은 같은 정책 문서를 기준으로 함께 관리해야 한다.

## 2026-06-20 운영 데이터 저장소 설정

- 운영 배포에서는 계정, 매매 기록, 이용권/광고 보상, 복기 보관함, 운영 이벤트 로그 DB 경로를 반드시 명시해야 한다.
- 필요한 환경변수는 `ALPHAMATE_ACCOUNT_DB_PATH`, `ALPHAMATE_JOURNAL_DB_PATH`, `ALPHAMATE_ACCESS_DB_PATH`, `ALPHAMATE_REVIEW_HISTORY_DB_PATH`, `ALPHAMATE_EVENT_LOG_DB_PATH`, `ALPHAMATE_ADMIN_TOKEN`이다.
- 실패한 `/api/...` 요청은 `operational_events` 테이블에 method, path, status code, 사용자 ID, 메시지, 안전한 부가정보로 저장된다. Authorization, token, secret, password, private key처럼 비밀값으로 보이는 필드는 저장 전에 `[redacted]`로 바뀐다.
- 모바일 앱의 광고/결제 SDK 실패는 `POST /api/client-events`를 통해 같은 `operational_events` 테이블에 저장한다. 클라이언트 보고는 장애 분석용 보조 정보이며, 광고 보상이나 결제 지급의 신뢰 근거로 사용하면 안 된다.
- `GET /api/admin/operational-events`는 `Authorization: Bearer ...`에 담긴 `ALPHAMATE_ADMIN_TOKEN`이 맞을 때만 최근 운영 로그를 반환한다. 이 토큰은 서버 secret으로만 관리하고 앱, frontend 환경변수, GitHub에 넣지 않는다.
- `GET /api/admin/operational-events/summary`도 같은 관리자 토큰으로 보호하며, 최근 운영 로그를 level, event type, path 기준으로 집계해 장애 원인 분류에 사용한다.
- `DELETE /api/admin/operational-events/retention`은 같은 관리자 토큰으로 보호하며, 지정한 보관기간보다 오래된 운영 로그만 삭제한다. 보관기간은 7일 미만으로 설정할 수 없고, 개인정보 최소 보관과 장애 분석 필요성 사이에서 운영 정책으로 정한다.
- 기본 개발 경로인 `backend/data/*.sqlite3`는 로컬 개발용으로만 보고, 운영에서는 백업 가능한 서버 볼륨이나 관리형 DB 마이그레이션 대상으로 분리해야 한다.
- 현재 코드는 SQLite 기반이므로 초기 운영은 명시 경로 + 백업 정책으로 시작할 수 있지만, 사용자 수가 늘면 PostgreSQL 같은 관리형 DB로 옮기는 것이 다음 큰 단계다.
