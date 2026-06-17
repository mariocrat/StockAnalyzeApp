# AlphaMate Development History

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
