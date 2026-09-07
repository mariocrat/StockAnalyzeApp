# StockBoda Execution Plans

담당: 큰 작업과 고위험 변경의 지속 가능한 계획·검증 기록.
규칙: [AGENTS](../../AGENTS.md), [개발 workflow](../DEVELOPMENT_WORKFLOW.md).

## 위치와 lifecycle

- 신규 계획은 active/<기능 또는 작업명>.md에 둔다. 한 계획에는 한 workstream만 담는다.
- active와 completed 디렉터리의 .gitkeep은 빈 디렉터리 보존용이다.
- 요구된 구현·검증·review가 끝나고 미완료 사항의 상태를 명확히 정리한 계획만 completed로 옮긴다.
- 필요한 device/external 검증이 남았다면 해당 기능을 완료로 표시하지 않는다. 문서 작업의 완료와 그 문서가 추적하는 제품 문제의 해결은 구분한다.
- 이전 docs/plans 계획은 원래 경로·worktree에 유지한다. 사용자가 지정한 기존 계획을 읽고 Git 상태와 대조한다. 임의 복사·이동·다른 worktree 수정은 하지 않는다.
- read-only 감사·review에는 파일 생성이나 진행 상황 갱신 의무가 없다.

## 필수 구조

아래 구조를 필요한 계획 파일에 사용한다. 실제 값은 현재 작업에서 확인한다.

### Goal

사용자 목적과 검증 가능한 완료 기준.

### Scope

허용 파일/행동과 보호할 기존 변경. 실행 환경·branch·기준 HEAD.

### Decisions

확정된 제품·기술 결정, 기본값, 변경할 수 없는 외부 계약. 미확정 의도와 구현 사실을 구분.

### Current Status

구현·검증·review·device/external 상태를 나눈 체크리스트. 코드 작성만으로 검증 완료를 표시하지 않음.

### Verification

실행 날짜, 기준 revision/working diff, 실행 위치와 명령, 결과, 증거 수준. 실제 secret·고객 데이터·외부 token을 포함하지 않음.

### Remaining / Unverified

미완료 작업, 알려진 위험, 검증 불가 이유. 별도 후속 작업으로 넘겼다면 범위와 이유를 명시하며 조용히 삭제하지 않음.

### Next Step

이어받는 사람이 수행할 다음 한 단계. 필요한 권한·선행 조건이 있으면 함께 명시.

### Out of Scope

이번에 하지 않을 기능·refactor·Git·production 작업.

## 갱신과 재개

의미 있는 구현 또는 검증 단계 후 실제 상태로 갱신한다. 상세 대화의 복사본 대신 결정과 증거를 남긴다.

재개 시 현재 HEAD/diff와 계획 기준을 대조한다. 이미 해결된 문제를 재현 없이 다시 수정하거나 과거 검증을 현재 결과로 재사용하지 않는다. 같은 접근 두 번 실패 규칙은 workflow를 따른다.
