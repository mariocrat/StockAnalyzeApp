# Login And Server DB Design

## 목표

AlphaMate를 앱으로 배포할 때 사용자를 구분하고, 사용자별로 Pro 구독, 일반 복기 이용권, 심층 복기 이용권, 광고 보상, 매매 이력 저장 여부를 안전하게 관리한다.

이 설계는 카카오 로그인과 네이버 로그인을 모두 지원하는 것을 전제로 한다. 두 로그인은 앱 입장에서는 다른 버튼이지만, 서버 내부에서는 같은 방식의 "로그인 제공자"로 처리한다.

## 핵심 결정

- OpenAI API Key는 앱에 넣지 않고 서버에만 둔다.
- 카카오/네이버는 사용자를 식별하는 수단이고, 복기권과 매매 이력은 AlphaMate 서버 DB가 관리한다.
- 운영 DB는 PostgreSQL을 권장한다. 개발 환경은 SQLite로 시작할 수 있지만, 결제/복기권 차감은 운영에서 PostgreSQL 트랜잭션으로 처리한다.
- 사용자는 카카오와 네이버 중 하나로 로그인할 수 있다.
- 같은 사람이 나중에 카카오와 네이버를 모두 연결하려면 앱에서 명시적으로 "계정 연결" 확인을 받는다.
- 매매 이력 저장은 기본 꺼짐이다. 사용자가 저장 기능을 켠 경우에만 서버 DB에 보관한다.
- 1회성 AI 복기는 요청 처리 후 원문 매매 데이터를 저장하지 않는다. 다만 과금, 악용 방지, 장애 분석을 위해 최소한의 요청 기록은 저장할 수 있다.

## 비목표

- 이번 단계에서 실제 카카오/네이버 SDK를 붙이지 않는다.
- 이번 단계에서 Google Play 결제나 AdMob 검증을 완성하지 않는다.
- 이번 단계에서 사용자 매매 이력을 기본 저장으로 바꾸지 않는다.

## 전체 구조

1. 앱에서 카카오 또는 네이버 로그인을 한다.
2. 앱은 로그인 제공자 토큰을 AlphaMate 서버로 보낸다.
3. 서버는 카카오/네이버 API로 토큰을 검증한다.
4. 서버는 `(provider, provider_user_id)`를 내부 `user_id`에 연결한다.
5. 서버는 AlphaMate 자체 세션 토큰을 앱에 발급한다.
6. 앱은 이후 AI 복기, 이용권 조회, 결제 검증 요청에 AlphaMate 세션 토큰을 보낸다.
7. 서버는 DB에서 사용자별 이용권과 사용량을 확인하고 차감한다.
8. 서버만 OpenAI API를 호출한다.

## 데이터 모델

### users

AlphaMate 내부 사용자 계정이다.

- `id`: 내부 사용자 ID
- `display_name`: 앱 표시 이름
- `created_at`
- `last_login_at`
- `status`: active, suspended, deleted
- `journal_storage_enabled`: 매매 이력 저장 여부
- `privacy_consent_version`: 동의한 개인정보 처리방침 버전
- `privacy_consented_at`

### user_identities

카카오/네이버 계정과 내부 사용자를 연결한다.

- `id`
- `user_id`
- `provider`: kakao 또는 naver
- `provider_user_id`: 카카오/네이버가 주는 고유 ID
- `email_hash`: 이메일은 필요하면 해시로 보관
- `connected_at`
- `last_verified_at`

`provider + provider_user_id`는 중복될 수 없다.

### user_sessions

앱 로그인 세션이다.

- `id`
- `user_id`
- `session_token_hash`
- `device_id_hash`
- `created_at`
- `expires_at`
- `revoked_at`

세션 토큰 원문은 DB에 저장하지 않고 해시만 저장한다.

### subscriptions

Pro 구독 상태다.

- `id`
- `user_id`
- `store`: google_play
- `product_id`
- `purchase_token_hash`
- `status`: active, expired, canceled, grace_period
- `started_at`
- `expires_at`
- `last_verified_at`

### credit_wallets

현재 보유 이용권 수량이다.

- `user_id`
- `basic_purchased_remaining`: 구매한 일반 복기 이용권
- `advanced_purchased_remaining`: 구매한 심층 복기 이용권
- `weekly_advanced_reward_remaining`: 광고 보상 심층 복기권
- `signup_basic_remaining`: 가입 보너스 일반 복기
- `updated_at`

### usage_counters

일/월/주 단위 사용량이다.

- `user_id`
- `date_key`: 예: 2026-06-14
- `month_key`: 예: 2026-06
- `week_key`: 예: 2026-W24
- `free_basic_daily_used`
- `free_basic_monthly_used`
- `pro_basic_monthly_used`
- `pro_advanced_monthly_used`
- `weekly_rewarded_ad_views`
- `weekly_advanced_reward_granted`

### purchases

소모성 이용권 구매 기록이다.

- `id`
- `user_id`
- `store`: google_play
- `product_id`
- `purchase_token_hash`
- `quantity`
- `kind`: basic 또는 advanced
- `status`: pending, verified, consumed, refunded
- `verified_at`
- `created_at`

### ad_rewards

보상형 광고 시청 검증 기록이다.

- `id`
- `user_id`
- `ad_network`: admob
- `reward_token_hash`
- `reward_type`: basic_review 또는 weekly_advanced_progress
- `status`: verified, rejected, duplicate
- `created_at`

### journal_trades

사용자가 저장 기능을 켠 경우에만 저장하는 매매 이력이다.

- `id`
- `user_id`
- `trade_date`
- `ticker`
- `name`
- `side`: buy 또는 sell
- `price`
- `quantity`
- `fee`
- `tax`
- `memo_encrypted`
- `created_at`
- `updated_at`
- `deleted_at`

민감할 수 있는 메모는 암호화 저장을 우선 검토한다.

### ai_review_requests

AI 복기 요청 기록이다. 원문 매매 메모를 저장하지 않는 것이 기본이다.

- `id`
- `user_id`
- `review_type`: basic 또는 advanced
- `access_source`: signup, free_daily, rewarded_ad, pro, purchased
- `model`
- `status`: success, failed, blocked
- `input_trade_count`
- `token_usage_in`
- `token_usage_out`
- `cost_estimate_krw`
- `created_at`

장애 분석용으로 에러 코드나 처리 시간은 저장할 수 있지만, 매매 원문과 Authorization 헤더는 저장하지 않는다.

## 이용권 차감 규칙

일반 복기:

1. 가입/무료 제공량
2. Pro 월 제공량
3. 구매한 일반 복기 이용권
4. 광고 시청 후 추가 제공
5. 구매 유도

심층 복기:

1. Pro 월 제공 심층 복기권
2. 광고 5회 시청 보상 주간 심층 복기권
3. 구매한 심층 복기 이용권
4. 구매 유도

차감은 반드시 서버 DB 트랜잭션 안에서 처리한다. 같은 사용자가 동시에 버튼을 두 번 눌러도 복기권이 음수가 되면 안 된다.

## API 초안

- `POST /api/auth/login/kakao`: 카카오 토큰 검증 후 AlphaMate 세션 발급
- `POST /api/auth/login/naver`: 네이버 토큰 검증 후 AlphaMate 세션 발급
- `POST /api/auth/logout`: 현재 세션 폐기
- `GET /api/me`: 내 계정과 저장 설정 조회
- `POST /api/me/link-provider`: 카카오/네이버 계정 연결
- `GET /api/journal/entitlements`: Pro/이용권/사용량 조회
- `POST /api/journal/ai-review-once`: 1회성 AI 복기
- `GET /api/journal/trades`: 저장 기능이 켜진 사용자만 저장 이력 조회
- `POST /api/journal/trades`: 저장 기능이 켜진 사용자만 매매 이력 저장
- `DELETE /api/journal/trades/{id}`: 사용자 본인 이력 삭제
- `POST /api/billing/google-play/verify`: 구독 또는 소모성 구매 검증
- `POST /api/ads/admob/reward`: 보상형 광고 검증

## 보안 원칙

- 앱에는 OpenAI API Key를 넣지 않는다.
- 앱에는 Google Play purchase token이 오래 남지 않게 한다.
- 서버 로그에 Authorization 헤더, OpenAI Key, 매매 메모, 광고 토큰 원문을 남기지 않는다.
- 세션 토큰, 결제 토큰, 광고 보상 토큰은 원문 저장 대신 해시 저장을 우선한다.
- HTTPS만 허용한다.
- 운영 배포 전 Play Integrity API로 위조 앱과 자동화 요청을 줄이는 방안을 검토한다.
- 탈퇴 시 저장된 매매 이력과 세션은 삭제하고, 결제/회계상 필요한 최소 기록만 별도 보존 기간을 둔다.

## 구현 단계

### 1단계: DB 기반 사용자/이용권 기초

- SQLAlchemy 또는 SQLModel 도입
- 개발 SQLite, 운영 PostgreSQL 설정 분리
- users, user_identities, credit_wallets, usage_counters 테이블 추가
- 현재 메모리 기반 access_control을 DB 기반으로 교체

### 2단계: 카카오/네이버 로그인

- 카카오 로그인 검증 API 추가
- 네이버 로그인 검증 API 추가
- AlphaMate 세션 토큰 발급
- 프론트에 카카오/네이버 로그인 버튼과 로그아웃 추가

### 3단계: 저장형 매매 이력 옵션

- 매매 이력 저장 켜기/끄기 설정 추가
- 저장 켜짐 사용자만 `journal_trades`에 저장
- 삭제/내보내기 정책 정리

### 4단계: 결제/광고 검증 연결

- Google Play 구독 검증
- Google Play 소모성 상품 검증
- AdMob 보상형 광고 서버 검증
- 이용권 차감과 구매 검증을 트랜잭션으로 연결

## 테스트 방법

- 로그인하지 않은 사용자가 AI 복기 API를 호출하면 거부되는지 확인한다.
- 카카오 로그인 사용자가 일반 복기 1회를 쓰면 해당 사용자만 차감되는지 확인한다.
- 네이버 로그인 사용자가 같은 기능을 써도 별도 사용자로 차감되는지 확인한다.
- 카카오와 네이버 계정 연결 후 같은 내부 사용자 지갑을 공유하는지 확인한다.
- 동시에 일반 복기 요청을 두 번 보내도 이용권이 한 번씩만 정확히 차감되는지 확인한다.
- 매매 이력 저장을 끈 상태에서는 `journal_trades`에 원문이 남지 않는지 확인한다.
- 매매 이력 저장을 켠 상태에서는 본인 데이터만 조회/삭제되는지 확인한다.
- Pro 만료 후 Pro 제공량이 더 이상 사용되지 않는지 확인한다.
- 구매 취소/환불 상태가 들어오면 남은 이용권과 접근 권한이 정책대로 바뀌는지 확인한다.

## 남은 결정 사항

- 운영 서버와 DB를 어디에 둘지 결정해야 한다.
- 카카오/네이버 로그인 중 어떤 것을 첫 구현 대상으로 할지 결정해야 한다.
- 매매 메모 암호화 방식과 키 관리 방식을 정해야 한다.
- 탈퇴 후 결제 기록 보존 기간은 실제 법률/세무 검토가 필요하다.
