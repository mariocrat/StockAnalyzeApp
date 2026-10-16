# StockBoda Testing

담당: 안전한 검증 환경, 명령의 부작용, 완료 증거.
근거: [wrapper](../scripts/verify_project.ps1), [coordinator](../tests/run_isolated_tests.py), [manifest](../tests/test_inventory.json).

## 공식 H4 TestOnly

Mode는 반드시 명시합니다. 생략 또는 잘못된 값은 test/build 시작 전에 실패합니다.
Python 3.11+와 Node 24+의 승인된 기존 실행기를 **절대경로**로 지정합니다.
PATH fallback이나 worktree .venv 자동 선택은 없습니다. 실행기 부재·상대경로·버전/기능 비호환은 사전 실패합니다.
실행기 및 필요한 Python 의존성 준비는 별도 승인 작업이며 wrapper는 설치하지 않습니다.

```powershell
& "<worktree>\scripts\verify_project.ps1" `
  -Mode TestOnly `
  -PythonPath "<approved absolute python.exe>" `
  -NodePath "<approved absolute node.exe>"
```

위 placeholder는 실제 승인된 경로로 대체합니다. 특정 PC 경로는 계약이 아닙니다.
BAT도 동일한 인자를 그대로 전달합니다. 호출 CWD에 의존하지 않으며 PowerShell exit code를 보존합니다.
Mode 없는 더블클릭 실행은 실패합니다.

```powershell
.\verify_project.bat -Mode TestOnly -PythonPath "<approved absolute python.exe>" -NodePath "<approved absolute node.exe>"
```

TestOnly 호출 구조:
1. 두 실행기의 격리된 compatibility probe.
2. 지정 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py --all`.
3. 같은 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py --node-all --node-executable <approved absolute node.exe>`.
Python coordinator와 module child는 모두 `-I -X utf8`로 실행되어 UTF-8 stdout/stderr를 사용합니다.

2026-10-16 source inventory는 manifest와 testcase declaration에서 재계산한다: Python direct **1079** (108 modules) = baseline **36 / 1005 / 22** (A1/foundation/helper / migrated / OUT) + Stage 1 **16** 별도 cohort.
2026-09-23 historical baseline은 Python direct **464** = **35 / 393 / 22** + Stage 1 **14**였다. 아래 closeout 결과와 구분한다.
Child probe **18**은 direct와 별도 집계합니다.
Node **23 entrypoint / 263 direct testcase**, `test:ai-chart-source`, `test:broker-import`, `test:canonical-review-renderer`, `test:mobile-bundle` 포함.
Manifest/source/execution 누락·중복·extra 및 예상 밖 skip은 실패입니다. Nested evidence는 direct에 중복 합산하지 않습니다.

일반 guarded module은 120초, coordinator self-test는 600초의 hard timeout을 유지합니다. 관측된 timeout module에만 별도 제한을 적용합니다: route 38-case mutation 회귀는 H4 계측 158.0초·공식 실행 234.4초에 근거해 360초, cache 14-case 회귀는 공식 실행 77.3초/120초 timeout·H4 계측 80.6초에 근거해 180초입니다. TimeoutExpired는 계속 실패이며 case coverage·환경/patch restoration·소유 root cleanup 판정은 완화하지 않습니다.

Raw `unittest discover`는 공식 경로가 아닙니다. Target import 전에 필요한 A1 boundary를 설치하는 승인 coordinator를 사용합니다.
`tests/run_phase_a_tests.py`는 deprecated이며 target import 전 **exit 2**로 종료합니다.
`tests/diagnose_phase_a_probe.py`는 공식 inventory/실행 대상이 아닙니다.

TestOnly 중 실제 private env/credential/HOME/keystore 접근, external provider/network/DNS,
npm install/package download, production build, Gradle/keytool, deploy/signing은 금지됩니다.
Child env는 정제하고 HOME/TEMP는 test-owned 경로를 사용합니다. Repo/persistent write는 허용하지 않습니다.
Test infrastructure의 명시적 Python/Node child와 승인된 synthetic socketpair 계약은 유지합니다.
Billing fixture는 integrity 검증된 13.17.2 배포물의 고정 source snapshot이며 runtime download는 없습니다.
Canonical review renderer 테스트는 현재 로컬에 설치된 React 19.2.6의 지정 파일만 hash와 lock version 검증 후 H4 소유 임시 경로로 복사해 실제 React server render를 실행합니다.
이는 실제 설치된 plugin이나 Android 산출물 검증을 대신하지 않습니다.

## BuildChecks는 별도 경로

```powershell
& "<worktree>\scripts\verify_project.ps1" -Mode BuildChecks -PythonPath "<approved absolute python.exe>" -NodePath "<approved absolute node.exe>"
```

BuildChecks에만 기존 네 검사를 둡니다:

- Backend compile check: `python -m compileall backend` (bytecode 쓰기).
- Tracked secret scan: `scripts/check_no_tracked_secrets.py` (추적 파일 검사).
- Frontend lint: 승인 Node 옆의 `npm.cmd run lint`.
- Frontend production build: 같은 `npm.cmd run build` (dist 생성).

기존 VITE_APP_NAME 미설정 시 StockBoda 기본값은 유지하고 CWD/env를 종료 시 복구합니다.
기존 테스트 단계는 TestOnly로 이동했으며 BuildChecks 통과는 테스트 통과가 아닙니다.
BuildChecks는 H4 격리 경계가 아니고 host env 및 기존 dependency tree를 사용할 수 있습니다.
npm lifecycle/build 설정의 부작용을 먼저 검토해야 하며 필요한 의존성 부재 시 임의 설치하지 않습니다.
이 wrapper는 release/deploy/signing 승인이나 Android build 경로가 아닙니다.
기존 일반 Vite build를 release 전용 workflow로 확장하지 않았습니다.

## 검증 상태와 범위

아래 closeout 결과는 2026-09-23, 검증 HEAD `9fff3f3e84ce26f663f41619d37a4eb101bfbc32`의 historical baseline입니다. 현재 source inventory는 Python 1079 direct / 18 child probe, Node 23 / 263입니다. 이전 Phase 6 전체 TestOnly 결과는 [당시 실행 계획](exec-plans/active/phase6-testonly-blockers.md), 현재 Slice 6 focused 통합 검증은 [migration plan](exec-plans/active/review-display-v2-migration.md)에 구분해 기록합니다.

### Phase 2D-4 client display compatibility gate — 2026-10-05

- 사용자가 Phase 2C 및 Phase 2D-1/2/3의 독립 승인을 통보하고 Phase 2D-4만 승인했다. 아래 이전 단계의 HOLD/검증 수치는 historical evidence다. 구현·검증·파일 목록은 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. Phase 2D-4 독립 검토는 대기 중이다.
- Frontend의 `reviewDisplayContract.js`가 단일 header/value/helper를 소유한다. 실제 AI execute, history list/detail, AI history 포함 account export의 네 요청에만 선언한다. Backend `review_display_client.py`는 기존 display schema constant를 사용하며 인증·권한을 부여하지 않는다. 각 production route의 첫 검사에서 정확한 단일 `review-display.v1`만 통과하고 누락/다른 version/공백/대소문자/parameter/comma/중복 field line은 고정 HTTP 426 `unsupported_review_display_client` / `AI 복기를 표시하려면 앱을 업데이트해 주세요.`로 거절한다. Raw header/error 값은 표시 메시지에 반사하지 않는다.
- H4 안에서 추가 dependency 없이 실제 ASGI app에 request/response 메시지를 전달했다. Basic/advanced execute의 `gate → idempotency lookup → quota charge → model` 순서와 unsupported lookup/charge/refund/model/provider/history write **0**을 관측했다. 기존 cache가 있어도 unsupported에게 content **0**, cache/wallet/history 불변이다. Supported replay는 동일 snapshot을 반환하고 추가 효과 **0**이다. Sealed approval 없음/invalid approval/wire 변경 cache는 기존 canonical admission에서 fixed 500으로 fail-closed하며 raw/legacy 재구성·재과금·환급이 없다.
- History list/detail/export는 gate 후 기존 whole-record adapter를 계속 통과한다. Unsupported는 history read/adapter/provider/billing **0**이며 supported canonical/legacy/unsafe의 canonical/adapted/unavailable 결과를 원래 adapter로 얻는다. Synthetic history DB bytes/rows는 불변이며 migration/backfill 없다. 기존 HTTP audit middleware의 session 조회와 실패/exception event 기록은 유지한다; zero-effect 증거는 요청된 replay/quota/model/provider/history 경계에 해당한다.
- 실제 production JSX/loader/export handler와 실제 header helper를 Node/React에서 실행했다. 네 AI 요청의 정확한 header, auth/idempotency 유지, 일반 journal/chart/review/data-summary header 미적용, 고정 update notice, old-server snapshotless live/history의 unavailable UI 및 legacy summary fallback **0**을 확인했다. Exact body/strong/Unicode/whitespace, 16 invalid body + 66 invalid chart 조합, whole-record/race 방어와 post-AI charts-once **0**의 Phase 2D-1/2/3 회귀도 유지한다.
- 최종 focused Python **433/433 PASS**(28 explicit modules, 새 ASGI gate 11, 기존 route 26/adapter 44와 Phase 2C/2B, Python coordinator/storage/docs 포함), Node **69/69 PASS**(production 39/cross-contract 11/canonical 10/parser 7/idempotency 2), Node coordinator **9/9 PASS**다. 25 guarded Python report의 unexpected **0**, 3 coordinator report의 null counters 및 nested 계약 통과, 모든 report restoration/patch restoration/cleanup true, 최종 inventory issues/FAIL/ERROR/SKIP **0**이다. Inventory-only는 Python **790 direct / 95 modules / 18 child probes**, baseline 35/718/22 + Stage 1 15; Node **23 entrypoints / 223 direct**, missing/duplicate/extra/dependency issues **0**이다. 이는 전체 suite 실행 수치가 아니다.
- 초기 검증 장애는 httpx 미설치, handoff path 초기화 전 import, imported TestCase의 중복 discovery, audit session 조회를 side-effect spy에 포함한 계측, Node AST binding 충돌, 이전 Python inventory 상수였다. Dependency 설치나 production boundary 완화 없이 준비·계측·inventory를 수정했고 영향받은 검증을 재실행했다. 전체 TestOnly/BuildChecks, browser/CSS/device, live network/private DB, DB migration/backfill, 배포/Play 및 Git mutation은 실행하지 않았다. 기존 22개 scoped 파일 변경 + 새 파일 3개, 나머지 시작 파일 **348/370** byte-identical이며 다른 worktree는 변경하지 않았다. Branch/HEAD 유지, staged **0** / tracked unstaged **29** / untracked **36**.

### Phase 2D-3 canonical exact renderer production transition — 2026-10-05

- Phase 2C/2D-1/2D-2는 사용자 통보에 따라 독립 승인됐다. Live AI와 history detail 본문은 같은 `CanonicalReviewRenderer`가 승인된 `display_snapshot`을 직접 표시한다. Production `AiReviewSummary`, `ReviewInlineText`, `reviewDisplayText`, `aiReviewFormat` 의존성을 제거한다. Backend compatibility `summary`와 기존 parser 코드는 유지한다.
- 기존 `validateReviewDisplay`를 변경 없이 재사용하며 chart header/tab/card/DOM tooltip에는 명시적 expected surface를 전달한다. Text/strong run, block 순서와 separator를 그대로 표시한다. Canvas marker는 기존 plain canonical text를 그대로 받는다. Invalid/missing body는 고정 unavailable UI와 빈 chart/card source; transport 실패는 별도 고정 frontend 안내다. Whole-record history admission과 최신 detail request guard, post-AI charts-once 0 계약을 유지한다.
- [실제 production Node/React 회귀](../frontend/scripts/ai-review-chart-source.test.js)는 원래 live JSX, history/detail loader, export handler와 chart effect를 실행한다. H4 backend child의 실제 synthetic route/storage/detail/export/cache/replay 결과가 필수다. DOM-root/chart API observer와 React server renderer 증거이며 browser/CSS/device 최종 gate가 아니다. Clone parser/renderer는 추가하지 않는다.
- Whole-record adapter가 승인한 옛 chart/card/tooltip `display_snapshot`은 기존 `body` surface를 그대로 사용한다. 새 projection의 전용 chart surface와 각각 명시적으로 구분하며 문서를 변경하거나 surface 검사를 완화하지 않는다. 최초 Node legacy tooltip 실패 1개는 이 기존 계약 차이로 수정됐다.
- 최종 focused Python **409/409 PASS**(26 modules), Node **62/62 PASS**(production 34/cross-contract 11/canonical 10/parser 7), Node coordinator **9/9 PASS**다. Normal basic/advanced 및 plain/strong 여섯 synthetic route 결과의 live/saved/detail/export/cache/replay exact body/strong identity, `[0,5)` strong, 16 invalid body + 정상 summary fallback 0, 기존 66 invalid chart 조합과 history 전환/race를 확인했다. Post-AI charts-once 0, replay 추가 model/provider/market/charts-once/charge/refund/history write 0, guarded unexpected/inventory issues/FAIL/ERROR/SKIP 0, restoration/patch restoration/cleanup true다. Source inventory Python 779/94/18와 Node 23/218은 전체 suite 실행 수치가 아니다. 기존 15개 scoped 파일 변경 + test-only DOM evidence helper 1개 추가, 나머지 시작 파일 354/369 byte-identical이다. Backend production bytes와 compatibility wire는 유지한다. Branch/HEAD 유지, staged 0 / tracked unstaged 26 / untracked 33; 독립 Phase 2D-3 검토 가능하며 client version/header gate와 Phase 2D-4는 HOLD다.
- Canonical/compatibility parser, Phase 2D-1/2C/2B, Node/Python coordinator/storage/docs와 inventory/whitespace만 focused 실행한다. 실제 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks, browser/CSS/device/live network/private DB, migration/backfill, client support header/gate와 Phase 2D-4는 실행하지 않는다. 구현 증거를 보고한 뒤 독립 검토를 기다린다.

### Phase 2D-2 P2 limited corrections — 2026-10-05

- 두 finding만 수정한다. Production `openReviewHistoryDetail`은 매 요청마다 순번을 증가시키고 이전 detail/ticker/error를 즉시 비운다. 최신 순번만 success/error/finally에서 state를 변경한다. 선택 버튼 비활성화에 의존하지 않는다.
- `aiReviewChartSource`는 [기존 frontend canonical validator](../frontend/src/components/CanonicalReviewRenderer.js)의 `validateReviewDisplay`를 재사용한다. 같은 검사에 expected surface를 명시해 header/tab/marker label/nullable tooltip/card 문서를 전부 검증한다. Unknown version/field, malformed block/run, canonical text mismatch와 잘못된 surface 중 하나라도 있으면 chart/card 전체가 빈 source다. 승인 문서를 재작성하거나 raw/general/history metadata로 복구하지 않는다. Renderer는 기존 body만 렌더하며 production에 연결하지 않는다.
- [Production Node/React regression](../frontend/scripts/ai-review-chart-source.test.js)은 원래 detail/AI loader와 JSX를 실행한다. A/B 응답 역전, stale failure/finally 및 빠른 연속 선택의 모든 state 변경을 관찰하고, 다섯 document 위치의 손상 matrix와 invalid→valid/valid→invalid 전환을 검증한다. H4 복사 목록과 hash에 실제 canonical contract dependency를 포함한다.
- Phase 2D-1 whole-record adapter, Phase 2C/2B, coordinator/storage/docs, 선택 Node entrypoint/coordinator와 inventory/whitespace만 실행한다. 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 아래 2026-10-04 결과는 수정 전 historical evidence다. 전체 TestOnly/BuildChecks, browser/device/live network/private DB는 실행하지 않으며 Phase 2D-3는 HOLD다.
- 최종 focused Python **409/409 PASS**(26 modules, route 26/adapter 44 포함), Node 선택 **52/52 PASS**(chart 24/cross-contract 11/canonical 10/format 7), Node coordinator **9/9 PASS**다. A/B 세 순서와 빠른 연속 선택에서 stale state 변경/이전 chart/card 0, 다섯 문서 위치의 66 corrupt 조합에서 chart/card render 0, 정상 복구/이전 content 제거를 확인했다. Immediate/storage/detail/cache/replay identity, post-AI charts-once 0, unsafe/error fallback 0과 replay 추가 model/provider/market/charts-once/charge/refund/history 0도 유지한다. Guarded unexpected/inventory issues/FAIL/ERROR/SKIP 0, restoration/patch restoration/cleanup true다. 실제 inventory는 Python 779/94/18, Node 23/208이며 전체 suite 실행 수치가 아니다. 두 finding 수정 12개 파일 이외 시작 파일 357/369는 byte-identical이다. Branch/HEAD 및 staged 0 / tracked unstaged 26 / untracked 32 유지; Phase 2D-2 P2 독립 재검토를 위해 보고 후 대기한다.

### Phase 2D-2 live AI review chart source — 2026-10-04

- Phase 2C와 Phase 2D-1/P2는 사용자 통보에 따라 독립 승인됐다. Production AI response의 `chart_display_snapshot`은 sealed envelope의 `charts`/`chart_cards`만 복사한다. 운영 access/history ID/replay flag는 이 projection에 들어가지 않는다. 오류에는 빈 chart surface만 허용한다.
- AI 완료 이후 `loadReviewContextForTrades`는 `/review-once`의 산술 통계만 갱신하며 `/charts-once`를 호출하지 않는다. 일반 `loadChartReview`와 명시적 과거 매매 복원은 기존 pre-AI 조회를 유지한다. AI 결과 chart는 일반 chart state를 읽지 않으므로 늦게 완료된 일반 조회도 교체할 수 없다.
- Immediate/history/replay는 같은 projection을 사용하고 header/tab/card/marker/tooltip의 승인 canonical text를 그대로 읽는다. Safe legacy history는 동일한 whole-record adapter가 승인한 기존 chart/tooltip documents만 사용한다. Unsafe/unknown/corrupt/new projection 오류는 row 전체를 unavailable로 반환하며 별도 chart fallback은 없다.
- [Production route](../tests/test_review_route_compatibility.py)와 [history adapter](../tests/test_review_history_adapter.py) focused 검증, [실제 frontend Node/React](../frontend/scripts/ai-review-chart-source.test.js) 검증을 추가한다. Frontend 테스트는 H4 backend child가 생성·저장·조회·replay한 실제 합성 응답을 필수로 받는다. TypeScript AST로 원래 production loader/view와 JournalTradeChart를 실행하며 React server render, DOM/차트 API 관찰자를 사용한다. Clone 구현이나 fixture 기대값 fallback은 없다.
- Focused Phase 2C/2B/coordinator/storage/docs, 선택 Node entrypoint/coordinator, Python/Node inventory와 whitespace를 실행한다. 실제 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. Full TestOnly/BuildChecks, live network/private DB, browser/device/CSS 최종 검증과 Phase 2D-3 이후는 실행하지 않는다.
- 최종 focused Python **409/409 PASS**(26 modules, route 26/adapter 44 포함), Node 선택 **40/40 PASS**(new production chart 13 포함), Node coordinator **9/9 PASS**. 정상 response/storage/detail/export/cache/replay chart identity, 별도 synthetic chart 차이, 늦은 일반 조회, metadata 불변성, 오류/unsafe history fallback 0과 replay 추가 model/provider/market/charts-once/charge/refund/history 0을 확인했다. Guarded unexpected 0, restoration/patch restoration/cleanup true, 최종 inventory issues/FAIL/ERROR/SKIP 0이다. Source inventory는 779/94/18 및 Node 23/196이며 전체 suite 실행 수치가 아니다. Branch/HEAD 유지, staged 0 / tracked unstaged 26 / untracked 32; 독립 Phase 2D-2 검토를 위해 보고 후 대기한다.

### Phase 2D-1 P2 semantic section admission — 2026-10-04

- 기존 adapter는 summary와 basic/advanced를 merge한 뒤 검증해 정상 duplicate가 원본 unknown/malformed 값을 숨길 수 있었다. 현재 semantic schema의 원본 section별 exact key, nested shape, scalar/list/object type을 merge 전에 검사하고 중복 key는 값이 같아도 거절한다. 검증되지 않은 원본을 삭제하거나 덮어서 승인하지 않는다. Canonical body 존재도 raw section 검사를 면제하지 않는다.
- [Adapter focused tests](../tests/test_review_history_adapter.py)의 새 6 cases는 두 P2 재현을 basic/advanced 및 canonical 유/무 조합으로 list/detail/export에서 검사한다. 정상 canonical/legacy, 중복 값, 원본 shape/type 오류, 3회 반복 read, synthetic DB row/file bytes와 입력 사본 불변성, model/provider/live chart/billing/history write 호출 0을 함께 검사한다. 기존 unsafe/unknown matrix와 Phase 2C/coordinator/storage/docs도 focused 실행한다.
- 검증 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 아래 최초 Phase 2D-1 결과는 수정 전 historical evidence다. 전체 TestOnly/BuildChecks, private DB/live network/browser/device, frontend production 및 Phase 2D-2 변경은 없다.
- 최종 focused Python **281/281 PASS**(15 modules, adapter 39 포함), 선택 Node **27/27 PASS**, Node coordinator **9/9 PASS**다. 두 P2 재현의 모든 list/detail/export 조합은 fail-closed이며 canonical/legacy controls와 원본 DB/호출 불변성이 통과했다. Guarded unexpected 0, restoration/patch restoration/cleanup true, final inventory issues/FAIL/ERROR/SKIP 0이다. 실제 inventory 770/18 및 Node 22/183은 전체 실행 수치가 아니다. 시작 파일 358/366과 frontend 135개는 byte-identical이며 staged 0 / tracked unstaged 24 / untracked 29를 유지한다. 독립 재검토를 위해 보고 후 대기한다.

### Phase 2D-1 whole-record history read adapter — 2026-10-04

- 사용자는 Phase 2C 전체 독립 승인을 알렸으며 legacy history read-time adapter만 승인했다. List/detail/export는 전체 DB row를 같은 [adapter](../backend/core/review_history_adapter.py)에 전달한 뒤 list metadata를 투영한다. Canonical body가 있어도 별도 chart/card/tooltip/trade/memo/metadata와 unknown nested 필드를 검사한다.
- 현재 저장 schema의 metadata와 다섯 JSON snapshot을 닫힌 필드/타입으로 검사한다. 지원 canonical은 version/shape/content/A1 wire 일치를 검사하고 body를 유지한다. 지원 legacy summary 또는 trade-review.v1은 memory에서만 canonical body로 변환하고 summary는 body에서 생성한다. Legacy semantic은 별도 표시 정본으로 반환하지 않는다. Canonical 오류와 unsupported legacy에는 raw fallback이 없다.
- 고정 표시 불가 결과는 원문 metadata/chart/access와 복원용 trade를 반환하지 않는다. Partial trade도 복원 대상으로 제공하지 않는다. 지원 legacy body는 A1 paragraph/text/strong grammar를 만족해야 하며 예약 markup/section/MA token 등의 unsupported body는 fail-closed한다.
- [Focused synthetic test](../tests/test_review_history_adapter.py)는 body-safe/chart-unsafe, 반대 조합, tooltip, name/memo 및 split text, unknown field/version, malformed canonical/JSON, DB row value/file byte 불변성, copy ownership과 반복 read를 검사한다. Read connection은 `mode=ro`이고 SELECT만 수행하며 DB/parent가 없을 때 생성하지 않는다. Adapter의 model/provider/live chart/charge/refund/storage/event 호출은 금지 mock으로 검사한다.
- 승인 Python의 `-I -X utf8 -B tests/run_isolated_tests.py`에 history adapter와 Phase 2B/2C, Python coordinator/storage/docs module을 명시한다. Node는 선택된 A1 cross-contract/canonical renderer/format entrypoint 및 `--node-regressions`만 실행한다. 실제 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks, browser/device/live network/private DB는 실행하지 않는다. Frontend production 변경 0; Phase 2D-2 이후는 대기한다.
- 최종 focused Python **394/394 PASS**(26 modules, adapter 33 포함), Node 선택 entrypoint **27/27 PASS**, Node coordinator **9/9 PASS**. Primary guarded unexpected 0, 모든 report restoration/patch restoration/cleanup true, inventory issues/FAIL/ERROR/SKIP 0이다. SQLite URI의 실제 경로를 검사하도록 H4를 보완했으며 root 밖/다른 URI option은 연결 전에 차단된다. Source inventory는 764 direct/18 child probes와 Node 22/183이며 전체 suite 실행 수치가 아니다. Frontend 135개는 시작 시점과 byte-identical이다. Branch/HEAD 유지, staged 0 / tracked unstaged 24 / untracked 29; Phase 2D-1 독립 검토 후속은 보고 뒤 대기한다.

### Phase 2C P2 prompt/admission consistency — 2026-10-04

- 독립 검토 finding 한 건만 수정한다. Advanced terminology prompt는 일봉의 5일/10일/20일 이동평균과 다른 주기의 실제 봉 개수(1분봉 차트의 5개 봉 이동평균)를 자연어로 지시한다. A1 reserved MA-token grammar, finalizer 순서, source/DTO/market-data, summary/canonical 역할, route/refund와 frontend는 유지한다.
- 새 production route testcase는 실제 전달된 instructions에 금지된 MA-number 표기가 없음을 검사하고, `일봉 차트의 20일 이동평균과 체결 기록을 비교했습니다.`의 ready/seal 1과 MA20/MA5/MA 20/ma20의 terminal compatibility reject/seal 0/serializer 0/refund 1/history 0을 확인한다. 성공 시 생성 및 history wire 검증의 모든 serializer 입력은 동일한 sealed body여야 한다. 기존 prompt assertion도 같은 자연어 계약으로 갱신한다.
- 새 route testcase 한 개로 현재 Python source inventory는 731 direct, 93 modules, baseline 35/659/22 + Stage 1 15, 별도 child probe 18이다. Node 22 entrypoints/183 direct는 유지한다. Focused 실행 결과와 preservation은 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks, browser/device/live network/private DB는 실행하지 않는다. Phase 2D HOLD; finding 재검토는 보고 후 대기한다.
- 최종 focused Python **280/280 PASS**(13 modules), A1 실제 frontend cross-contract **11/11 PASS**, Node coordinator **9/9 PASS**다. Route 정상 20일 이동평균은 ready/seal 1/refund 0/opt-in history 1이고, MA20/MA5/MA 20/ma20은 error/invalid_structured_output/seal 0/serializer 0/refund 1/신규 history 승인·저장 0이다. 모든 성공 serializer 입력은 같은 sealed body이고 replay 추가 model/charge/refund/history는 0이다. 처음 새 테스트가 생성과 history 검증 호출을 합쳐 1회로 기대했던 assertion만 수정해 재검증했다. Guarded unexpected 0, restoration/patch restoration/cleanup true, report/inventory issues 0이다. Production diff는 advanced terminology 한 문단뿐이며 A1/finalizer/source/route 및 frontend 135개는 유지했다. 상세 파일·증거는 실행 계획에 남긴다.

### Phase 2C-A3 route/refund/replay/history/cache — 2026-10-04

- 표시 정본은 sealed canonical body이고 `canonical_text`는 그 AST의 visible text다. `summary`는 sealed body에 A1 serializer를 적용한 deterministic compatibility wire다. Strong이 있으면 summary/canonical_text byte equality를 요구하지 않는다.
- Route는 기존 internal approval_state를 받아 body/wire/status/source/review_type을 검증하고 access/history ID만 추가한다. Cache는 동일한 immutable snapshot과 소유한 response copy를 보관하고 replay flag만 바꾼다. Semantic/raw model/legacy summary에서 본문이나 wire를 재구성하지 않는다.
- Opt-in history metadata는 기존 canonical helper와 safety로 seal 이전에 승인하고 independent JSON text로 고정한다. Ready/missing_key만 저장 가능하고 error/empty는 history 승인/저장하지 않는다. History 복원은 저장된 canonical body와 A1 wire를 검증한다. Canonical document가 없는 기존 legacy adapter는 확장하지 않는다. DB/API schema/version 변경은 없다.
- [Production route 회귀](../tests/test_review_route_compatibility.py)는 basic/advanced normal/fallback, plain/strong, opt-in/off, terminal compatibility failure, safety, malformed/schema-invalid, replay side effect 0, response/history/cache alias 차단과 tampering 거절을 실제 route 및 synthetic storage/refund로 검증한다. 기존 refund/history/finalization 회귀도 유지한다.
- 최종 focused Python은 **349/349 PASS**(22 modules, route 21/refund 13/history-consent 7/finalization 2 포함)다. A2 finalizer 18, A1 compatibility 14, structured 75와 safety/source/market/envelope/transport/access/history-store/coordinator/storage/docs 회귀도 통과했다. Guarded unexpected 0, 전체 restoration/patch restoration/cleanup true, inventory issues/FAIL/ERROR/SKIP 0이다. Python coordinator의 이전 baseline 상수 한 곳을 694→715로 수정하고 재검증했다. Node A1 cross-contract 11 + canonical React 9 + format 7 = **27/27 PASS**, Node coordinator **9/9 PASS**다. 정확한 sealed strong sentence와 실제 normal template의 strong, failed history 승인/저장 0, 환급 1회, replay 추가 model/charge/refund/history 0을 확인했다. Source inventory 730 direct/18 child probe와 Node 22/183은 전체 suite 실행 수치가 아니다. 시작 파일 347/363 및 frontend 135개는 byte-identical이며 상세 증거는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다.
- Frontend production 변경 0. 전체 TestOnly/BuildChecks, browser/device/live network/private DB와 다른 worktree 변경은 수행하지 않는다. A1/A2는 독립 승인됐고 전체 Phase 2C 독립 검토는 A3 구현/검증 뒤 대기한다. Phase 2D HOLD.

### Phase 2C-A2 production finalizer admission — 2026-10-04

- A1의 grammar와 공유 vectors를 유지하고 `validate_legacy_body`를 admission 전용 함수로 분리했다. Normalized semantic body의 canonical safety 뒤와 선택된 production envelope의 canonical safety 뒤에 compatibility admission을 수행한다. Admission 실패는 terminal error이며 snapshot/structured/body/raw summary를 공개하지 않는다. Missing key나 다른 template으로 복구하지 않고 기존 `safety_rejected` 의미를 유지한다.
- Production summary는 seal 이후 읽은 body에만 `admit_legacy_body`의 A1 deterministic serializer를 적용한다. Normal/fallback/low-confidence/fixed/unavailable/empty 경로를 모두 검증한다. Basic은 정보와 순서를 유지한 4문단, 중간 `\n\n`/마지막 빈 separator를 사용한다. Reserved section/list syntax를 safe labels와 문단 내 구분으로 바꾼다. Advanced fallback 4개 section은 문구·순서·정보를 그대로 유지하며 normal advanced는 빈 선택 항목의 template whitespace만 제거한다.
- A1 `mid_word_strong` PASS fixture는 표시 계약상 유효하지만 canonical text가 미래 매수 추천이다. Production safety는 이를 `safety_rejected`로 거절하고 승인된 안전 fallback을 사용한다. A1 grammar PASS 10 / FAIL 65와 frontend harness는 유지한다. 나머지 9 PASS는 production에서도 ready, FAIL 65는 ready/serializer 호출 없이 거절된다. 이 구분 없이 A1 표시 PASS를 production safety 승인으로 해석하지 않는다.
- H4 focused 실행: 기존 승인된 Python의 `-I -X utf8 -B tests/run_isolated_tests.py`에 legacy/finalizer/structured/OpenAI client/safety/finalization/source/admission/market/display/envelope/quality/chart-provider/Python coordinator/storage/docs의 명시적 module만 전달한다. Node는 `--node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-format --node-executable <approved absolute node.exe>` 및 `--node-regressions`를 사용한다. 실제 결과와 preservation은 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다.
- 최종 focused 결과: Python **291/291 PASS**(16 modules), Node cross-contract **11/11** + canonical React **9/9** + format **7/7**, Node coordinator **9/9** 별도 PASS. Guarded unexpected 0, restoration/patch restoration/cleanup true, final inventory issues/FAIL/SKIP 0. P1 두 raw model 입력은 두 builder에서 ready/seal/serializer/raw summary 노출 0. 시작 파일 348개와 frontend 파일 135개는 byte-identical이다. Inventory 709/18 및 Node 22/183은 source 집계이며 전체 suite 실행 수치가 아니다.
- Route/refund/replay/history/cache production 연결과 strong wire에 대한 기존 route equality 변경은 A3에 남긴다. Frontend production, CanonicalReviewRenderer, A1 frontend harness, source/market admission, DTO 보호와 whole-episode/20-trade window를 변경하지 않는다. 전체 TestOnly/BuildChecks, browser/device/live network/private DB는 실행하지 않는다. Phase 2D HOLD.

### Phase 2C-A1 legacy-safe cross-contract — 2026-10-04

- A — Legacy-safe subset 선택에 따라 [독립 계약](../backend/core/review_legacy_compatibility.py)을 추가했다. 입력은 검증된 `review-display.v1` canonical body뿐이며 semantic tree/raw summary를 읽지 않는다. `admit_legacy_body`는 immutable success/summary 또는 안정적인 rejection code를 반환한다. Production 연결은 이번 범위에 없다.
- Grammar: body surface, paragraph block, text/strong run만 허용한다. 중간 separator는 `\n\n`, 마지막은 빈 문자열이다. Text는 그대로, strong은 `**text**`로 직렬화한다. Wire와 canonical text의 byte equality는 요구하지 않으며 실제 표시 text, 문단 개수/순서, strong element 범위를 검증한다.
- Paragraph edge whitespace, 연속 space, ASCII space 이외의 whitespace(newline/tab/NBSP 포함), BOM, strong edge space를 거절한다. Literal `* _ backtick [ ] # backslash < >`, 목록/구분선 prefix, basic section token, MA/ma + 공백/숫자 token, display-removal token을 예약한다. Basic/MA 패턴은 canonical 문서 전체에서 검사해 run 및 문단 separator를 통한 우회도 거절한다. 입력 trim/replace/Unicode normalization은 없다.
- [공유 fixed vectors](../frontend/scripts/fixtures/review-legacy-compatibility-v1.json)는 production output에서 expected를 생성하지 않고 작성했다: PASS 10 / FAIL 65. 두 P1 literal 입력과 strong AST + 잘못된 suffix, run/문단 경계 우회, 정상 strong 및 advanced fallback 4문단 두 shape를 포함한다.
- [실제 frontend 교차 테스트](../frontend/scripts/legacy-review-cross-contract.test.js)는 production aiReviewFormat을 직접 import하고, TradingJournal의 `reviewDisplayText`, `ReviewInlineText`, `AiReviewSummary` 원본 선언을 TypeScript AST로 선택해 JSX만 test-only 변환/load한다. Production export/구현 변경이나 복제 parser/renderer는 없다. Real React server output의 DOM nesting, 개별 p node, visible text, strong node의 Unicode codepoint offset을 확인하며 basic/advanced 표시 mode를 모두 실행한다.
- H4 coordinator는 [fresh Python child](../tests/review_legacy_handoff.py)의 실제 admission 결과를 Node 임시 fixture로 전달한다. Rejection에는 summary가 없고 frontend 실행 전 gate에서 끝난다. React 19.2.6 지정 9개 파일과 기존 TypeScript 4.2.4 지정 2개 파일만 lock version/hash 확인 후 임시 복사한다. 설치/네트워크/production build는 수행하지 않는다.
- 실행 경로: 승인 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py tests.test_review_legacy_compatibility tests.test_review_display_contract tests.test_full_test_entrypoint tests.test_storage_fixture_runner tests.test_quick_verify_docs`; Node는 같은 coordinator의 `--node-entrypoint test:legacy-review-cross-contract --node-entrypoint test:canonical-review-renderer --node-entrypoint test:ai-format --node-executable <approved absolute node.exe>` 및 `--node-regressions`를 사용한다. 결과: Python 51/51(legacy 13, display 14, coordinator 15, storage 2, docs 7), Node cross-contract 11/11 + canonical React 9/9 + aiReviewFormat 7/7, Node coordinator 9/9 PASS. 정상 strong `[0,5)` 보존, P1 두 입력 및 FAIL 65개 frontend 호출 0. Guarded unexpected 0, restoration/patch restoration/cleanup true; coordinator nested 증거 통과. 상세 결과는 [실행 계획](exec-plans/structured-trade-review.md)에 기록한다. 전체 TestOnly/BuildChecks와 browser/CSS/device/external 증거는 포함하지 않는다.
- 기존 Phase 2C readiness는 redesign으로 대체되었다. A1 결과는 독립 subset 증명이며 finalizer/status/refund/route/history/cache/replay 연결 승인이나 Phase 2D 진행을 뜻하지 않는다. **Phase 2D HOLD**.

### Historical Phase 2C focused H4 evidence — 2026-10-03

- Inventory: Python 90 modules / 676 direct = 35 / 605 / 22 baseline + 14 Stage 1; 18 separate child probes. Node 21 entrypoints / 172 direct. Missing/duplicate/extra dependencies and expected skips are 0.
- Focused Python: 298/298 PASS in 20 explicit modules, including OpenAI client 16, display 14, envelope 26, structured 75, source contract 32, source admission 23, market admission 26, safety 17, finalization 2, transport 10, quality/chart/refund/history/access and Python/storage/docs coordinators. The 18 guarded reports have unexpected violations 0 and restoration/patch restoration/cleanup true. Both coordinator reports have restoration/patch restoration/cleanup true; their nested evidence contracts pass.
- Node: actual React renderer 9/9, unchanged frontend parser 7/7 and synthetic coordinator 9/9 PASS. Registered entrypoints have unexpected violations 0 and restoration/patch restoration/cleanup true.
- Serializer preserves body runs and separators exactly, including strong text, whitespace/newlines and list markers; invalid/wrong-surface/raw-summary inputs reject. Returned summaries match the sealed body. Source/candidate/result mutations cannot alter approved bytes or the already-generated summary. Model `매**수**` safety counterexamples cannot reappear through compatibility.
- Focused results above were rerun after the explicit advanced fallback newline decision: Python 298/298, parser 7/7, React 9/9, Node coordinator 9/9 PASS; inventory counts remain unchanged. Phase 2C is ready for independent review.
- Confirmed Phase 2C contract: advanced fallback top-level separators change from `\n` to `\n\n` by explicit user instruction. Basic fallback keeps single newlines; normal basic/advanced are unchanged. Fixed literals and a shared synthetic JSON contract preserve each section character/space while Python actual builder/sealed-body checks and the unchanged Node frontend parser verify four separate paragraphs. Final independent review remains pending; Phase 2D is not performed.
- H4-owned temporary storage/environment only; providers/model calls mocked or blocked. No full TestOnly/BuildChecks, live provider, browser/CSS/device or external validation.

### Phase 2B-3 focused H4 evidence — 2026-10-03

- Source inventory: Python 90 modules, direct **662** = baseline **35 / 591 / 22** + Stage 1 **14**, with **18** child probes counted separately. Missing/duplicate/expected skip are 0. Node is **21 entrypoints / 169 direct**; missing/duplicate/extra and missing source dependencies are 0.
- Focused Python run: **276/276 PASS** across 20 explicit modules covering source admission/contracts, typed compiler and display/envelope contracts, structured review, market data, safety/finalization, refund, history boundaries, Python coordinator, storage and docs. The 18 guarded module reports had unexpected violations 0 and restoration, patch restoration and cleanup true. Coordinator-owned nested storage-fixture evidence was 4/4 PASS with restoration and cleanup true.
- Node coordinator regressions: **9/9 PASS**. The registered canonical React renderer entrypoint: **9/9 PASS**, including cleanup/restoration and unexpected violations 0.
- New source-derived regressions prove invalid source stays terminal with both API keys absent, a prior ready snapshot is replaced after a later admission failure, and a missing `Close` column is rejected in both daily and context production-builder paths. Normal provider inputs remain `ready`.
- Provider/model calls were synthetic or mocked; persistent/private databases, live provider/network, device, full TestOnly and BuildChecks were not accessed or run. This focused evidence does not replace the historical full TestOnly closeout or prove production/device behavior.

**H4 test environment isolation closeout complete.** 공식 전체 TestOnly는 exit code **0**, 전체 PASS로 최종 승인됐고 closeout 문서화와 최종 확인도 완료됐습니다.

- Python direct **464 PASS** (FAIL/ERROR/SKIP 0); missing/duplicate/extra/unexpected skip 모두 0.
- H4 classification은 A1/foundation/helper **35**, migrated A2+B1+B2+C+D **393**, OUT **22**이며, Stage 1 신규 cohort **14**를 별도로 더해 464입니다.
- Child probe **18/18 계약 PASS**. Expected negative raw ledger **6 (4+1+1)**, probe contract mismatch **0**, suite-level unexpected **0**.
- Node entrypoint **17/17 PASS**, direct testcase **128 PASS** (FAIL/SKIP 0); missing/duplicate/extra/unexpected skip 모두 0.
- `restored`, `patches_restored`, `cleanup` 모두 true; Node temp cleanup 성공, test-owned temp 잔여와 repo pollution은 0입니다.

Stage 1/2 및 Foundation isolation 의미는 유지됐습니다. BuildChecks는 이번 H4 TestOnly에 포함되지 않았으며, 별도 실행·승인을 의미하지 않습니다.
Android debug/release wrapper와 임의 raw module 실행에 H4 TestOnly 보장이 자동 적용되지 않습니다. -B는 bytecode만 막으며 DB/network 격리를 대신하지 않습니다.

축소 문서 검증은 승인 Python으로 `-I -X utf8 -B tests/run_isolated_tests.py tests.test_quick_verify_docs`를 사용합니다. Wrapper synthetic 검증은 `tests/verify_project_wrapper_regression.ps1`에 명시적 PythonPath/NodePath를 전달하며, 실제 coordinator 대신 synthetic dispatch를 검사합니다.

## 변경별 검증 수준

| 변경 | 최소 확인 |
| --- | --- |
| 문서/AGENTS | 관련 문서 테스트, 링크·경로·명령 존재, 신규 파일 포함 secret 검사, diff/status |
| 환경/포트/CORS | 설정 누락·충돌·fallback, 최종 API/DB 선택, 실제 교차 출처 HTTP와 응답 헤더 |
| API/인증 | 소유권·익명·잘못된 세션·권한 거절, 실제 HTTP 입력/오류 응답 |
| 데이터/schema/삭제 | 이전 schema→현재, 다른 사용자 보존, 단계별 실패·재시도, 복원 |
| AI/권한/결제 | 중복·거절 후 재시도·차감/환급·서버 재시작, 외부 응답 mock과 별도 실서비스 검증 |
| Android UI/로그인/광고 | 정책 테스트와 최종 패키지 확인, 기기 화면·수명주기·외부 연동 |
| Release | RELEASE.md의 아티팩트·버전·서명·환경·배포 revision 증거 |

현재 Node 테스트에는 소스 문자열 검사도 있다. 문자열 존재는 React 렌더링·이벤트 순서·native plugin 작동 증거가 아니다. Java 기본 테스트도 package/샘플 확인 수준이다.

실제 HTTP client 기반 통합 테스트는 감사에서 발견하지 못했다. M6의 X-Request-ID/Retry-After CORS 노출처럼 직접 함수 호출이 놓치는 동작을 별도로 검증해야 한다.

## 반드시 분리해서 남길 미검증 영역

- OAuth: 취소, state/만료/중복 티켓, 앱 종료 후 복귀, cold start, 다른 URI scheme, 공급자 실제 설정.
- 결제: 보류·취소·중복 콜백, 구매 중 종료, 네트워크 단절, 계정 전환, consume/acknowledge 재시도, RTDN·환불.
- 광고: 각 광고 형식, Pro 숨김, keyboard/전체화면/뒤로가기, SSV 지연·중복, 테스트 ID와 실제 지급 차이.
- 데이터: 저장 on/off, 계정 전환, 삭제 중 실패/동시 요청, export 한도, 기기 파일 저장·backup.
- 운영: disk full/locked, 이전 schema, 복원, API timeout, process restart, proxy rate limit.

결과에는 명령, 실행 위치, 기준 revision, 통과/실패/미실행, 검증 수준, 남은 제약을 남긴다. 최신 device/external 증거가 없으면 완료를 주장하지 않는다. 과거 감사 결과와 현재 작업에서 새로 실행한 검증을 구분한다. 검증 기록은 사용자에게 승인받은 범위의 계획이나 최종 보고에 남긴다.
