# F3 재설계 Step 1 — production history producer 계약

기준: 2026-10-09, `feature/structured-trade-review`,
`787a9d5683803003fe2c7bfe1e786f5874847462`의 현재 working files.
이 문서는 Step 2의 입력 계약을 확정한다. 새 validator 구현이나 production
동작 변경은 포함하지 않는다. [상위 계획](structured-trade-review.md)의 이전
F3 완료 기록과 구분한다.

## 1. 확인 경계와 source

확인 대상은 `_save_ai_review_history_if_enabled` 호출 **직전**의 result와
`history_state["approved"]`다. 응답에 나중에 붙는 `review_history_id`, replay에서
바뀌는 `idempotent_replay=True`, DB가 생성하는 id/created_at은 새 write 입력이 아니다.
Legacy adapter가 허용하는 optional 필드를 production producer의 optional 필드로
간주하지 않는다.

| 책임 | 실제 production source |
| --- | --- |
| 사용자/세션 및 저장 동의 | [account_store.py](../../backend/core/account_store.py): `login_provider_identity`, `login_dev_provider`, `login_review_access`, `authenticate_session` |
| access auth/plan/source | [access_control.py](../../backend/core/access_control.py): `_authenticate`, `_plan_for`, `_consume_basic`, `_consume_advanced`, `verify_ai_review_access` |
| 일반 wallet, reset, Pro 주기 | 같은 파일: `_wallet_snapshot`, `_reset_deadlines`, `_pro_allowance_cycle`, `_subscription_is_active` |
| review quota/wallet/date | 같은 파일: `initialize_review_entitlement`, `_parse_utc_datetime`, `_review_row_is_active`, `_consume_review_quota`, `_review_entitlement_snapshot` |
| 저장 가능 여부/최종 access 직렬화 | [main.py](../../backend/main.py): `_optional_session_user`, `_prepare_ai_review_history_state`, `get_journal_ai_review_once` |
| review 결과/metadata/승인 snapshot | [ai_review_v2.py](../../backend/core/ai_review_v2.py): `_call_openai_review`, `build_basic_ai_review`, `build_advanced_ai_review`, `_finalize_ai_review`, `_canonical_history_metadata` |
| nested structured/display/chart | [review_source_projection.py](../../backend/core/review_source_projection.py), [review_source_contract.py](../../backend/core/review_source_contract.py), [review_envelope_contract.py](../../backend/core/review_envelope_contract.py), [journal_chart.py](../../backend/core/journal_chart.py) |
| 기존 persistence 및 replay와의 비교 | [review_history.py](../../backend/core/review_history.py): `add_review_history`; main의 `_validate_ai_review_cached_access`. 이들을 새 계약 구현으로 재사용하거나 수정하지 않음 |

## 2. 정상 저장 variant

아래 다섯 provenance 각각에 `basic / advanced × ready / missing_key` 네 조합을
지원한다. 실제 저장 가능한 계약상 auth_mode는 `session` 또는 `review`다.

| provenance | access.auth_mode | access.plan / wallet.plan | wallet producer | pro_allowance_resets_at |
| --- | --- | --- | --- | --- |
| session free | `session` | `free / free` | `_wallet_snapshot` | 반드시 `None` |
| session Pro | `session` | `pro / pro` | `_wallet_snapshot` | offset 있는 날짜 문자열; 보통 Play expiry 원문 |
| review | `review` | `pro / pro`, 또는 소비 후 상태 변경 시 `pro / free` | `_review_entitlement_snapshot` | entitlement expiry 원문, offset 있는 날짜 문자열 |
| dev 로그인으로 발급한 실제 free 세션 | `session` | `free / free` | `_wallet_snapshot` | 반드시 `None` |
| 실제 세션 + dev Pro entitlement | `session` | `pro / pro` | `_wallet_snapshot` | 활성 Play 구독이 없으면 KST 다음 달 1일 00:00 |

- 일반 세션과 dev 로그인 세션은 history 입력에서 같은 `session` 계약이다.
  dev 여부를 새로운 필드나 auth_mode로 추정하지 않는다. dev login 자체는 Pro를
  부여하지 않는다. dev Pro token은 dev access가 켜져 있을 때만 유효하다.
- `_pro_allowance_cycle`의 월별 fallback에는 별도 dev guard가 없다. plan 결정 후
  활성 Play row가 사라진 경우에도 같은 날짜를 만들 수 있다. 따라서 KST 월별
  expiry라는 이유만으로 production session Pro를 거절하지 않는다.
- review의 storage 기본값은 login에서 on이지만 이후 opt-out할 수 있다. 모든
  저장은 유효한 실제 세션과 현재 `journal_storage_enabled=True`가 선행 조건이다.
- 단독 `Bearer dev-token`은 `_authenticate`에서 `dev-user/dev`가 되지만
  `authenticate_session`에서는 401이고 history state는 `None`이다. 여기에 dev
  Pro/ad token, basic/advanced, ready/missing_key를 곱해 저장 가능 variant를 만들지
  않는다. 실제 route에서는 consent 세션 기록도 먼저 실패할 수 있다.
- dev 설정이 꺼져 있거나 `ALPHAMATE_ENV=production`이면 dev login/token 권한을
  정상 production variant로 취급하지 않는다. 설정 검증은 production의 dev 활성화를 거절한다.

## 3. 공통 required key와 exact type

모든 object는 아래 명시한 key를 **모두** 가져야 하고 extra key는 거절한다.
타입은 `type(value) is ...` 기준이다. bool을 int로, int를 float로, subclass를
plain JSON 타입으로 암묵 변환하지 않는다. `None`은 아래 명시한 자리만 허용한다.
모든 수치는 finite이고 count/id는 기존 JSON safe integer 범위 안이어야 한다.

### result와 승인 metadata

| 위치 | required key / exact type / 조건 |
| --- | --- |
| result 공통 | `status:str`, `source:str`, `review_type:str`, `model:str 또는 None`, `summary:str`, `display_snapshot:dict`, `structured_review:dict`, `chart_display_snapshot:dict`, `chart_contexts:list`, `chart_reviews:list`, `access:dict` |
| basic 추가 | `chart_snapshot:dict`, 현재 producer의 값은 `{}`. `chart_snapshots`는 없음 |
| advanced 추가 | `chart_snapshots:list`, 현재 producer의 값은 `[]`. `chart_snapshot`은 없음 |
| 현재 legacy chart placeholders | 두 타입 모두 `chart_contexts=[]`, `chart_reviews=[]`; 실제 승인 차트는 `chart_display_snapshot`에 있음 |
| ready | `status="ready"`, `source="openai"`, `model`은 nonempty str. API key가 없다는 이유로 model 문자열을 강제로 만드는 작업 금지 |
| missing_key | `status="missing_key"`, `source="chart-rules"`, `model is None`. key 누락 시 실제 `_call_openai_review`는 외부 요청 전에 빈 문자열을 반환 |
| 정상 두 status 공통 | `internal_status` 없음, `access.refunded is False`, `access.idempotent_replay is False` |
| approved | 정확한 `ApprovedReviewSnapshot`과 `metadata_json:str`. snapshot이 승인한 status/source/review_type, body, compatibility summary, 전체 chart projection이 result와 동일 |
| metadata | `ticker:str`, `name:str`, `trade_date:str`, `target_trade_id:int 또는 None`, `trade_snapshot:dict`, `recent_trades_snapshot:list`, `chart_snapshot:dict` |
| metadata.chart_snapshot | 정확히 `{"charts": list}`. catch된 chart-provider 예외나 ticker 없는 trade는 빈 list를 만들 수 있음 |
| trade_snapshot / recent item | `trade_date,ticker,name,side,memo,source:str`, `price,quantity,fee,tax:float`, `display_snapshot:dict`; identified request에는 `id:int` 추가. id 없는 정상 request에서는 id key 자체가 없음 |

trade_date는 실제 source가 허용하는 유효 calendar date/datetime이다. **trade 날짜의
offset 생략 허용과 access validity의 offset 필수 조건은 다르다.** price/quantity는
양수, fee/tax는 0 이상, side는 buy/sell, ticker는 여섯 자리 KRX 또는 name-only의
빈 문자열이다. target id가 있으면 양의 safe integer다. name/memo/source와 모든
표시 문서는 기존 source/display의 길이·문자·안전성 제한을 유지한다.

- metadata의 ticker/name/trade_date는 선택된 trade_snapshot의 동일 필드다.
- target id 미지정/일치 항목 없음이면 history producer는 입력의 마지막 trade를
  고르고, 지정한 id는 그대로 저장한다. 따라서 `target_trade_id == trade_snapshot.id`
  를 무조건 요구하지 않는다. 기본/심화 builder는 날짜로 정렬한 마지막 trade로
  fallback한다. 입력이 정렬되지 않았다면 이 둘의 선택이 다를 수 있다는 현재
  source 경계도 보존하며, 새 write 계약에서 새 선택 정책을 만들지 않는다.
- recent snapshot은 입력의 마지막 10개이고 target이 반드시 포함된다는 보장은 없다.
  request id가 없는 trade도 정상 저장 가능하다. POST DTO는 created_at/user_id를
  snapshot trade에 만들지 않는다.
- metadata chart는 일반 journal chart producer의 별도 결과다. AI 승인 chart
  projection과 값을 같게 강제하지 않는다. 두 객체는 각자의 계약을 만족해야 한다.
- ready라도 data confidence가 낮으면 실제 producer가 deterministic semantics를
  선택할 수 있다. origin/status/model만으로 model 원문과 semantic 일치를 요구하지 않는다.
- API result의 missing_key `model=None`과 DB column `model=""`은 기존의 서로 다른
  표현이다. Step 2가 result의 `None`을 임의 정규화해서는 안 된다.

### nested review/display 계약

- structured_review의 정확한 key는 `schema_version,review_type,objective,summary`
  및 해당 `basic` 또는 `advanced` 하나다. version은 `trade-review.v1`.
  summary는 `decision_quality:{label:str,explanation:str}`, `main_issue:str`,
  `next_action:str`, `data_confidence:{level:str,label:str,reasons:list[str]}`,
  `missing_information:list[str]`를 모두 가진다.
- basic은 `good_points:list[{title:str,detail:str}]`,
  `main_improvement:{title:str,detail:str}`,
  `next_trade_checks:list[{phase:str,text:str}]`,
  `lesson:{title:str,concept:str,applied_to_this_trade:str}`를 모두 가진다.
- advanced는 `entry_review:{evidence:list[str],uncertainty:list[str],invalidation:str,assessment:{label:str,explanation:str}}`,
  `risk_review:{planned_rule:str,actual_response:str,assessment:{label:str,explanation:str}}`,
  `exit_review:{profit_taking_assessment:str,trend_exit_assessment:str,explanation:str}`,
  `detailed_analysis:list[{title:str,detail:str}]`,
  `next_trade_playbook:{before_entry:list[str],while_holding:list[str],before_exit:list[str]}`,
  `reflection_questions:list[str]`, basic과 같은 lesson에 `next_trade_application:str`
  필드를 더한 object를 가진다. 열거값과 길이/배열 상한은 현재 semantic admission/schema
  를 따르며 이 Step에서는 변경하지 않는다.
- objective는 `symbol:{ticker:str,name:str}`,
  `period:{first_trade_date:str,last_trade_date:str}`, `result:dict`다.
  result의 `trade_count,closed_count,buy_fill_count,sell_fill_count,symbol_count`는 int,
  `realized_pnl,realized_return_pct,win_rate_pct,total_fee,total_tax,open_quantity`는
  finite int/float, `weighted_buy_price,weighted_sell_price`는 양수 int/float 또는
  None이다. 모두 required. count 관계와 period 순서는 기존 objective admission을 유지한다.
- display_snapshot은 `review-display.v1` / surface body의 기존 closed document다.
  `schema_version,surface,blocks,canonical_text`와 각 block/run의 exact key, 문자,
  길이, separator, canonical_text 일치 조건을 만족해야 한다.
- chart_display_snapshot은 정확히 `charts:list,chart_cards:list`다.
  nested key/type/nullability/배열 상한은 기존 `review_envelope_schema`와
  `validate_chart_display_snapshot`이 정본이다. 빈 projection도 정상이다. 생략, 재구축,
  int/float 교체와 seal 차이는 허용하지 않는다.

### access / wallet / quota

| 위치 | required key / exact type |
| --- | --- |
| access | `auth_mode,plan,review_type,source:str`; `quota,wallet:dict`; `refunded,idempotent_replay:bool` |
| quota | `basic,advanced:dict` |
| wallet | `plan:str`; `basic,advanced,products,settings,validity:dict` |
| basic (quota와 wallet 모두) | `signup_remaining,free_daily_remaining,free_daily_max_remaining,free_available_now,rewarded_ad_available,rewarded_ad_daily_remaining,free_monthly_remaining,free_monthly_limit,pro_monthly_remaining,purchased_remaining` 모두 int |
| advanced (동일) | `signup_remaining,pro_monthly_remaining,weekly_reward_remaining,weekly_advanced_granted,weekly_ad_views,weekly_ad_views_needed,purchased_remaining,max_hold` 모두 int |
| products | 정확히 `basic_review_15,basic_review_25,advanced_review_10,advanced_review_20:dict`. 각 product는 `kind:str,quantity:int,price_krw:int` |
| settings | `allow_advanced_ticket_for_basic:bool`, `ad_policy:dict`, `free_policy:dict` |
| ad_policy | `basic_reviews_per_rewarded_ad,rewarded_basic_daily_max,ads_per_advanced_ticket:int`; `force_rewarded_ad_chain:bool`; `preferred_rewarded_ad_sequence:str` |
| free_policy | `daily_basic,rewarded_basic_daily_max,monthly_basic_max,weekly_advanced_max:int` |
| validity | `timezone:str`; `daily_reset_at,weekly_reset_at,monthly_reset_at,weekly_reward_expires_at,pro_allowance_resets_at:str 또는 None`; `signup_pass_expires_at,purchased_pass_expires_at:None` |

각 required nullable leaf는 key 생략을 허용하지 않는다. wallet과 quota의 basic/advanced는
깊은 값과 타입이 같아야 한다. Python의 `True == 1`, `1 == 1.0`으로 같다고 처리하지 않는다.
값의 출처가 같아도 새 write 입력에서 mutable alias를 요구하지 않는다.

고정값: timezone=`Asia/Seoul`, ad sequence=`single`, ad basic grant=1, ad basic
daily max=2, free policy=(1,2,30,1), basic.free_monthly_limit=30, advanced.max_hold=1.
ads_per_advanced_ticket은 env에서 정한 1..20 (기본 5), force flag는 bool이다.
allow_advanced_ticket_for_basic은 일반 wallet에서는 env가 정한 bool, review에서는 항상 False다.

products의 현재 값:

| key | kind | quantity | price_krw |
| --- | --- | --- | --- |
| basic_review_15 | basic | 15 | 2900 |
| basic_review_25 | basic | 25 | 4500 |
| advanced_review_10 | advanced | 10 | 3900 |
| advanced_review_20 | advanced | 20 | 6900 |

모든 variant가 같은 production PRODUCTS를 사용한다. 새 write에서 누락이나 종류
불일치를 보완하지 않는다. 이번 Step에서 가격/상품을 변경하지 않는다.

## 4. 값의 관계와 review 예외

### 일반 wallet (session, 실제 dev session)

- `access.plan == wallet.plan`. free의 두 pro_monthly_remaining은 0이다.
  Pro basic은 0..35, advanced는 0..25다.
- `free_available_now = signup_remaining + free_daily_remaining`.
  monthly_remaining=0이어도 이 표시값은 양수가 될 수 있다. Pro에서도 signup/free 표시값이
  남는다. 양수라는 이유로 소비 가능하다는 판정을 추가하지 않는다.
- free_daily_remaining은 0..1, free_monthly_remaining은 0..30이다.
  `rewarded_ad_available == rewarded_ad_daily_remaining`이며 free는 0..2, Pro는 0이다.
- free는 `free_daily_max_remaining = free_daily_remaining + rewarded_ad_daily_remaining`.
  **Pro는 예외**: producer가 숨기기 전 rewarded 잔수를 더하므로 외부에 표시한 rewarded=0이어도
  free_daily_max_remaining은 3이 될 수 있다. Pro에서 이 등식을 강제하지 않고 차이 0..2를 허용한다.
- `weekly_ad_views_needed = max(0, ads_per_advanced_ticket - weekly_ad_views)`.
  pro_monthly 잔수 0과 signup/weekly/purchased 잔수가 동시에 있을 수 있다.

### review wallet

- access.plan은 verify에서 항상 pro다. wallet.plan은 snapshot을 얻을 때 `_review_row_is_active`
  로 재평가한다. quota 소비와 snapshot은 별도 호출이므로 소비 성공 직후
  entitlement가 만료되면 `access.plan=pro / wallet.plan=free`가 실제로 생성된다.
  정상 지원할 예외이며 일반적인 plan 등가 조건을 적용하지 않는다.
- basic은 free_monthly_limit=30과 pro_monthly_remaining 외에는 0이다.
  advanced는 max_hold=1과 pro_monthly_remaining 외에는 0이다.
  weekly_ad_views_needed=0이므로 일반 wallet의 ads-needed 등식을 적용하지 않는다.
- active일 때 두 pro_monthly_remaining은 review row의 0 이상 quota (통상 초기 100)다.
  설정 초기값은 1..1000으로 제한한다. 일반 Pro의 35/25 상한을 적용하지 않는다.
  source가 plan/basic/advanced의 active를 각각 판정하므로 expiry 경계에서 한쪽
  quota가 먼저 0이 될 수도 있다. 잔수 0은 직전 소비의 실패를 뜻하지 않는다.
- wallet.free일 때 quota 잔수는 0이다. reset 4개와 signup/purchased expiry는 항상 None이다.
  pro_allowance_resets_at은 row expiry를 유지한다. 저장 시 미래 시각이나 wallet.pro를
  다시 요구하면 성공한 소비 뒤의 정상 snapshot을 거절하게 된다.
- `_review_row_is_active`는 enabled/pro_enabled, parse 가능한 starts/expires,
  `starts <= now < expires`를 판정한다. starts/enabled/pro_enabled는 wallet에
  포함되지 않는다. write validator가 이들을 DB에서 다시 조회하거나 만들어내지 않는다.

### source와 review_type/plan의 관계

| auth/plan | basic에서 가능한 source | advanced에서 가능한 source |
| --- | --- | --- |
| session free | signup_basic, free_daily_basic, rewarded_ad_basic, purchased_basic, purchased_advanced_as_basic | signup_advanced, weekly_ad_advanced, purchased_advanced |
| session pro | pro_monthly_basic, purchased_basic | pro_monthly_advanced, purchased_advanced, signup_advanced, weekly_ad_advanced |
| review (wallet pro/free 공통) | review_basic | review_advanced |

dev session은 같은 표를 사용한다. purchased_advanced_as_basic은 설정 on일 때만 가능하다.
Pro basic에는 advanced권 fallback이 없다. 반면 `_consume_advanced`는 Pro와
구매 advanced권을 소진하면 signup/weekly 분기로 진행한다. 따라서 Pro advanced의
signup/weekly source를 잘못 거절하지 않는다. snapshot은 소비 후이므로 잔수 0도 정상이다.

## 5. access validity/date 확정 조건

| leaf | session free | session pro / dev session pro | review |
| --- | --- | --- | --- |
| daily/weekly/monthly_reset_at | KST offset을 가진 str | 동일 | None |
| weekly_reward_expires_at | weekly_reset_at과 같은 str | 동일 | None |
| signup_pass_expires_at | None | None | None |
| purchased_pass_expires_at | None | None | None |
| pro_allowance_resets_at | None | offset을 가진 str | offset을 가진 str (wallet.free여도 None 아님) |

내부 reset 형식은 `YYYY-MM-DDT00:00+09:00`이다. daily는 다음 날, weekly는 다음 월요일
(당일이 월요일이어도 7일 뒤), monthly는 다음 달 1일이다. 실재하는 calendar 날짜를 검증한다.
연도/월/윤일을 문자열만으로 추정하지 않는다. timezone 라벨이 Asia/Seoul이어도 외부
expiry는 UTC의 Z나 +00:00, +09:00 등을 유지할 수 있다. 모두 +09:00으로 바꾸지 않는다.
Pro의 Play expiry는 monthly reset과 같을 필요가 없다. dev 월별 fallback도
reset과 별도 시계 호출이므로 월 경계를 넘으면 무조건 같다고 요구할 수 없다.

새 write의 외부 expiry는 비어 있지 않은 str, parse 가능한 실재 datetime, 명시적 offset이 필수다.
현재 legacy 날짜 규칙과 replay 검증에 공통인 ISO 표현 (Z 또는 ±HH:MM, 정상
시각/offset)을 사용하고 원래 문자열을 저장한다. 미래 비교, UTC 변환, 보완은 하지 않는다.

**producer에서 도달할 수 있어도 신규 저장 전에 거절할 date 예외:**

1. `_review_access_config`, `_parse_utc_datetime`, `_parse_google_time`은 naive
   datetime/date-only도 parse하며 판정 시에만 UTC를 보완한다. snapshot에는 원문이
   남는다. 현재 replay의 offset 필수 조건에 맞지 않으므로 새 write에서
   저장 전에 거절한다. upstream이 수용하는 사실과 새 write 지원 범위를 구분한다.
2. `_subscription_is_active`는 ACTIVE/IN_GRACE_PERIOD의 expiry를 parse하지 못해도
   True를 반환한다. `_pro_allowance_cycle`이 `""`, 비정상 문자열, 존재하지 않는 날짜를
   wallet에 반환할 수 있다. 이 경우도 저장 전에 거절한다. CANCELED의 동일 조건과는 다르다.
3. review 초기화는 parse 불가능한 expiry를 503으로 거절한다. review와 Play의 잘못된 expiry를
   같은 upstream 동작으로 취급하지 않는다.

이 date 거절 방침은 replay 호환성을 위한 **Step 2 확정 사항**이며,
이번 Step에서는 새로운 거절을 구현하지 않았다. F1 cache 검증도 변경하지 않았다.

## 6. 신규 저장 전에 거절할 비정상 산출물

- required key 누락/extra, nullable key 생략, exact type 위반, 음수 count, nonfinite 수,
  비정상 id, plain JSON이 아닌 object, 순환/과도한 깊이·요소·길이.
- storage off/유효 세션 없음/auth_mode=dev를 저장 가능하다고 만든 조합.
  storage 판정은 route의 session 경계가 소유하고 pure write 계약에 외부 조회를 추가하지 않는다.
- ready/missing_key 외 status, status/source/model 불일치, internal_status가 있는 정상 결과,
  새 write의 refunded=True/idempotent_replay=True, 생성 후 review_history_id 혼입.
- review_type과 source 표 위반, quota/wallet 값 또는 exact type 불일치, 일반 wallet의
  plan 불일치, review 외 review_* source, review plan≠pro, 표에 없는 null/date 조건.
- 위 date 예외, 고정 policy/product의 누락/불일치, variant별 잔수/관계 위반.
  review의 35/25 초과, Pro의 숨긴 reward 잔수, review wallet.free는 거절 이유가 아니다.
- seal 누락/위조, body/summary/chart/status/source/review_type과 seal 불일치,
  chart projection 생략, basic/advanced placeholder 교체, unsafe 표시 내용.
- canonical metadata/trade/chart의 누락/타입/내용 위반. legacy adapter가 보완할 optional
  shape나 normalize하면 고쳐지는 result를 새 정상 producer variant로 지원하지 않는다.

거절은 history write connection/INSERT 전에 끝나야 한다. Step 2에서 이
경계를 만들 때도 legacy read adapter, writer, F1/F2/F4 변경은 별도 지시를 기다린다.

## 7. 검증과 Step 2 인계

추가한 [characterization tests](../../tests/test_review_history_producers.py)는
독립적인 key/type/값 fixture를 사용한다. production이 import하는 새 contract 구현은 없다.

- 실제 auth/access/builder/finalizer/기존 writer로 검증한 정상 20개 조합.
- 실제 소비 14개 분기, review의 큰 quota와 소비 직후 만료 4개 조합.
- 실제 no-key 경로, offset/Z 원문 보존, naive/date-only와 replay 불일치,
  ACTIVE subscription의 빈/비정상/존재하지 않는 날짜, review 초기화의 거절.
- 내부 reset의 연말/윤일, Pro free 표시와 숨긴 reward, storage-off,
  dev bearer 인증 불가, id 없음/stale target의 history metadata.

focused 증거와 최종 파일 보존 감사는 상위 계획에 기록한다. H4 안의
합성 unit/route/storage 증거이며 production 서비스나 device를 실행하지 않았다.
Step 2는 이 계약의 지원 variant와 저장 전 거절을 구현할 수 있는 상태다. 구현은 미착수다.
