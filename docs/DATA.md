# StockBoda Data

담당: 저장소·소유권·schema 변경·삭제·백업·복구.
근거: [account_store](../backend/core/account_store.py), [journal](../backend/core/journal.py), [review_history](../backend/core/review_history.py), [access_control](../backend/core/access_control.py), [event_log](../backend/core/event_log.py), [env](../backend/core/env.py).

## 저장소와 설정

| 설정 이름 | 기본 파일 / 데이터 |
| --- | --- |
| ALPHAMATE_ACCOUNT_DB_PATH | backend/data/accounts.sqlite3 — 사용자·identity·세션·저장 설정·동의 |
| ALPHAMATE_ACCESS_DB_PATH | backend/data/access.sqlite3 — 지갑·구매·구독·원장·광고·review 권한 |
| ALPHAMATE_JOURNAL_DB_PATH | backend/data/trades.sqlite3 — 사용자 매매 |
| ALPHAMATE_REVIEW_HISTORY_DB_PATH | backend/data/review_history.sqlite3 — 매매/차트/AI 결과 스냅샷 |
| ALPHAMATE_EVENT_LOG_DB_PATH | backend/data/event_log.sqlite3 — 운영 이벤트 |

기본 경로는 로컬 fallback이며 production 경로의 정답이 아니다. [render.yaml](../render.yaml)은 /var/data/alphamate의 다섯 DB와 cache를 지정한다. 실제 mount/데이터/백업은 외부에서 확인해야 한다.

**H3:** 공통 env_value는 process 값, 지정 환경파일, 기본 root/backend .env를 순서대로 읽어 누락 값을 보충한다. journal의 별도 loader는 ALPHAMATE_ENV_FILE을 읽지 않는다. 일반 시장 cache는 `ALPHAMATE_CACHE_DIR`을 해석하지만 `journal_chart.py`는 별도 `backend/.cache/yfinance` 경로를 사용하고 module import 중 디렉터리를 만들 수 있다. 단일 환경파일이나 cache 환경변수 하나로 모든 저장소와 cache가 격리되었다고 판단하지 않는다.

실행 전에 모든 최종 DB/cache 경로와 대상 환경을 검증한다. 비밀값이나 데이터 내용을 출력할 필요는 없다. 테스트 디렉터리 밖 연결은 거부하는 fixture가 필요하지만 아직 공통 구현이 확인되지 않았다.

## 데이터 계약

- 저장·조회·삭제는 현재 사용자에 한정한다. user_id가 없는 legacy 개발 분기가 실제 사용자 DB에 닿지 않게 한다.
- 저장 opt-in이 매매/복기 저장을 제어한다. 저장 off, logout, 기록 삭제, 계정 삭제의 의미를 구분한다.
- 주문 원장은 수량·잔여량·토큰·가격 제약 및 주문/사용자 연결을 유지한다. purchase_order 사용량은 같은 사용자의 유효한 주문에 연결되어야 한다.
- 구매 토큰은 hash와 암호문/key ID로 관리한다. 암호화 key 없이 DB만 복구하는 것으로 정상 복구를 보장할 수 없다.
- M5: 현재 export는 매매와 복기 이력 각각 코드에 지정된 건수로 제한된다. 전체 백업이나 완전한 데이터 반환을 보장한다고 설명하지 않는다.

## Schema와 초기화

현재 연결 함수에서 CREATE TABLE IF NOT EXISTS와 일부 ALTER TABLE을 수행한다. access_schema_meta의 특정 초기화 표식은 전체 DB에 대한 일반 schema migration 체계가 아니다. 새 테이블의 제약조건이 이미 존재하는 테이블에 자동 적용되지 않는다(H5).

**initialize_purchase_credit_ledger(reset_legacy_balances=True)는 일반 초기화/복구 명령이 아니다.** 기존 구매 잔액·구매/원장 관련 기록을 지우는 전환용 동작이다. 문서 복사, 테스트 준비, 오류 해결 목적으로 실행하지 않는다.

Schema 변경 작업에는 다음을 명시한다.

1. 대상 환경·DB 파일·기존 schema와 적용 revision.
2. 기존 사용자 데이터/제약조건/외부 계약에 대한 영향과 upgrade 방식.
3. 이전 schema 합성 fixture에서 upgrade·재실행·실패 검증.
4. 백업·쓰기 중단 또는 일관성 확보 방법·복원 확인.
5. 구버전 코드 호환성, forward fix/rollback 선택, 실패 중단 기준.

이는 요구사항이며 현재 migration runner나 자동 rollback이 구현되어 있다는 뜻이 아니다.

## 삭제와 미완료 처리

계정 삭제는 매매→복기→이벤트→권한→계정 DB를 각각 변경한다. 전체 원자성·동시 요청 차단·단계별 재시도 체계는 확인되지 않았다(H5). 코드 변경 전 삭제 상태, 신규 쓰기 차단, 일부 실패 후 복구와 다른 사용자 보존을 설계한다.

계정 삭제는 결제 관련 기록도 제거한다. 구독·분쟁용 최소 보관·삭제 후 외부 알림 정책은 승인된 의도를 확인해야 한다. 법적 보관 기간을 코드나 문서 작업자가 임의 결정하지 않는다.

H7: 이용권 차감은 DB에 commit되지만 AI 요청 중복 방지와 결과는 process cache에 있다. 재시작·TTL 이후 동일 요청과 기존 차감을 연결하는 영속 복구 체계가 부족하다. 요청 ID·처리 상태·차감/환급을 함께 추적하는 후속 작업이 필요하다.

## 백업과 복원 기준

아직 검증된 production 백업·복원 runbook은 확보하지 못했다. persistent disk가 있다는 사실은 복구 성공 증거가 아니다.

실제 데이터 변경을 승인받기 전에 DB 다섯 개의 일관된 백업 범위·시점, 암호화 key의 별도 안전 보관, 보관/삭제 정책, 복원 대상과 권한을 정한다. 쓰는 중인 SQLite 파일을 단순 복사한 결과를 검증 없이 완전한 백업이라고 부르지 않는다.

복원 연습은 production에 쓰지 않는 격리 환경에서 수행하고 schema, 사용자별 건수·관계, 잔액/원장, 로그인·삭제·export를 확인한다. 로그/실데이터를 보고서에 덤프하지 않는다. 결과와 미검증 영역은 실행 계획에 기록한다.
