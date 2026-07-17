# AlphaMate 출시 준비 체크리스트

이 문서는 Play Store 출시 전 준비물을 하나씩 확인하기 위한 체크리스트입니다. 개발 용어를 최대한 줄였고, "무엇을 준비해야 하는지", "어디에 쓰이는지", "준비되면 어떻게 확인하는지"를 기준으로 정리했습니다.

## 1. 서버와 API Key

### OpenAI API Key

- [ ] OpenAI API Key를 발급한다.
- [ ] Key는 모바일 앱이나 frontend `.env`에 넣지 않는다.
- [ ] 운영 서버의 환경변수 또는 Secret Manager에만 넣는다.
- [ ] 일반 복기 모델과 심화 복기 모델 환경변수를 설정한다.
- [ ] AI 복기 분당 요청 제한과 서버 동시 처리 개수를 운영 비용에 맞게 설정한다.

확인 방법:

```env
OPENAI_API_KEY=실제_Key
OPENAI_BASIC_REVIEW_MODEL=gpt-5.4-mini
OPENAI_ADVANCED_REVIEW_MODEL=gpt-5.6-terra
OPENAI_BASIC_REVIEW_MAX_OUTPUT_TOKENS=1000
OPENAI_ADVANCED_REVIEW_MAX_OUTPUT_TOKENS=3000
ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE=10
ALPHAMATE_AI_REVIEW_MAX_CONCURRENT=3
ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS=300
ALPHAMATE_JOURNAL_ONCE_MAX_TRADES=500
ALPHAMATE_AI_REVIEW_MAX_TRADES=100
ALPHAMATE_JOURNAL_MEMO_MAX_CHARS=2000
ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT=500
ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES=500
ALPHAMATE_OPENAI_TIMEOUT_SECONDS=45
ALPHAMATE_OPENAI_MAX_RETRIES=1
ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS=0.5
```

기본값은 일반 복기 `gpt-5.4-mini`, 심화 복기 `gpt-5.6-terra`입니다. 출시 직전 OpenAI 공식 모델/가격표가 바뀌었으면 이 두 환경변수만 바꾸면 됩니다.
OpenAI 실행 안전 상한: timeout 최대 90초, 재시도 최대 3회, 재시도 대기 최대 5초.
OpenAI 출력 안전 상한: 일반 복기 기본 1,000토큰, 심화 복기 기본 3,000토큰, 설정 가능한 최대 10,000토큰.
AI 복기 요청 제한 안전 상한: 분당 최대 60회.
AI 복기 동시 실행 안전 상한: 최대 20개 작업.
AI 복기 중복 요청 방지 캐시 안전 상한: 서버 프로세스당 메모리 최대 1,000개.
메모리 기반 요청 제한기 안전 상한: 제한기당 추적 client/user key 최대 10,000개.
AI 복기 중복 요청 TTL 안전 상한: 최대 3,600초.
매매복기 작업량 안전 상한: 단건 복기 최대 1,000건, AI 복기 최대 200건, 메모 최대 5,000자, 조회/분석 최대 1,000행.
광고 보상 정책 안전 상한: 심화 복기 이용권 1장당 보상형 광고 최대 20회.
AdMob SSV 저장 안전 상한: 보상 식별자 최대 120자, custom data 최대 500자.
Google Play 저장 안전 상한: 구매/구독 상품 및 주문 필드 최대 120자.
로그인 저장 안전 상한: provider 사용자 ID와 표시 이름 최대 120자.
개인정보 동의 저장 안전 상한: 저장/노출되는 동의 버전 최대 120자.
OAuth 로그인 timeout 안전 상한: 최대 20초.

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
Invoke-RestMethod -Uri 'https://api.alphamate.co.kr/healthz'
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
VITE_KAKAO_REDIRECT_URI=https://api.alphamate.co.kr/api/auth/kakao/callback
KAKAO_CLIENT_ID=카카오_REST_API_KEY
KAKAO_REDIRECT_URI=https://api.alphamate.co.kr/api/auth/kakao/callback
ALPHAMATE_OAUTH_TIMEOUT_SECONDS=8
ALPHAMATE_OAUTH_APP_SCHEME=com.mariocrat.stockanalyze
```

`KAKAO_CLIENT_SECRET`은 카카오 설정에서 필요한 경우에만 서버 Secret으로 따로 설정합니다. 실제 값은 문서나 GitHub에 적지 않습니다.

### 네이버 로그인

- [ ] 네이버 개발자 센터 앱을 만든다.
- [ ] Client ID를 확인한다.
- [ ] Client Secret을 확인한다.
- [ ] Callback URL을 등록한다.
- [ ] 서버와 frontend 환경변수에 같은 Callback URL을 넣는다.

환경변수:

```env
VITE_NAVER_CLIENT_ID=네이버_Client_ID
VITE_NAVER_REDIRECT_URI=https://api.alphamate.co.kr/api/auth/naver/callback
NAVER_CLIENT_ID=네이버_Client_ID
NAVER_REDIRECT_URI=https://api.alphamate.co.kr/api/auth/naver/callback
ALPHAMATE_OAUTH_TIMEOUT_SECONDS=8
ALPHAMATE_OAUTH_APP_SCHEME=com.mariocrat.stockanalyze
```

`NAVER_CLIENT_SECRET`은 서버 Secret으로 따로 설정합니다. 실제 값은 문서나 GitHub에 적지 않습니다.

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
- [ ] 심화 복기 이용권 5회 상품을 만든다.
- [ ] 심화 복기 이용권 10회 상품을 만든다.
- [ ] Pro 월 구독 상품을 만든다.
- [ ] Play Console 상품 ID와 서버 환경변수 상품 ID를 맞춘다.

상품 예시:

| 상품 | 가격 | 용도 |
| --- | ---: | --- |
| 일반 복기 30회권 | 2,900원 | 구독 없이 일반 복기 추가 사용 |
| 일반 복기 100회권 | 6,900원 | 일반 복기를 자주 쓰는 사용자 |
| 심화 복기 이용권 5회 | 2,900원 | 심화 복기 추가 사용 |
| 심화 복기 이용권 10회 | 4,900원 | 심화 복기를 자주 쓰는 사용자 |
| Pro 월 구독 | 3,900원 또는 4,900원 | 월 제공량과 광고 제거 |

### Google Play Developer API

- [ ] Google Cloud/Play Console 서비스 계정을 만든다.
- [ ] 서비스 계정에 Play Developer API 권한을 준다.
- [ ] 서비스 계정 JSON을 서버 Secret으로 넣는다.
- [ ] 서버가 Google Play 구매 토큰을 검증할 수 있게 설정한다.
- [ ] RTDN 알림을 받을 Pub/Sub push URL을 준비한다.

환경변수 예시:

```env
GOOGLE_PLAY_PACKAGE_NAME=com.mariocrat.stockanalyze
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
- [ ] 앱 복귀용 전면 광고 단위를 만든다.
- [ ] 차트 자세히 보기용 전면 광고 단위를 만든다.
- [ ] 배너 광고 단위를 만든다.
- [ ] 운영 빌드에서 Google 테스트 광고 단위가 남지 않게 한다.

환경변수:

```env
VITE_ADMOB_ANDROID_APP_ID=ca-app-pub-...
VITE_ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-...
VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID=ca-app-pub-...
VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID=ca-app-pub-...
VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID=ca-app-pub-...
VITE_ADMOB_BANNER_AD_UNIT_ID=ca-app-pub-...
ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-...
```

### 보상형 광고 SSV

- [ ] AdMob 보상형 광고의 Server Side Verification 콜백 URL을 서버로 설정한다.
- [ ] 로그인된 사용자 ID가 광고 SSV userId로 전달되는지 확인한다.
- [ ] 광고를 본 뒤 일반 복기 1회 실행이 가능한지 확인한다.
- [ ] 같은 광고 보상이 중복 사용되지 않는지 확인한다.
- [ ] 무료 사용자는 하단 배너 광고가 보이고 Pro 사용자는 비보상형 광고가 숨겨지는지 확인한다.
- [ ] 앱을 90초 이상 백그라운드에 둔 뒤 돌아올 때 전면 광고가 노출될 수 있는지 확인한다.
- [ ] 차트 자세히 보기는 3번째 진입마다 전면 광고가 시도되고, 광고 실패가 차트 진입을 막지 않는지 확인한다.
- [ ] 복기 보관함 진입 시 전면 광고가 1회 시도되고, 보관함 안에서 다른 복기를 눌러볼 때 과하게 반복되지 않는지 확인한다.

## 6. 개인정보처리방침과 Play Store 문구

- [ ] 개인정보처리방침 페이지를 만든다.
- [ ] HTTPS 공개 URL로 배포한다.
- [ ] 앱 내 개인정보/AI 이용 안내와 내용이 어긋나지 않는지 확인한다.
- [ ] Play Store Data safety 문항을 작성한다.
- [ ] AdMob SDK가 처리하는 데이터도 신고한다.
- [ ] AI 분석 시 매매 기록이 서버와 AI 제공업체로 전송된다는 내용을 명시한다.

환경변수:

```env
ALPHAMATE_PRIVACY_POLICY_URL=https://alphamate.co.kr/privacy
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

```powershell
.\verify_android_debug.bat
```

출시 빌드 전 확인:

```bat
cd frontend
npm run mobile:release:check
```

Android 업로드 서명 키를 처음 만들거나 `frontend/.env.release`의 빈 서명 비밀번호를 채우려면 아래 파일을 실행합니다. 이미 값이나 키 파일이 있으면 덮어쓰지 않습니다.

```powershell
.\generate_android_upload_key.bat
```

서명 키와 출시 설정이 준비된 뒤 Play Store 업로드용 AAB까지 만들려면 아래 파일을 실행합니다.

```powershell
.\verify_android_release.bat
```

## 8. 운영 로그와 고객 문의 대응

- [ ] `ALPHAMATE_ADMIN_TOKEN`을 32자 이상의 긴 랜덤 값으로 설정한다.
- [ ] 운영 로그 DB 경로를 설정한다.
- [ ] 로그 보관 기간을 정한다.
- [ ] 사용자가 오류 화면에 표시된 문의용 ID를 알려주면 로그를 조회할 수 있는지 확인한다.

긴 랜덤 토큰이 필요하면 `generate_release_secrets.bat`를 실행해서 서버용 `.env.release`의 빈 `ALPHAMATE_ADMIN_TOKEN`과 `GOOGLE_PLAY_RTDN_SHARED_TOKEN` 값을 채울 수 있습니다. 이미 값이 있으면 덮어쓰지 않으며, 채운 `.env.release`는 GitHub에 올리지 않습니다.

환경변수:

```env
ALPHAMATE_ADMIN_TOKEN=32자_이상의_긴_랜덤_토큰
ALPHAMATE_EVENT_LOG_RETENTION_DAYS=90
```

문의용 ID로 조회:

```powershell
Invoke-RestMethod -Uri 'https://api.alphamate.co.kr/api/admin/operational-events?request_id=문의용ID' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

오류 요약 보기:

```powershell
Invoke-RestMethod -Uri 'https://api.alphamate.co.kr/api/admin/operational-events/summary?limit=500' -Headers @{ Authorization = "Bearer $env:ALPHAMATE_ADMIN_TOKEN" }
```

## 9. 최종 검증

내 PC나 서버 설정이 출시 준비에 얼마나 가까운지 먼저 보고 싶으면 아래 파일을 실행합니다.

```powershell
.\release_readiness_report.bat
```

이 보고서는 필요한 설정 이름만 보여주고 API Key, 토큰, 서비스 계정 원문은 출력하지 않습니다.

일반 전체 검증:

```powershell
.\verify_project.bat
```

Android 디버그 검증:

```powershell
.\verify_android_debug.bat
```

Android 출시 AAB 검증:

```powershell
.\verify_android_release.bat
```

출시 직전에는 다음이 모두 통과해야 합니다.

- [ ] 백엔드 테스트
- [ ] 백엔드 컴파일 확인
- [ ] Git 추적 파일 비밀값 검사
- [ ] 프론트 출시 설정 테스트
- [ ] 프론트 Android 브랜딩 테스트
- [ ] 프론트 Android Billing Library 버전 테스트
- [ ] 프론트 모바일 결제 테스트
- [ ] 프론트 모바일 AdMob 테스트
- [ ] 프론트 사용자 오류 로그 테스트
- [ ] 프론트 API 오류 요청 ID 테스트
- [ ] 프론트 OAuth 앱 복귀 테스트
- [ ] 프론트 앱 뒤로가기 테스트
- [ ] 프론트 AI 복기 중복 요청 방지 테스트
- [ ] 프론트 스플래시 로딩 정책 테스트
- [ ] 프론트 차트 레이아웃 테스트
- [ ] 프론트 매매복기 모바일 UX 테스트
- [ ] 프론트 린트
- [ ] 프론트 운영 빌드
- [ ] Android 디버그 빌드
- [ ] Android 출시 AAB 빌드
- [ ] 실제 기기 로그인/결제/광고/AI 복기 수동 테스트

## 지금 당장 다음으로 할 일

1. OpenAI API Key를 준비한다.
2. 운영 서버를 어디에 둘지 정한다.
3. 개인정보처리방침 URL을 만든다.
4. 카카오/네이버 개발자 콘솔 앱을 만든다.
5. Google Play Console과 AdMob 설정을 시작한다.

이 다섯 가지가 준비되면, 앱을 실제 서비스 환경처럼 테스트하는 단계로 넘어갈 수 있습니다.

## 10. 출시용 설정 파일 템플릿

실제 Key나 비밀번호는 GitHub에 올리면 안 됩니다. 대신 아래 템플릿을 개인 PC나 운영 서버에서 복사해서 실제 값을 채웁니다.

- 서버용: `.env.release.example`
- 프론트/Android 빌드용: `frontend/.env.release.example`

사용 흐름:

1. PowerShell에서는 `.\prepare_private_release_setup.bat`, 명령 프롬프트에서는 `prepare_private_release_setup.bat`를 실행해서 템플릿 복사, 서버용 랜덤 토큰 채우기, Android 업로드 서명 키 준비, 출시 준비 보고서 확인을 한 번에 진행한다.
2. 복사한 파일에만 OpenAI Key, 카카오/네이버 Secret, Google Play 서비스 계정, AdMob 광고 단위처럼 외부에서 받아야 하는 값을 채운다.
3. 채운 파일은 GitHub에 올리지 않는다.
4. PowerShell에서는 `.\release_readiness_report.bat`, 명령 프롬프트에서는 `release_readiness_report.bat`를 다시 실행해서 빠진 설정이 줄어드는지 확인한다.
5. 루트의 `.env.release`와 `frontend/.env.release`가 있으면 보고서가 자동으로 그 파일을 우선 읽는다.

개별로 실행하고 싶다면 PowerShell 기준 `.\prepare_release_env_files.bat`, `.\generate_release_secrets.bat`, `.\generate_android_upload_key.bat` 순서로 실행해도 됩니다.

주의:

- OpenAI API Key는 서버 설정에만 넣고 frontend 설정에는 넣지 않는다.
- Android 키스토어 파일과 비밀번호는 GitHub에 올리지 않는다.
- 운영 서버 주소와 Google Play 패키지명은 서버용 설정과 프론트/Android 설정이 서로 맞아야 한다.

## Android 패키지명 배포 기준

- `VITE_GOOGLE_PLAY_PACKAGE_NAME`은 Google Play Console의 실제 패키지명과 같아야 한다.
- Android 빌드의 `applicationId`, 앱 내부 결제 요청 패키지명, 서버의 `GOOGLE_PLAY_PACKAGE_NAME`은 같은 값을 사용해야 한다.
- 패키지명을 바꿀 때는 `.env.release`와 서버 env를 함께 바꾸고 `npm run release:check`, `release_readiness_report.bat`를 실행한다.
