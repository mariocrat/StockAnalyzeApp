# OAuth logout and relogin

## Goal

Kakao/Naver 로그아웃 후 로그인 버튼이 다시 활성화되고, 같은 provider로 새 OAuth 로그인을 시작할 수 있게 한다.

## Scope and design

- 작업 위치: `fix/oauth-relogin`, 기준 HEAD `e04fa20e8e3dfa9230dd53d192875f5a8c8cc2cc`.
- 로그아웃 시 저장된 세션과 OAuth 임시 state, 화면의 로컬 이용권 상태를 정리한다.
- 폐기된 세션 토큰을 이용권 조회에 다시 사용하지 않는다. 로그인 loading을 먼저 해제하고, 개발용 토큰이 있을 때만 이용권 조회를 비차단으로 시작한다.
- 이용권 조회는 시작 시점의 인증 세대값을 캡처한다. 이후 인증 세션이 바뀌었다면 지연된 성공·실패 결과 모두 로컬 이용권에 반영하지 않는다.
- Debug OAuth scheme을 쓰는 Vite 빌드는 Kakao/Naver 공개 client ID와 redirect URI 4개가 모두 있어야 진행한다.
- 기존 callback 및 ticket 검증 계약, backend, AI 복기, PDF 복기, Debug preview는 변경 범위 밖이다.

## Current status

- 작업 branch의 `TradingJournal.jsx`에는 logout 관련 hunk만 이식했다.
- `vite.config.js`에는 Debug scheme 누락 설정 guard만 추가했다.
- OAuth 신규 Node 테스트 2개를 공식 `test:*` 및 H4 manifest에 등록했다. 고정 수치 회귀와 검증 문서도 현재 inventory 수로 갱신했다.
- 독립 검증 P2 finding의 개발용 조회/재로그인 경합을 인증 세대값으로 막았고, 수정 결과의 독립 재검증도 승인 완료됐다.
- 대상 자동 검증 및 P2 독립 재검증은 완료됐다. 실제 Android/provider 재로그인 검증은 미실행이다.

## Verification

- 2026-09-24, 기준 HEAD `e04fa20e8e3dfa9230dd53d192875f5a8c8cc2cc`와 현재 미커밋 변경: 공식 Node inventory **20 entrypoint / 160 direct testcase**, 누락·중복·extra 0. 변경 전은 18 / 149였다.
- 신규 `oauth-initial-state` 5개, `oauth-logout` 6개, 기존 `oauth-app-return` 4개: 직접 Node 실행 및 H4 격리 entrypoint 실행 모두 **15 direct PASS / 0 FAIL / 0 SKIP**. P2 지연 응답 4개 nested case도 Kakao/Naver 성공·실패 모두 **PASS**. 새 로그인 이용권 반영 후 이전 요청을 완료시켜 추가 state 쓰기가 없음을 확인했다. 실제 provider·기기는 호출하지 않고 synthetic network/storage를 사용했다.
- Node inventory/coordinator regression **9 PASS**, 검증 문서 회귀 **7 PASS**. 격리 실행의 누락·중복·extra·예상 밖 skip·잔여물은 0이었다.
- 이 worktree에는 `node_modules`가 없어 `npm run lint`는 ESLint 실행 전 실패했다. 동일한 설정 내용과 lockfile을 가진 기존 설치 도구로 현재 변경 JS/JSX 4개 파일의 lint는 통과했다. 전체 frontend lint는 변경하지 않은 `scripts/client-event-log.test.js:152`의 `no-useless-escape` 1건으로 실패했다.
- 전체 TestOnly, BuildChecks, 앱 빌드, 기기/provider 테스트는 이번 단계에서 실행하지 않는다.

## Remaining / next step

- 실제 Android/provider 왕복 검증은 별도 후속 확인으로 남아 있다.
