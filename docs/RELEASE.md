# StockBoda Release

담당: 빌드 종류·환경 선택·최종 아티팩트·배포 증거.
근거: [package scripts](../frontend/package.json), [debug wrapper](../scripts/verify_android_debug.ps1), [release wrapper](../scripts/verify_android_release.ps1), [Gradle app](../frontend/android/app/build.gradle), [Render Blueprint](../render.yaml).

## 환경별 현재 동작

| 경로 | 실제 의미 |
| --- | --- |
| run_backend.bat / run_frontend.bat | backend 8002 / frontend 5174. 포트 점유가 동일 저장소의 올바른 프로세스라는 보장은 없음 |
| npm run dev | Vite 개발 실행. wrapper와 같은 포트가 아님 |
| npm run build | 일반 Vite production 모드. .env.release를 선택하지 않으며 소스에 loopback API fallback 존재 |
| mobile:build | Vite --mode release → dist API 검사 → Capacitor sync |
| verify_android_debug.bat | development 표시·테스트 광고 ID를 설정하지만 mobile:build 사용. API를 개발 서버로 고정하지 않음 |
| verify_android_oauth_debug.bat | release 파일의 production 공개 OAuth/API 설정을 사용 |
| verify_android_admob_qa.bat | 운영 공개 설정을 사용하는 등록 기기 QA 경로 |
| verify_android_release.bat | frontend release 환경을 process에 로드하고 release 검사·웹 빌드·sync·bundleRelease 수행 |
| Render | Blueprint의 production 환경·persistent disk와 Uvicorn 시작 명령 |

**H1: 현재 안전하게 격리된 debug API 경로가 확보되었다고 문서화할 수 없다.** 테스트 광고·development 표시·debug 서명만으로 production 계정/데이터/이용권이 보호되지 않는다. 기존 OAuth/AdMob QA 가이드를 일반 개발 절차로 실행하지 않는다.

개발 API·DB·계정·OAuth 설정을 분리하는 후속 작업이 필요하다. 그 전에는 승인된 범위의 소스/정책 검사만으로 결과 수준을 제한한다. 운영 점검이 명시적으로 요청되더라도 대상 요청의 실제 상태 변경 여부를 먼저 확인한다.

## 환경과 호환성 검증

- Vite mode, process의 VITE_* 값, mode별 env 파일, 최종 번들 주소를 함께 확인한다. release 환경을 로드한 shell을 개발용으로 재사용하지 않는다.
- com.mariocrat.stockanalyze는 Android/Play/OAuth와 연결된 안정 식별자다. 기본 debug/release application ID가 같으므로 설치·서명 충돌이 가능하다.
- 설치 문제를 해결하려고 앱을 삭제하면 로컬 데이터가 사라질 수 있다. 임의 제거하지 않는다.
- AndroidManifest의 HTTPS WebView origin과 backend CORS의 https://localhost를 유지한다. 이를 개발용 웹 localhost 허용과 혼동하지 않는다.
- Gradle의 버전 기본값이나 frontend package 버전을 업로드 기준으로 삼지 않는다. 실제 release versionCode/versionName과 Play에 이미 업로드된 값을 확인한다.
- signing key·암호·서비스 계정 JSON은 비공개 설정이다. 정렬 검사에는 항목 존재/일치 여부만 보고한다.

## 승인된 release 작업의 순서

1. 실제 checkout/HEAD/diff, 릴리스 대상과 포함할 변경을 확인한다.
2. 공개 API·package/OAuth·광고·버전 설정과 private signing 준비를 비밀값 없이 확인한다. 검사 통과가 외부 Console 연결 성공을 뜻하지 않음을 기록한다.
3. 검증된 도구와 기존 release wrapper를 사용한다. npm build 또는 Gradle 직접 호출을 공식 전체 경로와 동등하게 취급하지 않는다.
4. Capacitor sync 후 추적 Gradle diff를 확인한다. 다른 작업의 변경을 되돌리거나 commit에 섞지 않는다.
5. 최종 APK/AAB의 package·version·서명 인증서·API·광고 설정·웹 자산을 검사한다. 소스/dist 검사로 대체하지 않는다.
6. commit/변경 상태, 빌드 종류, 설정 출처(값 제외), 도구 버전, 아티팩트 SHA256, 실제 기기·외부 테스트 결과를 해당 실행 계획에 남긴다.
7. 배포/Play publication은 별도 승인 범위에서 진행한다. 실제 revision과 렌더링·기능을 확인하고 미검증 외부 영역을 남긴다.

기존 파일의 존재나 수정 시각만으로 최신 빌드라고 판단하지 않는다. 빌드 종류와 설정을 먼저 확인하고 최종 아티팩트와 해당 빌드의 웹 자산을 비교한다. 차이를 곧바로 오래된 소스라고 단정하지 않는다.

## Backend 배포와 복구

render.yaml은 backend와 다섯 DB의 persistent disk 경로를 정의한다. requirements.txt는 버전 고정이 없고 repository 내 CI workflow는 발견하지 못했다(M4). 외부 자동 배포 설정은 미검증이다. branch push가 배포를 촉발할 수 있는지 확인한다.

현재 시작 명령은 backend release validator를 강제하지 않는다. /healthz의 ok와 revision은 생존/출처 확인이며 DB·OAuth·결제·AI 준비 완료 증거가 아니다.

데이터 변경 전 [DATA](DATA.md)의 백업·schema 호환·복원 계획이 필요하다. 코드 rollback이 데이터 rollback을 보장하지 않는다. multi-worker/인스턴스 확장은 메모리 티켓·중복 방지·lock을 포함해 독립 설계·review를 수행한다.

실제 Render 설정, Play version/signing, 기기 업데이트, 복원 절차는 확인 결과가 없으면 미검증이다. 문서 작업으로 출시 준비 완료를 선언하지 않는다.
