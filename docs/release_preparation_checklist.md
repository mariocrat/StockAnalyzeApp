# AlphaMate 출시 준비 체크리스트

이 문서는 Play Store 출시 전 준비물을 하나씩 확인하기 위한 체크리스트입니다. 개발 용어를 최대한 줄였고, "무엇을 준비해야 하는지", "어디에 쓰이는지", "준비되면 어떻게 확인하는지"를 기준으로 정리했습니다.

## 1. 서버와 API Key

### OpenAI API Key

- [ ] OpenAI API Key를 발급한다.
- [ ] Key는 모바일 앱이나 frontend `.env`에 넣지 않는다.
- [ ] 운영 서버의 환경변수 또는 Secret Manager에만 넣는다.
- [ ] 일반 복기 모델과 심층 복기 모델 환경변수를 설정한다.

확인 방법:

```env
OPENAI_API_KEY=실제_Key
OPENAI_BASIC_REVIEW_MODEL=사용할_일반_복기_모델
OPENAI_ADVANCED_REVIEW_MODEL=사용할_심층_복기_모델
```

주의:

- Key를 카카오톡, 메모장, GitHub, 앱 코드, frontend `.env`에 남기지 않는다.
- 실제 모델명은 출시 전 OpenAI 공식 문서와 가격표 기준으로 다시 확인한다.

### 운영 서버

- [ ] HTTPS가 가능한 운영 서버를 준비한다.
- [ ] backend를 서버에서 실행할 방법을 정한다.
- [ ] 서버 환경변수 저장 방식을 정한다.
- [ ] 서버 재시작 후에도 데이터가 사라지지 않는 저장 경로를 준비한다.
- [ ] 서버 로그와 DB 백업 정책을 정한다.

확인 방법:

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/healthz'
```

정상 예시:

```json
{"ok": true, "service": "alphamate-api"}
```

## 2. 데이터 저장소

운영에서는 로컬 개발용 `backend/data/*.sqlite3`에 의존하면 안 됩니다. 서버에서 유지되고 백업 가능한 경로를 명시해야 합니다.

- [ ] 계정 DB 경로
- [ ] 매매 기록 DB 경로
- [ ] 이용권/광고 보상 DB 경로
- [ ] 복기 보관함 DB 경로
- [ ] 운영 로그 DB 경로

환경변수:

```env
ALPHAMATE_ACCOUNT_DB_PATH=/secure-data/accounts.sqlite3
ALPHAMATE_JOURNAL_DB_PATH=/secure-data/journal.sqlite3
ALPHAMATE_ACCESS_DB_PATH=/secure-data/access.sqlite3
ALPHAMATE_REVIEW_HISTORY_DB_PATH=/secure-data/review_history.sqlite3
ALPHAMATE_EVENT_LOG_DB_PATH=/secure-data/event_log.sqlite3
```

운영 초기는 SQLite로 시작할 수 있지만, 사용자 수가 늘면 PostgreSQL 같은 관리형 DB로 옮기는 것을 검토합니다.

## 3. 로그인

### 카카오 로그인

- [ ] 카카오 개발자 콘솔 앱을 만든다.
- [ ] REST API Key를 확인한다.
- [ ] Client Secret 사용 여부를 정한다.
- [ ] Redirect URI를 등록한다.
- [ ] 서버와 frontend 환경변수에 같은 Redirect URI를 넣는다.

환경변수:

```env
VITE_KAKAO_REST_API_KEY=카카오_REST_API_KEY
VITE_KAKAO_REDIRECT_URI=https://your-app.example.com/oauth/kakao
KAKAO_CLIENT_ID=카카오_REST_API_KEY
KAKAO_CLIENT_SECRET=필요한_경우만
KAKAO_REDIRECT_URI=https://your-app.example.com/oauth/kakao
```

### 네이버 로그인

- [ ] 네이버 개발자 센터 앱을 만든다.
- [ ] Client ID를 확인한다.
- [ ] Client Secret을 확인한다.
- [ ] Callback URL을 등록한다.
- [ ] 서버와 frontend 환경변수에 같은 Callback URL을 넣는다.

환경변수:

```env
VITE_NAVER_CLIENT_ID=네이버_Client_ID
VITE_NAVER_REDIRECT_URI=https://your-app.example.com/oauth/naver
NAVER_CLIENT_ID=네이버_Client_ID
NAVER_CLIENT_SECRET=네이버_Client_Secret
NAVER_REDIRECT_URI=https://your-app.example.com/oauth/naver
```

확인 방법:

- 앱에서 카카오 로그인 버튼을 누르면 카카오 로그인 페이지로 이동해야 한다.
- 앱에서 네이버 로그인 버튼을 누르면 네이버 로그인 페이지로 이동해야 한다.
- 로그인 후 AlphaMate 계정 상태가 표시되어야 한다.
- 카카오 계정과 네이버 계정의 복기권/기록이 섞이지 않아야 한다.

## 4. Google Play 결제

### 앱과 상품

- [ ] Google Play Console에 앱을 만든다.
- [ ] 패키지명을 frontend Android 설정과 맞춘다.
- [ ] 일반 복기 30회권 상품을 만든다.
- [ ] 일반 복기 100회권 상품을 만든다.
- [ ] 심층 복기 5회권 상품을 만든다.
- [ ] 심층 복기 10회권 상품을 만든다.
- [ ] Pro 월 구독 상품을 만든다.
- [ ] Play Console 상품 ID와 서버 환경변수 상품 ID를 맞춘다.

상품 예시:

| 상품 | 가격 | 용도 |
| --- | ---: | --- |
| 일반 복기 30회권 | 2,900원 | 구독 없이 일반 복기 추가 사용 |
| 일반 복기 100회권 | 6,900원 | 일반 복기를 자주 쓰는 사용자 |
| 심층 복기 5회권 | 2,900원 | 심층 복기 추가 사용 |
| 심층 복기 10회권 | 4,900원 | 심층 복기를 자주 쓰는 사용자 |
| Pro 월 구독 | 3,900원 또는 4,900원 | 월 제공량과 광고 제거 |

### Google Play Developer API

- [ ] Google Cloud/Play Console 서비스 계정을 만든다.
- [ ] 서비스 계정에 Play Developer API 권한을 준다.
- [ ] 서비스 계정 JSON을 서버 Secret으로 넣는다.
- [ ] 서버가 Google Play 구매 토큰을 검증할 수 있게 설정한다.
- [ ] RTDN 알림을 받을 Pub/Sub push URL을 준비한다.

환경변수 예시:

```env
GOOGLE_PLAY_PACKAGE_NAME=com.yourcompany.alphamate
GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=/secure-secrets/google-play-service-account.json
GOOGLE_PLAY_RTDN_SHARED_TOKEN=긴_랜덤_토큰
```

확인 방법:

- 테스트 계정으로 일반 복기권 구매
- 구매 후 이용권 증가 확인
- 같은 구매가 중복 지급되지 않는지 확인
- 구매 중 앱 종료 후 `Google Play 구매 복구`로 반영되는지 확인
- Pro 구독 구매 후 Pro 제공량이 보이는지 확인

## 5. AdMob 광고

### 광고 단위

- [ ] AdMob 앱을 만든다.
- [ ] 보상형 광고 단위를 만든다.
- [ ] 복기 보관함 진입용 전면 광고 단위를 만든다.
- [ ] 운영 빌드에서 Google 테스트 광고 단위가 남지 않게 한다.

환경변수:

```env
VITE_ADMOB_ANDROID_APP_ID=ca-app-pub-...
VITE_ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-...
VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID=ca-app-pub-...
ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-...
```

### 보상형 광고 SSV

- [ ] AdMob 보상형 광고의 Server Side Verification 콜백 URL을 서버로 설정한다.
- [ ] 로그인된 사용자 ID가 광고 SSV userId로 전달되는지 확인한다.
- [ ] 광고를 본 뒤 일반 복기 1회 실행이 가능한지 확인한다.
- [ ] 같은 광고 보상이 중복 사용되지 않는지 확인한다.

## 6. 개인정보처리방침과 Play Store 문구

- [ ] 개인정보처리방침 페이지를 만든다.
- [ ] HTTPS 공개 URL로 배포한다.
- [ ] 앱 내 개인정보/AI 이용 안내와 내용이 어긋나지 않는지 확인한다.
- [ ] Play Store Data safety 문항을 작성한다.
- [ ] AdMob SDK가 처리하는 데이터도 신고한다.
- [ ] AI 분석 시 매매 기록이 서버와 AI 제공업체로 전송된다는 내용을 명시한다.

환경변수:

```env
ALPHAMATE_PRIVACY_POLICY_URL=https://your-site.example.com/privacy
ALPHAMATE_PRIVACY_CONSENT_VERSION=2026-06-24
```

주의:

- 이 문서는 법률 자문이 아닙니다.
- 실제 출시 전 개인정보보호법, 전자상거래/광고 정책, Google Play 정책 기준으로 최종 검토가 필요합니다.

## 7. Android 앱 빌드

- [ ] 앱 이름을 최종 결정한다.
- [ ] 앱 아이콘을 최종 결정한다.
- [ ] 스플래시 이미지를 확인한다.
- [ ] Android 패키지명을 확정한다.
- [ ] Android 서명 키를 만든다.
- [ ] 출시용 AAB 빌드를 만든다.
- [ ] 실제 Android 기기에서 테스트한다.

확인 명령:

```bat
verify_android_debug.bat
```

출시 빌드 전 확인:

```bat
cd frontend
npm run mobile:release:check
```

## 8. 운영 로그와 고객 문의 대응

- [ ] `ALPHAMATE_ADMIN_TOKEN`을 32자 이상의 긴 랜덤 값으로 설정한다.
- [ ] 운영 로그 DB 경로를 설정한다.
- [ ] 로그 보관 기간을 정한다.
- [ ] 사용자가 오류 화면에 표시된 문의용 ID를 알려주면 로그를 조회할 수 있는지 확인한다.

환경변수:

```env
ALPHAMATE_ADMIN_TOKEN=32자_이상의_긴_랜덤_토큰
ALPHAMATE_EVENT_LOG_RETENTION_DAYS=90
```

문의용 ID로 조회:

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events?request_id=문의용ID' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

오류 요약 보기:

```powershell
Invoke-RestMethod -Uri 'https://your-api.example.com/api/admin/operational-events/summary?limit=500' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

## 9. 최종 검증

일반 전체 검증:

```bat
verify_project.bat
```

Android 디버그 검증:

```bat
verify_android_debug.bat
```

출시 직전에는 다음이 모두 통과해야 합니다.

- [ ] backend tests
- [ ] backend compile
- [ ] tracked secret scan
- [ ] frontend release-env tests
- [ ] frontend Android branding tests
- [ ] frontend mobile billing tests
- [ ] frontend mobile AdMob tests
- [ ] frontend client event tests
- [ ] frontend API error request ID tests
- [ ] frontend lint
- [ ] frontend production build
- [ ] Android debug build
- [ ] 실제 기기 로그인/결제/광고/AI 복기 수동 테스트

## 지금 당장 다음으로 할 일

1. OpenAI API Key를 준비한다.
2. 운영 서버를 어디에 둘지 정한다.
3. 개인정보처리방침 URL을 만든다.
4. 카카오/네이버 개발자 콘솔 앱을 만든다.
5. Google Play Console과 AdMob 설정을 시작한다.

이 다섯 가지가 준비되면, 앱을 실제 서비스 환경처럼 테스트하는 단계로 넘어갈 수 있습니다.
