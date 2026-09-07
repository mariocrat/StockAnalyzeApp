# StockBoda Development Workflow

담당: 작업 범위·thread/worktree·실패 처리·review·Git.
근거: [AGENTS](../AGENTS.md), [실행 계획](exec-plans/README.md), [검증 명령](../scripts/verify_project.ps1).
아래는 도입하는 운영 규칙이며 모든 규칙이 자동화되었다는 뜻은 아니다.

## 시작

실제 작업 위치에서 다음을 읽기 전용으로 확인한다.

```powershell
git --no-optional-locks rev-parse --show-toplevel
git --no-optional-locks branch --show-current
git --no-optional-locks rev-parse HEAD
git --no-optional-locks status --short --untracked-files=all
git --no-optional-locks worktree list
```

요청의 목적·완료 기준·허용 파일/행동·제외 대상을 정한다. 기존 staged/unstaged/untracked 변경을 구분하고 보호한다. 작업 제목·예전 경로·다른 worktree 상태를 현재 사실로 삼지 않는다.

동일 파일에 기존 변경이 있으면 필요한 hunk만 다룬다. 모르는 변경을 청소하거나 맞춰 고치지 않는다. 실제 범위가 예상과 다르면 의존하는 변경 전에 보고한다.

정확한 대상과 데이터 손실 영향을 명시적으로 승인받지 않은 상태에서는 broad `git clean`, working-tree reset/restore로 기존 변경 폐기, recursive delete, database 삭제, app uninstall 또는 app data clear를 수행하지 않는다. 이 제한은 승인된 범위의 일반적인 파일 편집을 막지 않는다.

## Thread와 worktree

한 thread는 하나의 목적과 하나의 확인된 worktree를 기본으로 한다. 서로 다른 기능이 같은 파일을 수정할 때 담당 범위와 통합 순서를 명시한다. 다른 thread의 미완성 작업을 승인된 결과로 취급하지 않는다.

큰 기능은 별도 branch/worktree를 권장하되 생성·전환·통합은 승인 범위에 따른다. 현재 worktree 목록은 실행 시 확인하고 정적 목록을 정본에 복제하지 않는다.

Worktree는 Git 파일 작업을 분리할 뿐 process 환경·포트·절대 DB 경로·외부 서비스는 격리하지 않는다. StockBoda의 큰 App/TradingJournal/access_control 파일과 생성 Gradle 파일은 충돌 가능성을 특히 확인한다.

새 thread에 넘길 때는 경로·branch·HEAD·기존/새 변경·plan·실제 검증·미검증·다음 한 단계를 전달한다.

## Plan과 독립 review

다음은 구현 전에 persistent execution plan을 작성한다.

- 큰 기능, 여러 subsystem의 계약 변경.
- DB/schema/삭제, auth/OAuth, 결제/권한, security, 환경 경계, signing/release/배포 식별자 변경.

작은 문구·문서 링크·명백한 저위험 변경은 간단한 작업 설명과 비례한 검증으로 충분하다. 무조건 전체 테스트·별도 branch·독립 reviewer를 요구하지 않는다.

고위험 변경은 구현자와 구분되는 독립 review로 실제 diff·테스트·실패/복구·미검증을 평가한다. reviewer는 읽기 전용을 기본으로 하고 코드 수정 권한을 추정하지 않는다. 별도 agent/thread 생성도 요청 또는 적용 지침의 권한 범위 안에서 한다.

## 두 번 실패 규칙

같은 원인·가정에 의존하는 material approach가 두 번 실패하면 세 번째 반복을 중단한다. 표현만 바꾼 명령은 새 접근이 아니다.

실패 단계, 두 시도의 실제 오류, 확보한 evidence, 원인 가설, 변경 파일·Git 상태, 다른 접근과 기대 관측을 보고한다. shell quoting·권한·도구 실행 실패와 제품 코드 실패를 구분한다.

다른 접근이 이미 승인된 범위에서 가능하면 계속한다. 필요한 권한이나 사용자만 정할 수 있는 선택이 있으면 이유와 출처를 설명하고 기다린다. 오류를 숨기거나 테스트를 약화시켜 통과시키지 않는다.

## 실행·검증·완료

명령의 파일/DB/네트워크 부작용을 먼저 확인한다. safe GET이라는 이유만으로 callback이나 getter를 실행하지 않는다. production은 개발·테스트 환경으로 사용하지 않는다.

[TESTING](TESTING.md)의 수준에 따라 static/unit/HTTP/artifact/device/external 결과를 나눈다. 실행하지 않은 build나 실기기 동작을 통과로 적지 않는다. 요구되는 검증이 불가능하면 완료 기준 중 남은 부분을 명시한다.

사용자에게 변경 내용·이유·실행한 검증·실패·남은 한계·현재 branch/HEAD/status·다른 worktree 영향 여부를 보고한다. 문서화가 runtime finding 해결을 뜻하지 않는다.

## Commit과 production 권한

구현 승인은 stage/commit/push/merge/deploy 승인을 자동 포함하지 않는다. 명시적으로 승인된 Git 작업만 수행한다.

Commit 전에는 승인된 파일 또는 hunk만 stage하고 staged 이름·stat·전체 diff를 확인한다. 미추적 새 파일은 일반 git diff에 나타나지 않으므로 따로 확인한다. 기존 변경을 통째로 포함하는 git add . 같은 광범위 작업을 피한다.

Commit 후 SHA와 최종 status를 확인한다. 다른 worktree를 건드리지 않는다. push가 자동 배포를 일으킬 수 있는지 확인하고 production 변경·Play publication은 별도 승인 범위를 지킨다.
