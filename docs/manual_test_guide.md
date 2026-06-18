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

1. backend가 켜진 상태에서 `http://127.0.0.1:8002/api/journal/products`를 엽니다.
2. `consumables`에 일반/심층 복기권 상품이 보이는지 확인합니다.
3. `subscriptions`에 Pro 월 구독 상품이 보이는지 확인합니다.
4. `google_play.missing_server_settings`에 빠진 서버 설정이 표시되는지 확인합니다.
5. Google Play 구매 요청 endpoint는 실제 Google Play purchase token이 검증된 경우에만 복기권을 지급합니다.

정상 결과:

- 상품 ID와 가격/수량은 보입니다.
- 서비스 계정 secret 값은 응답에 보이지 않습니다.
- 서비스 계정 설정이 없거나 잘못되면 503으로 막히고 복기권이 충전되지 않습니다.
- 같은 purchase token을 다시 보내도 복기권은 한 번만 충전됩니다.
- Pro 구독은 Google Play subscription token이 검증되고 만료 시간이 유효할 때만 Pro 상태로 반영됩니다.
- 같은 subscription token이 만료/비활성 상태로 다시 검증되면 Pro 상태가 해제되어야 합니다.
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

개발 PC의 웹 화면만으로는 실제 AdMob 광고 시청을 완전히 검증할 수 없습니다. 이 부분은 Android/iOS 앱 빌드 뒤 AdMob 테스트 광고 단위로 확인해야 합니다.

광고 정책 설정:

- `ALPHAMATE_ADS_PER_ADVANCED_TICKET=5`: 광고 5회 시청 시 주간 심층 복기권 1장 지급
- `ALPHAMATE_FORCE_REWARDED_AD_CHAIN=false`: 여러 보상형 광고를 연속으로 강제하지 않음
- `GET /api/journal/products`에서 `admob.ready`, `settings.ad_policy` 값을 확인할 수 있습니다.

## 9. Android 앱 래퍼 및 APK 빌드 확인

현재 frontend에는 Capacitor 앱 래퍼와 Android 프로젝트 골격이 들어간 상태입니다. 이 PC에서는 프로젝트 안의 `.tools` 폴더에 JDK와 Android SDK command-line tools를 받아 디버그 APK 빌드까지 확인했습니다. `.tools`는 PC 전용 도구라 GitHub에는 올리지 않습니다.

1. `frontend/.env`에서 배포용 앱은 `VITE_API_BASE=https://서버주소`, `VITE_ALPHAMATE_ENV=production`, `VITE_ENABLE_DEV_TOOLS=false`로 둡니다.
2. `frontend` 폴더에서 `npm run build`를 실행합니다.
3. 웹 변경사항을 Android 프로젝트에 반영할 때는 `npm run mobile:sync` 또는 `npm run mobile:build`를 실행합니다.
4. Android Studio로 열 때는 `npm run mobile:open:android`를 실행합니다.
5. APK 빌드는 아래처럼 로컬 JDK/SDK 환경변수를 잡은 뒤 `frontend/android`에서 실행합니다.

```powershell
$env:JAVA_HOME='D:\작업\windsurf\StockAnalyze\.tools\jdk\jdk-21.0.11+10'
$env:ANDROID_HOME='D:\작업\windsurf\StockAnalyze\.tools\android-sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
$env:Path="$env:JAVA_HOME\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
cd D:\작업\windsurf\StockAnalyze\frontend\android
.\gradlew.bat assembleDebug
```

정상 빌드 결과물은 아래 위치에 생깁니다.

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

`frontend/android/local.properties`는 이 PC의 SDK 위치만 적는 파일이라 GitHub에는 올리지 않습니다. 새 PC에서 다시 빌드할 때는 Android Studio를 설치하거나, 같은 방식으로 `.tools`에 JDK/SDK를 다시 준비하면 됩니다.

아직 이 단계에서는 Play Store 서명, 앱 아이콘, 스플래시 이미지, AdMob SDK 연결, Google Play Billing SDK 연결을 완료한 것이 아닙니다.
