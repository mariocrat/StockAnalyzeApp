# AlphaMate 보안/배포 설계 메모

## 권장 결론

- 모바일 앱에는 OpenAI/Gemini API Key를 넣지 않는다.
- 앱은 로그인, 광고 시청 완료, 매매복기 데이터를 서버로 보내고 서버가 AI API를 호출한다.
- OpenAI API Key는 서버 환경변수 또는 클라우드 Secret Manager에만 둔다.
- 매매복기 저장은 기본 비활성으로 두고, 사용자가 명시적으로 저장을 켠 경우에만 계정별 DB에 저장한다.
- 광고 보상, 결제 검증, 사용량 제한, 사용자별 비용 통제는 모두 서버에서 처리한다.

## 권장 흐름

1. 사용자가 앱에서 매매 기록을 입력한다.
2. 사용자가 일반 복기 또는 심층 복기를 실행한다.
3. 무료 사용자는 필요 시 앱에서 보상형 광고를 본다.
4. 앱은 로그인 세션, 광고 보상 토큰, 매매 기록, 개인정보/매매 기록 전송 동의 여부를 서버로 보낸다.
5. 서버는 사용자 인증, 광고 보상 검증, 이용권 차감, 요청 제한, 비용 제한을 확인한다.
6. 서버가 OpenAI API를 호출한다.
7. 서버는 분석 결과만 앱에 반환한다.
8. 사용자가 매매 이력 저장을 켠 경우에만 복기 결과와 차트 스냅샷을 계정별 DB에 저장한다.

## 현재 배포용 API 구조

- `POST /api/journal/review-once`
- `POST /api/journal/ai-review-once`
- `POST /api/journal/charts-once`

이 API들은 요청 본문으로 받은 매매 기록만 분석한다. 저장 기능이 꺼져 있으면 SQLite에 매매 기록을 저장하지 않는다.

Legacy `GET /api/journal/ai-review`는 이용권, 광고 보상, 요청 제한을 우회하지 못하도록 410 Gone으로 닫혀 있다.

운영 환경에서 서버 DB를 읽거나 쓰는 매매 기록 API는 로그인 세션이 필요하다. 로그인하지 않은 일회성 흐름은 `review-once`, `ai-review-once`, `charts-once`처럼 request-body 기반 API를 사용해야 한다.

## 배포 전 보안 작업

- 카카오/네이버 로그인 또는 OIDC 기반 간편 로그인을 운영 키로 연결한다.
- `(provider, provider_user_id)`를 내부 사용자 ID에 연결하고, 계정 연결은 사용자 확인 후 처리한다.
- 이용권, Pro 상태, 광고 보상, 일/월 사용량은 서버 DB에 저장한다.
- AdMob SSV 콜백을 실제 광고 단위와 연결한다.
- Google Play Billing 검증과 RTDN Pub/Sub push를 실제 Play Console 값과 연결한다.
- AI 복기 요청은 사용자별, IP별, 서버 전체 동시 실행 제한을 둔다.
- 운영 서버는 HTTPS만 사용한다.
- 서버 로그에는 매매 기록 원문, 메모, Authorization 헤더, AI Key를 남기지 않는다.
- 운영 DB 경로는 백업 가능한 서버 볼륨 또는 관리형 DB로 분리한다.

## 개인정보처리방침 초안 문구

> AlphaMate는 사용자가 입력한 매매 기록, 종목명, 체결 가격, 수량, 메모를 매매복기 및 AI 분석 제공 목적으로 처리합니다.
> AI 분석을 요청하는 경우 해당 입력 데이터와 차트 지표가 AI 분석 제공업체(OpenAI 또는 Google 등)에 전송될 수 있습니다.
> 회사는 기본적으로 매매복기 전문을 서버에 저장하지 않으며, 분석 요청 처리 후 즉시 폐기합니다.
> 사용자가 매매 이력 저장 기능을 켜는 경우 해당 기록은 사용자 계정별로 저장되며, 사용자는 앱에서 열람, 내보내기, 삭제할 수 있습니다.
> 서비스 안정성, 부정 이용 방지, 광고 보상 검증, 오류 분석을 위해 최소한의 접속 기록, 인증 식별자, 요청 시각, 처리 결과 상태를 일정 기간 보관할 수 있습니다.
> 사용자는 AI 분석 요청 시 개인정보 및 민감한 투자자 메모가 외부 AI 서비스로 전송될 수 있음을 확인하고 동의해야 합니다.

이 문구는 개발 초안이며 법률 자문이 아니다. 실제 Play Store 배포 전 개인정보보호법, 전자상거래, 광고 정책, Google Play 정책 기준으로 최종 법률 검토가 필요하다.

## Google Play Data safety 작성 방향

- AI 분석 요청 시 매매 데이터가 기기 밖 서버로 전송되므로 데이터 수집/처리에 해당한다.
- AdMob SDK 사용으로 광고 식별자 및 광고 관련 데이터 처리가 발생할 수 있다.
- Google Play Data safety form에는 앱, 서버, SDK가 처리하는 데이터 범위를 함께 신고해야 한다.
- 일회성 처리라도 기기 밖으로 전송되는 데이터는 사용자에게 명확히 안내해야 한다.

## 개발/운영 환경 분리

개발 환경 예시:

```env
OPENAI_API_KEY=실제_OpenAI_Key
OPENAI_BASIC_REVIEW_MODEL=gpt-5.4-mini
OPENAI_ADVANCED_REVIEW_MODEL=gpt-5.6-terra
ALPHAMATE_ENV=development
ALPHAMATE_DEV_AUTH_TOKEN=dev-token
ALPHAMATE_DEV_AD_REWARD_TOKEN=dev-ad-reward
ALPHAMATE_DEV_PRO_ENTITLEMENT_TOKEN=dev-pro-entitlement
ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC=false
```

프론트 개발 환경 예시:

```env
VITE_DEV_AUTH_TOKEN=dev-token
VITE_DEV_AD_REWARD_TOKEN=dev-ad-reward
VITE_DEV_ACCESS_PLAN=free
VITE_DEV_PRO_ENTITLEMENT_TOKEN=dev-pro-entitlement
```

운영에서는 `ALPHAMATE_ENV=production`을 사용한다. production에서는 개발용 로그인, 개발용 구매, `dev-token`, `dev-ad-reward`, `dev-pro-entitlement`가 실제 권한으로 인정되지 않는다.

frontend에는 `VITE_*` 공개 설정만 들어가야 한다. OpenAI API Key, 카카오/네이버 Secret, Google Play 서비스 계정 JSON, 관리자 토큰은 frontend `.env`에 넣지 않는다.

## 로그인 보안 상태

- 카카오/네이버 웹 OAuth authorize/code 교환 흐름과 backend code-login API가 연결되어 있다.
- 운영 전 실제 Client ID, Secret, Redirect URI를 카카오/네이버 개발자 콘솔 값으로 채워야 한다.
- frontend는 공개 client id/key와 redirect URI만 가진다.
- provider client secret은 backend 환경변수에만 둔다.
- OAuth 설정 진단 API는 secret 값을 반환하지 않고 준비 여부와 누락된 설정 이름만 반환한다.

## 이용권/구독 보안 상태

- AI 복기 이용권은 SQLite-backed entitlement wallet으로 관리한다.
- `ALPHAMATE_ACCESS_DB_PATH`는 운영에서 백업 가능한 서버 볼륨 또는 관리형 DB 경로로 분리해야 한다.
- Google Play 소모성 상품은 purchase token을 서버에서 검증하고, token 원문은 저장하지 않고 SHA-256 hash만 저장한다.
- Pro 구독은 `purchases.subscriptionsv2.get`으로 구독 token을 검증하고, 활성 상태와 만료 시간 기준으로만 Pro 권한을 부여한다.
- RTDN Pub/Sub push는 공유 토큰과 선택적 OIDC 검증으로 보호한다.

## AdMob 보안 상태

- 모바일 앱에는 AdMob SDK가 연결되어 있다.
- 운영 배포 전 실제 AdMob 앱 ID, 보상형/전면/배너 광고 단위 ID, SSV 콜백 URL을 연결해야 한다.
- AdMob SSV는 Google 공개키로 서명을 검증하고, transaction id 중복 지급을 막는다.
- 광고 로드 실패는 사용자 흐름을 막지 않고 운영 로그에 기록한다.

## 운영 로그 보안 상태

- 운영 로그 DB는 `ALPHAMATE_EVENT_LOG_DB_PATH`로 분리한다.
- 관리자 로그 API는 `ALPHAMATE_ADMIN_TOKEN`으로 보호하고 production에서는 32자 이상의 긴 토큰을 요구한다.
- 로그 details는 secret-like 값, 긴 문자열, 큰 객체를 저장 전에 줄이거나 가린다.
- 사용자가 오류 화면의 문의용 ID를 알려주면 관리자 API에서 `request_id`로 해당 실패를 찾을 수 있다.
