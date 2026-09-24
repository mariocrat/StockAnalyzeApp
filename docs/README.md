# StockBoda 문서 지도

이 문서 체계는 repository 감사에서 확인한 경계와 승인된 작업 규칙을 정리한다. 현재 HEAD, 실행 결과, 배포 상태는 작업마다 다시 확인하며 문서 도입을 출시 승인으로 취급하지 않는다.

## 정본과 책임

| 문서 | 답하는 질문 |
| --- | --- |
| [ARCHITECTURE](ARCHITECTURE.md) | 어떤 구성요소가 연결되고 어디에서 실행되는가? |
| [PRODUCT_RULES](PRODUCT_RULES.md) | 어떤 사용자 동작과 권한 정책을 유지해야 하는가? |
| [TESTING](TESTING.md) | 무엇을 어떤 환경에서 검증하고 어디까지 완료라고 말할 수 있는가? |
| [RELEASE](RELEASE.md) | 어떤 빌드를 만들며 무엇을 확인해야 배포할 수 있는가? |
| [SECURITY](SECURITY.md) | 인증·비밀값·개인정보·외부 서비스 경계는 무엇인가? |
| [DATA](DATA.md) | 데이터 소유권·schema·삭제·백업·복구는 어떻게 관리하는가? |
| [DEVELOPMENT_WORKFLOW](DEVELOPMENT_WORKFLOW.md) | 작업 범위·thread·worktree·review·commit을 어떻게 운영하는가? |
| [exec-plans](exec-plans/README.md) | 큰 작업을 어떻게 이어받고 완료하는가? |

짧은 작업 규칙은 [root AGENTS.md](../AGENTS.md)에 둔다. 신규 실행 계획은 exec-plans만 사용한다.

## Governance 문서 검증 범위

기존 documentation tests는 이 새 governance 정본을 자동 검증하지 않는다. 일부 테스트는 기존 reference/historical 문서의 특정 문구를 고정한다. 현재 governance 문서는 링크·경로, 필수 section, 문서 간 상호참조와 별도 문서 검증으로 확인하며, 기존 테스트 통과만으로 새 governance coverage가 보장되었다고 판단하지 않는다.

## 사실과 의도를 구분하는 원칙

- **현재 구현:** 코드·설정·실제 실행 증거를 근거로 기술한다.
- **제품 규칙:** 승인된 의도를 설명한다. 코드와 충돌하면 의도 변경이나 코드 변경을 임의로 선택하지 말고 차이를 보고한다.
- **필수 운영 절차:** 앞으로 작업자가 지켜야 할 조건이다. 그 절차를 자동 강제하는 코드가 이미 있다는 뜻은 아니다.
- **미검증/후속 구현:** 실제 device·외부 시스템 또는 별도 코드 작업이 필요하다.
- SDK/의존성/버전/API schema/상품 ID/필수 환경변수의 기계적 목록은 코드·manifest·validator를 확인한다. 문서 수치만 믿고 설정을 바꾸지 않는다.
- 변경된 책임 영역의 정본을 함께 갱신한다. 오래된 보고서의 테스트 개수나 준비 상태를 현재 결과로 재사용하지 않는다.

## 열린 감사 항목

아래 ID는 governance 도입 전 기술 감사의 finding과 연결된다. 감사 기준은 baseline HEAD `fc94bfca0739d54108c1dbdc9961de928e6f890a`, audit date `2026-09-07`이며 repository/static review 중심이다. Android device, external service, production runtime 검증은 포함하지 않았다. 관련 코드가 변경되면 해당 finding을 현재 revision에서 재검증한다. 문서 구축만으로 제품 결함을 해결 처리하지 않는다. P0는 안전한 기능 실행·검증 기반의 우선순위이며 모든 문서/순수 함수 작업을 금지하는 뜻이 아니다.

| ID | 우선순위 / 영향 | 확인된 상태와 후속 작업 | 담당 문서 |
| --- | --- | --- | --- |
| H1 | P0 / High | debug wrapper가 release 웹 설정을 사용하는 경로. 안전한 개발 API/계정/빌드 경계 구축 필요 | RELEASE |
| H2 | P0 / High | 환경 누락 시 개발 접근과 익명 매매 경로가 열림. 명시적 환경·시작 검증 필요 | SECURITY |
| H3 | P0 / High | 공통 env fallback과 매매 DB 별도 loader 불일치. 환경 로딩 통합 필요 | DATA |
| H4 | P0 / High | 일부 테스트의 DB·환경 격리 불완전. 전체 DB/cache/외부 통신 격리 필요 | TESTING |
| H5 | P1 / High | 일반적인 기존 schema upgrade·복원 체계 부족, DB별 순차 계정 삭제. 관련 배포 전 보완 | DATA |
| H6 | P1 / High | OAuth 티켓만으로 세션 교환 가능. 로그인 시작 앱 결합 필요; 실제 가로채기 미검증 | SECURITY |
| H7 | P1 / High | 영속 차감과 메모리 AI 중복 방지 분리. 재시작 후 미완료 요청 복구 필요 | DATA |
| M1 | P1 / Medium | AI 요청 제한이 try 밖에 있어 pending 상태 잔류 가능. 거절 후 재시도 회귀 검증 필요 | TESTING |
| M2 | P1 / Medium | 비밀값 검사가 기존 설정 설명용 JSON 대입 예시에 반응. 미해결이며 기존 문서·검사기는 별도 remediation에서 처리 | SECURITY |
| M3 | P1 / Medium | 아티팩트와 HEAD/환경의 출처 연결 부족. 비교 시 debug/release 빌드 종류 차이도 고려 | RELEASE |
| M4 | P1 / Medium | Python 의존성 미고정, 저장소 CI workflow 미발견. 재현 가능한 설치·CI gate 필요 | RELEASE |
| M5 | P1 / Medium | export가 매매·복기 각각 고정 건수 한도이며 잘림 표시 없음. 전체 export 계약 보완 | DATA |
| M6 | P1 / Medium | frontend가 읽는 X-Request-ID/Retry-After의 CORS expose_headers 없음. 실제 HTTP 확인 필요 | TESTING |
| M7 | P1 / Medium | Repository 소유 Uvicorn access log, application event 및 error traceback credential hotfix 적용. 일부 429/CORS summary와 Render/proxy/platform log 및 production history는 미검증 | SECURITY |
| M8 | P1 / Medium | localStorage 세션과 Android allowBackup=true. 실제 backup 범위·기기 이동 검증 필요 | SECURITY |
| M9 | P1 / Medium | 공개 일회성 분석 제한과 X-Forwarded-For 신뢰 경계 점검 필요; 실제 공격 미검증 | SECURITY |
| M10 | P2 / Low | 과거 문서 경로·명칭·연락처·준비 상태 혼재. 이 지도에서 상태만 구분, 기존 본문·링크 변경은 별도 승인 후속 | 본 문서 |

실제 production 침해·데이터 손실·중복 차감은 확인하지 않았다. 각 항목 해결 시 해당 diff, 검증 수준, revision을 관련 실행 계획에 남기고 이 표의 상태를 갱신한다.

## 기존 문서의 상태와 사용법

기존 문서 본문은 이번 단계에서 수정하거나 자동 폐기하지 않는다. 새 작업 규칙은 위 정본을 따르고, 예전 operational 절차는 코드·설정과 대조한 세부 참고자료로 사용한다. 기존 문서에 새 링크가 있다고 가정하지 않는다.

| 기존 자료 | 상태 | 사용 기준 / 새 정본 |
| --- | --- | --- |
| [plans/README](plans/README.md) | Reference — 기존 계획 호환 | 지정된 기존 계획은 원래 worktree에서 유지. 신규 위치는 [exec-plans](exec-plans/README.md) |
| [quick_verify](quick_verify.md) | Reference — 과거 검증 안내 | 명령의 부작용과 격리 조건은 [TESTING](TESTING.md) 우선 |
| [manual_test_guide](manual_test_guide.md) | Reference — 세부 시나리오 | [TESTING](TESTING.md), [SECURITY](SECURITY.md)와 현재 코드 대조 |
| [release_preparation_checklist](release_preparation_checklist.md) | Reference — 기존 checklist | 과거 체크 상태는 현재 통과 증거 아님. [RELEASE](RELEASE.md), M2 별도 후속 |
| [project_owner_dashboard](project_owner_dashboard.md) | Historical — 준비 상태 스냅샷 | 현재 운영/Console 준비 상태로 재사용하지 않음 |
| [security_deployment_plan](security_deployment_plan.md) | Reference — 과거 설계 | [SECURITY](SECURITY.md), [DATA](DATA.md)와 충돌하면 보고 |
| [render_deployment_guide](render_deployment_guide.md) | Reference — 외부 콘솔 절차 | [RELEASE](RELEASE.md), 실제 Blueprint/외부 상태/승인 확인 후 사용 |
| [android_oauth_test_guide](android_oauth_test_guide.md) | Reference — production 연결 QA | 격리된 개발 절차 아님. [RELEASE](RELEASE.md), [TESTING](TESTING.md) 확인 |
| [android_admob_qa_test_guide](android_admob_qa_test_guide.md) | Reference — 외부 서비스 QA | 테스트 광고·등록 기기 여부와 API/data 격리를 구분 |
| [ai_review_monetization_plan](ai_review_monetization_plan.md) | Reference — 제품 의도와 구현 이력 혼재 | [PRODUCT_RULES](PRODUCT_RULES.md), 서버 정책·승인된 의도 대조 |
| development_history*.md, superpowers/ | Historical — 과거 결정·구현 | 현재 기능 완료나 최신 검증 근거로 사용하지 않음 |

기존 문서의 경로·문구·링크를 정비하거나 H1~H7/M1~M10을 수정하는 일은 별도 작업이다. 이 지도는 사실·의도·미검증을 구분하기 위한 것이며 기존 코드·configuration·테스트 문제를 해결하지 않는다.
