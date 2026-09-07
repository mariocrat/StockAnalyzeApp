# StockBoda Security

담당: 인증·secret·개인정보·로그·외부 신뢰 경계.
근거: [account_store](../backend/core/account_store.py), [oauth_login](../backend/core/oauth_login.py), [event_log](../backend/core/event_log.py), [privacy policy](../backend/core/privacy_policy.py), [Android manifest](../frontend/android/app/src/main/AndroidManifest.xml).

## 현재 보호와 열린 위험

서버는 세션 토큰을 해시로 저장한다. `ALPHAMATE_ENV=production`이 정확히 해석되는 정상 설정에서는 개발용 접근을 차단한다. 사용자별 저장 접근, AI 동의 검사, 서버 구매 검증, 구매 토큰 암호화, AdMob SSV 검증이 있다. 이 보호를 약화시키지 않는다.

- **H2:** 환경 이름 누락/오타는 fail-closed가 아니며 안전한 거절을 보장하지 않는다. 명시적 환경·시작 검증이 필요하며 Render Blueprint의 production 값만으로 다른 실행 경로를 보호할 수 없다.
- **H6:** OAuth custom scheme 티켓은 일회성·만료가 있고 앱이 state를 검사하지만 서버 교환은 티켓만 요구한다. 로그인 시작 앱의 verifier와 결합하는 후속 설계가 필요하다. 실제 가로채기 성공은 확인하지 않았다.
- **M8:** 앱 세션은 localStorage에 저장되고 Android allowBackup=true다. OS backup·기기 이동에 실제 포함되는 범위는 별도 검증한다.
- **M9:** X-Forwarded-For 첫 값을 직접 신뢰하고 일부 공개 일회성 분석 경로의 제한이 시장 API와 다르다. proxy 신뢰 설정과 요청 크기/빈도를 검토한다.

Session/OAuth/상품 식별자를 변경할 때 기존 로그인·설치·복구를 포함한 migration과 독립 review를 요구한다. custom scheme과 API origin을 임의 rename하지 않는다.

## 비밀값 경계

- OpenAI key, 관리자 token, 공급자 client secret, 서비스 계정, signing 암호, 구매 토큰 암호화 key는 서버/비공개 설정에만 둔다.
- VITE_* 값은 앱 번들에 공개될 수 있다. 공급자의 공개 client ID와 서버 secret을 구분한다.
- 출력은 이름·존재·일치·검증 결과로 제한한다. env 파일 전체, 실제 token, Authorization, private key, 고객 문서를 출력하지 않는다.
- [비밀값 검사](../scripts/check_no_tracked_secrets.py)는 제한된 패턴으로 추적 파일을 확인한다. 미추적 파일과 Git history, 바이너리/이미지, 외부 로그 검사를 대체하지 않는다.
- M2의 설정 예시는 실제 비밀값 유출로 확인된 것이 아니다. 현재 예시와 검사 스크립트는 이번 governance 작업에서 수정하지 않는다. 탐지 규칙을 약화하지 않는 별도 remediation이 필요하며 신규 문서는 따로 검사한다.
- 키 유출이 의심되면 원문을 재출력하지 말고 위치·종류·노출 범위를 보고한다. 키 교체/폐기는 영향과 권한을 확인한 별도 작업이다.

## 개인정보와 외부 전송

AI 전송 동의와 저장 opt-in을 분리한다. 현재 AI 경로는 Responses 요청에 store=false를 설정한다. 이 설정이 외부 사업자의 모든 로그·보관을 없앤다는 뜻은 아니다. 외부 정책의 최신 유효성은 별도 확인한다.

계정/매매/복기/권한/로그의 저장 위치와 삭제는 [DATA](DATA.md)에 둔다. 저장 off는 영속 복기함 저장을 제어하지만 메모리 idempotency 응답 cache까지 즉시 없어지는 의미는 아니다. 과거 “즉시 폐기” 문구를 검증 없이 재사용하지 않는다.

조사한 코드에서 고객 문서 upload/import는 확인하지 못했다. 해당 기능을 도입할 때 파일 형식·용량·파싱·악성 입력·원본 보관/삭제·로그·외부 전송을 설계해야 한다. 실제 고객 문서는 repository fixture로 사용하지 않는다.

## 로그와 운영 점검

event_log는 details의 민감한 키를 마스킹하고 크기를 제한한다. 자유 형식 message와 문자열 전체가 자동으로 안전해지는 것은 아니다(M7). 사용자 메모·문서·token을 메시지로 만들지 말고 코드화된 오류와 request ID를 사용한다.

OAuth code와 RTDN 공유 token은 URL query 경로에 등장한다. 앱 로그뿐 아니라 Uvicorn/proxy/외부 콘솔의 access log와 retention을 확인해야 한다. 감사한 로컬 로그에서는 해당 query 흔적을 찾지 못했으나 production과 history는 미검증이다.

이벤트 retention은 cache warm-up 경로와 연결되어 있다. 환경변수 하나를 설정했다고 즉시 삭제되었다고 보고하지 말고 실제 실행 경로와 주기를 확인한다.

production 점검에서 GET도 데이터 조회만 한다고 가정하지 않는다. OAuth callback·AdMob SSV는 상태를 바꾸며 DB getter도 schema 초기화를 할 수 있다. 승인되지 않은 live 상태 변경을 하지 않는다.
