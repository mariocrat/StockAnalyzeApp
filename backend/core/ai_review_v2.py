import copy
import datetime
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request

from core.ai_review import _env_value, _fmt8, _parse_date, _chart_context_for_trade
from core.data_fetcher import get_review_stock_ohlcv
from core.event_log import record_event
from core.journal import build_review
from core.journal_chart import build_journal_charts, _prepare_review_ohlcv
from core.trade_review_schema import (
    STRUCTURED_REVIEW_SCHEMA_VERSION,
    structured_output_format,
)
from core.review_display_contract import (
    ReviewDisplayContractError, compile_literal_lines, compile_literal_text,
    compile_structured_review, flatten_document, validate_document, serialize_compatibility_summary,
)
from backend.core.review_body_compiler import (
    compile_review_body, compile_basic_fallback_body, compile_advanced_fallback_body,
)
from backend.core.review_legacy_compatibility import (
    LegacyCompatibilityContractError, validate_legacy_body, admit_legacy_body,
)
from core.review_envelope_compiler import compile_review_envelope, seal_review_envelope
from backend.core.review_envelope_contract import (
    ApprovedReviewSnapshot, approved_chart_display_snapshot,
    validate_envelope as validate_review_envelope,
)
from backend.core.review_history_prepared_content import (
    _CAPTURE as _HISTORY_CONTENT_CAPTURE, prepare_history_content,
)
from backend.core.review_source_contract import (
    SourceAdmissionError, TradeSource, CompactChartSource, UnavailableChartSource,
    AnalysisContextSource, AnalysisContextErrorSource, TechnicalObservationSource,
    ValidatedReviewSource, admit_trade_sources, admit_chart_source,
    admit_analysis_context_source, admit_objective_source, admit_semantic_source,
    admit_journal_chart_source, select_chart_candles, compose_review_source,
    finish_review_source, unavailable_review_source, UNAVAILABLE_REVIEW_TEXT,
)
from backend.core.review_source_projection import (
    trade_payload, chart_payload, context_payload, semantic_payload,
    structured_review_payload, review_data_quality,
)


OPENAI_TIMEOUT_MAX_SECONDS = 90
OPENAI_MAX_RETRIES_LIMIT = 3
OPENAI_RETRY_BACKOFF_MAX_SECONDS = 5.0
OPENAI_MAX_OUTPUT_TOKENS_LIMIT = 10_000
OPENAI_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh"}
BASIC_REVIEW_FOCUS_LABELS = {
    "balanced": "매수 시점, 매도 시점, 위험 관리를 균형 있게 점검",
    "entry_timing": "매수 직후 5개 봉과 진입 위치를 우선 점검",
    "exit_timing": "매도 뒤 5개 봉과 청산 효율을 우선 점검",
    "risk_control": "분할 체결, 평균 체결가, 손실 제한 기준을 우선 점검",
}
AI_REVIEW_SAFETY_RULES = (
    "<safety_rules>이 서비스는 과거 매매 의사결정의 복기만 제공한다. "
    "과거 실제 체결 가격과 시각은 사실 확인을 위해 언급할 수 있다. "
    "향후 특정 종목, 가격, 시각, 날짜 또는 조건에서 매수하거나 매도하라고 권유, 추천, 지시 또는 암시하지 않는다. "
    "'X원에 매수 또는 매도', 'N시에 매수 또는 매도', '돌파 시 매수', '이탈 시 매도' 같은 실행 가능한 신호와 "
    "목표가, 추천 매수가, 추천 매도가를 만들지 않는다. 대신 당시 근거, 가설의 일관성, "
    "위험 관리 기록 여부와 사후 확인 질문만 제시한다.</safety_rules>\n"
)
_ACTION_DIRECTIVE_SUFFIX = (
    r"(?:하세요|하십시오|해야\s*합니다|하는\s*것을\s*(?:권장|추천)합니다|"
    r"(?:을|를)?\s*(?:권장|추천)합니다|해\s*보세요|하는\s*편이\s*좋습니다|"
    r"할\s*계획을\s*세우세요|(?:을|를)\s*(?:(?:고려|검토)(?:하세요|해\s*보세요)|"
    r"생각해\s*보세요))"
)
_PRICE = r"(?:\d[\d,]*(?:\.\d+)?원|\d+(?:\.\d+)?만원)"
_TARGET_PRICE_TERM = r"(?:목표\s*가격|목표\s*주가|목표가)"
_BUY_TRADE_ACTION = r"(?:매수|진입)"
_SELL_TRADE_ACTION = r"(?:매도|청산|손절)"
_TRADE_ACTION = rf"(?:{_BUY_TRADE_ACTION}|{_SELL_TRADE_ACTION})"
_RECOMMENDATION_PRICE_TERM = r"추천\s*{action}\s*(?:가|가격(?:대)?)"
_POSITIVE_RECOMMENDATION_PREDICATE = (
    r"(?:좋(?:아\s*보입니다|습니다)|낫습니다|"
    r"유리(?:해\s*보입니다|합니다)|적절(?:해\s*보입니다|합니다))"
)
_TARGET_PRICE_SETTING_ACTION = r"(?:잡는|설정하는|정하는|제시하는)"
_TARGET_PRICE_SETTING_DIRECTIVE = (
    r"(?:잡(?:으세요|으십시오|습니다)|설정(?:하세요|하십시오|합니다)|"
    r"정(?:하세요|하십시오|합니다)|제시(?:하세요|하십시오|합니다))"
)
_PRICE_GUIDANCE_SUFFIX = (
    r"(?:\s*(?:입니다|이에요|이다)|"
    r"\s*(?:정도|수준)\s*(?:가|이)?\s*(?:적절|타당)합니다|"
    rf"\s*(?:으로|로)\s*(?:{_TARGET_PRICE_SETTING_DIRECTIVE}|"
    rf"{_TARGET_PRICE_SETTING_ACTION}\s*(?:것이|게|편이)\s*"
    rf"{_POSITIVE_RECOMMENDATION_PREDICATE})|"
    r"\s*(?:으로|로)\s*(?:보입니다|적절해\s*보입니다)|"
    r"(?=\s*(?:[.!?]|$)))"
)
_DIRECTION_RECOMMENDATION_FORM = (
    rf"(?:쪽이|하는\s*(?:것이|게|편이))\s*(?:더\s*)?"
    rf"{_POSITIVE_RECOMMENDATION_PREDICATE}"
)


def _safety_comparison_text(text: str) -> str:
    """Normalize only the comparison copy; approved/display text stays exact."""
    return unicodedata.normalize("NFC", str(text or ""))


def _compile_safety_pattern(pattern: str) -> re.Pattern:
    return re.compile(_safety_comparison_text(pattern))


_PROHIBITED_TRADE_GUIDANCE_RULES = (
    (
        "rule_1",
        "target_price",
        _compile_safety_pattern(
            rf"{_TARGET_PRICE_TERM}\s*(?:는|은|를|:)?\s*(?:약\s*)?"
            rf"{_PRICE}{_PRICE_GUIDANCE_SUFFIX}"
            rf"|{_PRICE}\s*(?:을|를)?\s*{_TARGET_PRICE_TERM}\s*(?:으로|로)"
            rf"\s*{_TARGET_PRICE_SETTING_ACTION}\s*(?:것이|게|편이)"
            rf"\s*{_POSITIVE_RECOMMENDATION_PREDICATE}"
        ),
    ),
    (
        "rule_1",
        "recommended_entry_price",
        _compile_safety_pattern(
            rf"{_RECOMMENDATION_PRICE_TERM.format(action=_BUY_TRADE_ACTION)}"
            rf"\s*(?:는|은|를|:)?\s*(?:약\s*)?{_PRICE}"
            rf"{_PRICE_GUIDANCE_SUFFIX}"
        ),
    ),
    (
        "rule_1",
        "recommended_exit_price",
        _compile_safety_pattern(
            rf"{_RECOMMENDATION_PRICE_TERM.format(action=_SELL_TRADE_ACTION)}"
            rf"\s*(?:는|은|를|:)?\s*(?:약\s*)?{_PRICE}"
            rf"{_PRICE_GUIDANCE_SUFFIX}"
        ),
    ),
    (
        "rule_1",
        "buy_recommendation",
        _compile_safety_pattern(
            rf"{_BUY_TRADE_ACTION}\s*(?:추천\s*"
            rf"(?:합니다|드립니다|해요|입니다|하세요|하십시오)"
            rf"|{_DIRECTION_RECOMMENDATION_FORM})"
        ),
    ),
    (
        "rule_1",
        "sell_recommendation",
        _compile_safety_pattern(
            rf"{_SELL_TRADE_ACTION}\s*(?:추천\s*"
            rf"(?:합니다|드립니다|해요|입니다|하세요|하십시오)"
            rf"|{_DIRECTION_RECOMMENDATION_FORM})"
        ),
    ),
    (
        "rule_2",
        "conditional_trade_instruction",
        _compile_safety_pattern(
            rf"(돌파|이탈|도달|하회|상회)\s*(?:하면|시|할\s*때).{{0,30}}"
            rf"{_TRADE_ACTION}\s*(?:{_ACTION_DIRECTIVE_SUFFIX}|[.!?]|$)"
        ),
    ),
    (
        "rule_3",
        "price_or_time_trade_instruction",
        _compile_safety_pattern(
            rf"\d[\d,]*(?:원|시|분).{{0,30}}{_TRADE_ACTION}\s*"
            rf"{_ACTION_DIRECTIVE_SUFFIX}"
        ),
    ),
    (
        "rule_4",
        "explicit_risk_price_instruction",
        _compile_safety_pattern(
            r"(손절가|청산가|진입가).{0,20}\d[\d,]*(?:원|%).{0,20}"
            r"(?:설정|정하|두)(?:세요|십시오|는\s*것을\s*(?:권장|추천)합니다)"
        ),
    ),
    (
        "rule_5",
        "percentage_trade_instruction",
        _compile_safety_pattern(
            rf"-?\d+(?:\.\d+)?%.{{0,24}}{_TRADE_ACTION}\s*"
            rf"{_ACTION_DIRECTIVE_SUFFIX}"
        ),
    ),
)


class _OpenAiReviewText(str):
    def __new__(cls, value: str, *, response_status: str):
        instance = super().__new__(cls, value)
        instance.response_status = str(response_status or "unknown")
        return instance


def _matched_prohibited_trade_guidance_rule_ids(text: str) -> list[str]:
    normalized = _safety_comparison_text(text)
    return list(dict.fromkeys(
        rule_id
        for rule_id, _category, pattern in _PROHIBITED_TRADE_GUIDANCE_RULES
        if pattern.search(normalized)
    ))


def _matched_prohibited_trade_guidance_rule_categories(text: str) -> list[str]:
    normalized = _safety_comparison_text(text)
    return list(dict.fromkeys(
        category
        for _rule_id, category, pattern in _PROHIBITED_TRADE_GUIDANCE_RULES
        if pattern.search(normalized)
    ))


def _contains_prohibited_trade_guidance(text: str) -> bool:
    return bool(_matched_prohibited_trade_guidance_rule_ids(text))


def _env_int(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        value = int(_env_value(name) or default)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float | None = None) -> float:
    try:
        value = float(_env_value(name) or default)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _is_retryable_openai_error(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 409, 429, 500, 502, 503, 504}
    return isinstance(error, (urllib.error.URLError, TimeoutError))


def _review_max_output_tokens(payload: dict) -> int:
    if str(payload.get("review_type") or "").strip().lower() == "advanced":
        return _env_int("OPENAI_ADVANCED_REVIEW_MAX_OUTPUT_TOKENS", 3000, 256, OPENAI_MAX_OUTPUT_TOKENS_LIMIT)
    return _env_int("OPENAI_BASIC_REVIEW_MAX_OUTPUT_TOKENS", 1000, 256, OPENAI_MAX_OUTPUT_TOKENS_LIMIT)


def _review_reasoning_effort(payload: dict) -> str:
    is_advanced = str(payload.get("review_type") or "").strip().lower() == "advanced"
    env_name = "OPENAI_ADVANCED_REVIEW_REASONING_EFFORT" if is_advanced else "OPENAI_BASIC_REVIEW_REASONING_EFFORT"
    default = "medium" if is_advanced else "none"
    configured = str(_env_value(env_name) or default).strip().lower()
    return configured if configured in OPENAI_REASONING_EFFORTS else default


def _record_openai_usage(data: dict, *, payload: dict, model: str) -> None:
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    details = {
        "review_type": str(payload.get("review_type") or "unknown"),
        "model": model,
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(input_details.get("cached_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    try:
        record_event(
            level="info",
            event_type="openai_review_usage",
            method="POST",
            path="/v1/responses",
            status_code=200,
            message="OpenAI review token usage recorded.",
            details=details,
        )
    except Exception:
        # Usage telemetry must never turn a successful review into a user-facing failure.
        return


def _record_openai_failure(error: BaseException, *, payload: dict, model: str, attempt: int) -> None:
    status_code = error.code if isinstance(error, urllib.error.HTTPError) else 0
    details = {
        "review_type": str(payload.get("review_type") or "unknown"),
        "model": model,
        "attempt": attempt,
        "error_type": type(error).__name__,
        "retryable": _is_retryable_openai_error(error),
    }
    try:
        record_event(
            level="error",
            event_type="openai_review_request_failed",
            method="POST",
            path="/v1/responses",
            status_code=status_code,
            message="OpenAI review request failed without storing prompt or response content.",
            details=details,
        )
    except Exception:
        return


def _filter_openai_review_safety(
    text: str, *, payload: dict, model: str, response_status: str | None = None,
) -> tuple[str, list[str]]:
    matched_rule_ids = _matched_prohibited_trade_guidance_rule_ids(text)
    if not matched_rule_ids:
        return text, []
    matched_rule_categories = _matched_prohibited_trade_guidance_rule_categories(text)
    try:
        record_event(
            level="warning",
            event_type="openai_review_safety_rejected",
            method="POST",
            path="/v1/responses",
            status_code=200,
            message="OpenAI review output was rejected by application safety rules without storing response content.",
            details={
                "review_type": str(payload.get("review_type") or "unknown"),
                "model": model,
                "matched_rule_ids": matched_rule_ids,
                "matched_rule_categories": matched_rule_categories,
                "response_status": str(response_status or getattr(text, "response_status", "unknown") or "unknown"),
            },
        )
    except Exception:
        # Safety telemetry must never interfere with rejecting unsafe output.
        pass
    return "", matched_rule_ids


def _call_openai_review(payload: dict, *, model: str, instructions: str) -> str:
    api_key = _env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY")
    if not api_key:
        return ""

    body = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": _review_max_output_tokens(payload),
        "reasoning": {"effort": _review_reasoning_effort(payload)},
        "store": False,
    }
    response_format = (payload.get("output_contract") or {}).get("response_format")
    if isinstance(response_format, dict):
        # Responses API structured output is opt-in so legacy callers and tests
        # that request plain text keep the original request shape.
        body["text"] = {"format": response_format}
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout_seconds = _env_int("ALPHAMATE_OPENAI_TIMEOUT_SECONDS", 45, 5, OPENAI_TIMEOUT_MAX_SECONDS)
    max_retries = _env_int("ALPHAMATE_OPENAI_MAX_RETRIES", 1, 0, OPENAI_MAX_RETRIES_LIMIT)
    retry_backoff_seconds = _env_float(
        "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
        0.5,
        0.0,
        OPENAI_RETRY_BACKOFF_MAX_SECONDS,
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as res:
                data = json.loads(res.read().decode("utf-8"))
            _record_openai_usage(data, payload=payload, model=model)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt >= max_retries or not _is_retryable_openai_error(e):
                _record_openai_failure(e, payload=payload, model=model, attempt=attempt + 1)
                raise RuntimeError(str(e)) from e
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds)
        except json.JSONDecodeError as e:
            _record_openai_failure(e, payload=payload, model=model, attempt=attempt + 1)
            raise RuntimeError(str(e)) from e
    else:
        raise RuntimeError(str(last_error))

    if data.get("output_text"):
        output_text = str(data["output_text"]).strip()
        if output_text:
            return _OpenAiReviewText(output_text, response_status=data.get("status"))

    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    output_text = "\n".join(chunks).strip()
    if output_text:
        return _OpenAiReviewText(output_text, response_status=data.get("status"))

    incomplete = data.get("incomplete_details") if isinstance(data, dict) else None
    try:
        record_event(
            level="error",
            event_type="openai_review_empty_output",
            method="POST",
            path="/v1/responses",
            status_code=502,
            message="OpenAI review response did not contain user-visible text.",
            details={
                "review_type": str(payload.get("review_type") or "unknown"),
                "model": model,
                "response_status": str(data.get("status") or "unknown"),
                "incomplete_reason": str((incomplete or {}).get("reason") or ""),
            },
        )
    except Exception:
        pass
    raise RuntimeError("OpenAI response did not include output text.")


def _target_trade(trades: tuple[TradeSource, ...], target_trade_id=None):
    ordered = sorted(trades, key=lambda row: (row.trade_date, row.id or 0))
    if target_trade_id is not None:
        for trade in ordered:
            if str(trade.id) == str(target_trade_id):
                return trade
    return ordered[-1] if ordered else None


def _contexts_for_trades(trades: tuple[TradeSource, ...]):
    if type(trades) is not tuple or any(type(trade) is not TradeSource for trade in trades):
        raise SourceAdmissionError("AI contexts require admitted trades")
    by_ticker = {}
    for trade in trades:
        if trade.ticker:
            by_ticker.setdefault(trade.ticker, []).append(trade)
    contexts = []
    for ticker, ticker_trades in by_ticker.items():
        dates = [_parse_date(trade.trade_date) for trade in ticker_trades]
        start = min(dates) - datetime.timedelta(days=140)
        end = max(dates) + datetime.timedelta(days=45)
        df = _prepare_review_ohlcv(get_review_stock_ohlcv(ticker, _fmt8(start), _fmt8(end)))
        for trade in ticker_trades:
            # Admit producer output before quality checks or prompt projection.
            contexts.append(admit_analysis_context_source(
                _chart_context_for_trade(trade_payload(trade), df), memo_max_chars=_source_memo_limit()))
    return tuple(contexts)


def _trade_episode(trades: tuple[TradeSource, ...], target: TradeSource):
    symbol_trades = [row for row in trades if
                     (target.ticker and row.ticker == target.ticker) or
                     (not target.ticker and row.name == target.name)]
    ordered = sorted(symbol_trades, key=lambda row: (row.trade_date, row.id or 0))
    episodes, current, position = [], [], 0.0
    for row in ordered:
        current.append(row)
        position += row.quantity if row.side == "buy" else -row.quantity
        if row.side == "sell" and position <= 0:
            episodes.append(current)
            current, position = [], 0.0
    if current:
        episodes.append(current)
    for episode in episodes:
        if any(row is target for row in episode):
            return tuple(episode)
    return tuple(ordered)


def _compact_chart_snapshot(trades: tuple[TradeSource, ...]):
    if type(trades) is not tuple or any(type(trade) is not TradeSource for trade in trades):
        raise SourceAdmissionError("AI chart window requires admitted trades")
    try:
        produced = build_journal_charts(trades, review_source=True)
    except SourceAdmissionError:
        raise
    except Exception:
        return admit_chart_source({"kind": "unavailable", "reason": "provider_error"})
    if type(produced) is not dict or set(produced) != {"charts"} or type(produced["charts"]) is not list:
        raise SourceAdmissionError("invalid journal chart collection")
    # Every complete chart is admitted before choosing the first chart or any
    # candle window. Unknown fields and invalid late candles cannot disappear.
    admitted = tuple(admit_journal_chart_source(chart) for chart in produced["charts"])
    if not admitted:
        return admit_chart_source({"kind": "unavailable", "reason": "no_market_data"})
    chart = admitted[0]
    if type(chart) is UnavailableChartSource:
        return chart
    marker_times = {str(marker.time) for marker in chart.trade_markers}
    marker_indexes = [index for index, row in enumerate(chart.candles) if str(row.time) in marker_times]
    if marker_indexes:
        start = max(0, min(marker_indexes) - 25)
        end = min(len(chart.candles), max(marker_indexes) + 36)
        indexes = tuple(range(start, end))
    else:
        indexes = tuple(range(max(0, len(chart.candles) - 100), len(chart.candles)))
    if len(indexes) > 140:
        step = max(1, len(indexes) // 120)
        indexes = indexes[::step][-140:]
    return select_chart_candles(chart, indexes)


def _weighted_average(trades: tuple[TradeSource, ...], side: str):
    rows = [row for row in trades if row.side == side]
    total_quantity = sum(row.quantity for row in rows)
    return sum(row.price * row.quantity for row in rows) / total_quantity if total_quantity > 0 else None


def _safe_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_basic_review_focus(value: str | None) -> str:
    focus = str(value or "").strip().lower()
    return focus if focus in BASIC_REVIEW_FOCUS_LABELS else "balanced"


def _objective_review_snapshot(trades: tuple[TradeSource, ...]):
    """Calculate full-episode facts from admitted trades, then admit the result."""
    if type(trades) is not tuple or any(type(trade) is not TradeSource for trade in trades):
        raise SourceAdmissionError("AI objective requires admitted trades")
    if not trades:
        return admit_objective_source({"kind": "unavailable", "reason": "no_trades"})
    ordered = sorted(trades, key=lambda row: (row.trade_date, row.id or 0))
    review = build_review([trade_payload(trade) for trade in ordered])
    summary = review["summary"]
    buys = [trade for trade in ordered if trade.side == "buy"]
    sells = [trade for trade in ordered if trade.side == "sell"]
    return admit_objective_source({
        "symbol": {"ticker": ordered[-1].ticker, "name": ordered[-1].name},
        "period": {"first_trade_date": ordered[0].trade_date, "last_trade_date": ordered[-1].trade_date},
        "result": {
            "trade_count": summary["trade_count"], "closed_count": summary["closed_count"],
            "realized_pnl": summary["realized_pnl"], "realized_return_pct": summary["realized_return_pct"],
            "win_rate_pct": summary["win_rate_pct"],
            "weighted_buy_price": _weighted_average(tuple(ordered), "buy"),
            "weighted_sell_price": _weighted_average(tuple(ordered), "sell"),
            "total_fee": round(sum(trade.fee for trade in ordered), 2),
            "total_tax": round(sum(trade.tax for trade in ordered), 2),
            "buy_fill_count": len(buys), "sell_fill_count": len(sells),
            "open_quantity": round(max(0.0, sum(trade.quantity for trade in buys) - sum(trade.quantity for trade in sells)), 4),
            "symbol_count": len(review["by_symbol"]),
        },
    })


def _review_data_quality(source: ValidatedReviewSource):
    return review_data_quality(source)


def _default_decision_quality(data_quality: dict, missing: list[str]) -> dict:
    if data_quality.get("level") == "low":
        return {
            "label": "판단 보류",
            "explanation": "데이터 신뢰도가 낮아 당시 판단 품질을 확정하지 않고 확인이 필요한 상태로 남깁니다.",
        }
    if missing:
        return {
            "label": "판단 보류",
            "explanation": "사전 기준 또는 실제 이유 기록이 부족해 결과와 판단 품질을 분리해 확정하기 어렵습니다.",
        }
    return {
        "label": "보통",
        "explanation": "확인 가능한 거래·차트 근거를 바탕으로 평가하되 결과와 판단 품질을 별도로 봅니다.",
    }


def _default_basic_semantics(source: ValidatedReviewSource):
    data_quality, missing = _review_data_quality(source)
    result = source.objective.result
    observations = [item for chart in source.charts if type(chart) is CompactChartSource
                    for item in chart.rule_based_observations]
    good_points = []
    for observation in observations:
        if "좋음" in observation.title:
            good_points.append({
                "title": "체결 시점에서 확인된 강점",
                "detail": observation.detail,
            })
    if not good_points and result.sell_fill_count > 0 and not missing:
        good_points.append({
            "title": "행동과 기준을 비교할 단서가 있음",
            "detail": "매수·매도 체결과 사전 기록을 함께 비교할 수 있어 결과와 판단 품질을 나눠 점검할 수 있습니다.",
        })
    if not good_points:
        good_points.append({
            "title": "확인된 강점은 판단 보류",
            "detail": "사전 이유나 기준 기록이 부족해 확인된 강점은 추가 정보 확인 뒤 평가합니다.",
        })

    if data_quality.get("level") == "low":
        issue_title = "데이터 확인 필요"
        issue_detail = "체결가와 차트 기준이 크게 다르거나 차트가 없어 기술적 평가를 먼저 제한해야 합니다."
    elif "사전 매도 기준" in missing:
        issue_title = "사전 매도 기준 부재"
        issue_detail = "매도 후 가격이 더 올랐는지가 아니라, 수익 확정과 추세 종료를 구분한 기준이 사전에 있었는지 확인해야 합니다."
    elif "사전 위험/무효화 기준" in missing:
        issue_title = "사전 위험 기준 부재"
        issue_detail = "손실 결과만으로 판단하지 않고, 매수 전에 판단이 틀렸다고 볼 기준을 기록했는지 확인해야 합니다."
    else:
        issue_title = "판단 기준과 실제 행동 연결"
        issue_detail = "당시 가설과 실제 대응이 어떤 기준으로 연결됐는지 한 문장으로 남기는 것이 핵심 개선점입니다."

    return admit_semantic_source({
        "decision_quality": _default_decision_quality(data_quality, missing),
        "main_issue": issue_detail,
        "next_action": "주문 전에 이번 매매의 핵심 기준을 한 문장으로 기록하세요.",
        "good_points": good_points[:2],
        "main_improvement": {"title": issue_title, "detail": issue_detail},
        "next_trade_checks": [
            {"phase": "before_entry", "text": "진입 이유와 판단이 틀렸다고 볼 기준을 기록하기"},
            {"phase": "while_holding", "text": "보유 중 실제 흐름이 처음 가설과 일치하는지 확인하기"},
            {"phase": "before_exit", "text": "수익 확정과 추세 종료를 구분해 매도 이유를 기록하기"},
        ],
        "lesson": {
            "title": "좋은 매도는 최고가 매도가 아닙니다",
            "concept": "매도 후 추가 상승이라는 사후 결과와 매도 당시 판단의 품질은 분리해 봐야 합니다.",
            "applied_to_this_trade": issue_detail,
        },
    }, "basic")


def _default_advanced_semantics(source: ValidatedReviewSource):
    trades = source.trades
    data_quality, missing = _review_data_quality(source)
    observations = [item for chart in source.charts if type(chart) is CompactChartSource
                    for item in chart.rule_based_observations]
    buy_observation = next((item for item in observations if "매수" in item.title), None)
    sell_observation = next((item for item in observations if "매도" in item.title), None)
    evidence = [item.detail for item in (buy_observation, sell_observation) if item is not None]
    uncertainty = list(missing[:3])
    if data_quality.get("level") == "low" and data_quality.get("reasons"):
        uncertainty.extend(data_quality["reasons"][:2])
    entry_label = "근거 부족" if "실제 매매 이유" in missing or not buy_observation else "근거 일부"
    if buy_observation and "좋음" in buy_observation.title:
        entry_label = "근거 충분"
    risk_missing = "사전 위험/무효화 기준" in missing
    exit_missing = "사전 매도 기준" in missing
    return admit_semantic_source({
        "decision_quality": _default_decision_quality(data_quality, missing),
        "main_issue": (
            "체결가와 차트 기준 가격 차이를 먼저 확인해야 합니다."
            if data_quality.get("level") == "low"
            else "사전 기준이 실제 대응과 어떻게 연결됐는지 확인해야 합니다."
        ),
        "next_action": "다음 주문 전 진입·위험·매도 기준을 각각 짧게 기록하세요.",
        "entry_review": {
            "evidence": evidence[:4] or ["차트와 매매 이유 근거가 충분하지 않습니다."],
            "uncertainty": uncertainty[:4] or ["당시 가설을 확인할 추가 기록이 없습니다."],
            "invalidation": "기록 없음" if risk_missing else "사전에 기록한 무효화 기준과 실제 대응을 대조합니다.",
            "assessment": {
                "label": entry_label,
                "explanation": "매수 당시 알 수 있었던 정보와 사전 가설 기록을 중심으로 판단합니다.",
            },
        },
        "risk_review": {
            "planned_rule": "기록 없음" if risk_missing else "사전 위험 기준 기록을 확인합니다.",
            "actual_response": "매도 체결이 없어 실제 방어 대응은 판단 보류" if not any(trade.side == "sell" for trade in trades) else "실제 매도 대응과 사전 기준의 일치 여부를 확인합니다.",
            "assessment": {
                "label": "근거 부족" if risk_missing else "근거 일부",
                "explanation": "손실 또는 수익 결과가 아니라 사전 계획과 실제 행동의 일치를 평가합니다.",
            },
        },
        "exit_review": {
            "profit_taking_assessment": "판단 보류" if exit_missing else "사전 수익 확정 기준과 실제 매도를 비교",
            "trend_exit_assessment": "판단 보류" if exit_missing else "당시 추세 종료 근거와 실제 매도를 비교",
            "explanation": "매도 후 가격이 오른 사실만으로 매도 실패라고 판단하지 않습니다.",
        },
        "detailed_analysis": [
            {"title": item.title, "detail": item.detail}
            for item in observations[:5]
        ],
        "next_trade_playbook": {
            "before_entry": ["진입 근거를 한 가지로 기록하기", "판단이 틀렸다고 볼 기준을 기록하기"],
            "while_holding": ["실제 흐름이 처음 가설과 일치하는지 점검하기"],
            "before_exit": ["수익 확정과 추세 종료 관점을 나눠 매도 이유 기록하기"],
        },
        "lesson": {
            "title": "사전 기준과 사후 결과를 분리하기",
            "concept": "판단의 질은 결과보다 당시 알 수 있었던 정보와 주문 전 기준으로 평가해야 합니다.",
            "applied_to_this_trade": "매도 후 상승 또는 손실 크기만으로 당시 판단을 단정하지 않고 기록된 기준을 먼저 확인합니다.",
            "next_trade_application": "진입·위험·매도 기준을 주문 전에 각각 기록합니다.",
        },
        "reflection_questions": [
            "매수 직전 어떤 조건이 깨지면 내 판단이 틀렸다고 보려고 했는가?",
            "이번 매도는 계획된 수익 확정이었는가, 순간적인 불안에 의한 행동이었는가?",
        ],
    }, "advanced")


class _StructuredModelDecodeError(ValueError):
    """JSON parsing/conversion failure before semantic admission."""


class _DuplicateStructuredJsonKeyError(_StructuredModelDecodeError):
    """Ambiguous model objects are terminal, even when both values are safe."""


def _unique_structured_json_object(pairs):
    """JSON supplies decoded keys for every object, including inside arrays."""
    decoded = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicateStructuredJsonKeyError("duplicate structured JSON key")
        decoded[key] = value
    return decoded


def _decode_structured_model_output(value):
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_structured_json_object)
    except _StructuredModelDecodeError:
        raise
    except (TypeError, ValueError, RecursionError, OverflowError) as error:
        # ValueError includes JSONDecodeError; semantic errors stay outside.
        raise _StructuredModelDecodeError("invalid structured JSON") from error
    return decoded if isinstance(decoded, dict) else None


_FINAL_REVIEW_MAX_NODES = 4096
_FINAL_REVIEW_MAX_DEPTH = 32
_SERVER_OWNED_REVIEW_PATHS = frozenset({
    ("schema_version",), ("review_type",), ("objective",),
    ("summary", "data_confidence"), ("summary", "missing_information"),
})
_FIXED_SAFE_REVIEW_SUMMARY = UNAVAILABLE_REVIEW_TEXT


def _text_leaf_paths(value, *, excluded_paths=frozenset(), allow_scalars=False, max_nodes=_FINAL_REVIEW_MAX_NODES):
    """Walk every text leaf with bounded depth/size; reject unknown shapes."""

    leaves = []
    stack = [((), value, 0, frozenset())]
    visited = 0
    while stack:
        path, node, depth, ancestors = stack.pop()
        if path in excluded_paths:
            continue
        visited += 1
        if visited > max_nodes or depth > _FINAL_REVIEW_MAX_DEPTH:
            raise ValueError("structured review traversal limit exceeded")
        if isinstance(node, str):
            leaves.append((path, node))
        elif isinstance(node, (dict, list)):
            if id(node) in ancestors:
                raise ValueError("cyclic structured review container")
            child_ancestors = ancestors | {id(node)}
            if isinstance(node, dict):
                if any(not isinstance(key, str) for key in node):
                    raise ValueError("non-string structured review key")
                stack.extend((path + (key,), item, depth + 1, child_ancestors) for key, item in reversed(list(node.items())))
            else:
                stack.extend((path + (index,), item, depth + 1, child_ancestors) for index, item in reversed(list(enumerate(node))))
        elif not (allow_scalars and (node is None or type(node) in (bool, int, float))):
            raise ValueError("unsupported structured review value")
    return leaves


def _structured_string_values(value):
    for _path, field in _text_leaf_paths(value, allow_scalars=True):
        yield field


def _prepare_structured_model_output(value, *, payload: dict, model: str) -> tuple[object | None, list[str], bool]:
    """Return validated semantic output, safety rule ids, and rejection flag."""

    raw_text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    # Decode before safety selection so neither value order nor plain/escaped
    # forbidden text can turn a duplicate-key failure into a sealed fallback.
    candidate = _decode_structured_model_output(raw_text)
    _filtered_text, safety_rule_ids = _filter_openai_review_safety(raw_text, payload=payload, model=model)
    if safety_rule_ids:
        return None, safety_rule_ids, True
    for field in _structured_string_values(candidate):
        _, safety_rule_ids = _filter_openai_review_safety(
            field,
            payload=payload,
            model=model,
            response_status=getattr(value, "response_status", None),
        )
        if safety_rule_ids:
            return None, safety_rule_ids, True
    admitted = admit_semantic_source(candidate, payload["review_type"])
    return admitted, [], False


def _model_text_leaves(structured: dict):
    if not isinstance(structured, dict) or structured.get("schema_version") != STRUCTURED_REVIEW_SCHEMA_VERSION:
        raise ValueError("invalid final structured review")
    review_type = structured.get("review_type")
    if review_type not in ("basic", "advanced") or not isinstance(structured.get("summary"), dict) or not isinstance(structured.get(review_type), dict):
        raise ValueError("incomplete final structured review")
    return _text_leaf_paths(structured, excluded_paths=_SERVER_OWNED_REVIEW_PATHS)


def _validate_final_review(structured: dict, display_snapshot: dict, covered_paths: set[tuple], *,
                           payload: dict, model: str, response_status: str | None):
    """Check exact semantic coverage and the approved canonical text."""
    try:
        leaves = _model_text_leaves(structured)
        if covered_paths != {path for path, _value in leaves}:
            raise ReviewDisplayContractError("unmapped semantic field")
        canonical = flatten_document(display_snapshot)
        server_visible = _text_leaf_paths({
            "data_confidence": structured["summary"].get("data_confidence"),
            "missing_information": structured["summary"].get("missing_information"),
        }, allow_scalars=True)
    except (TypeError, KeyError, ValueError, RecursionError):
        return "invalid_structured_output", []
    for text in [*(value for _path, value in leaves), *(value for _path, value in server_visible), canonical]:
        _filtered, rule_ids = _filter_openai_review_safety(
            text, payload=payload, model=model, response_status=response_status,
        )
        if rule_ids:
            return "safety_rejected", rule_ids
    return None, []


_ENVELOPE_MAX_NODES = 100_000


def _validated_control_string(path: tuple, value: str) -> bool:
    """Only closed control values are exempt from free-text checks."""

    key = path[-1] if path else None
    allowed = {
        "status": {"ready", "error", "missing_key", "empty"},
        "source": {"openai", "chart-rules", "none"},
        "internal_status": {"safety_rejected", "invalid_structured_output"},
        "review_type": {"basic", "advanced"},
        "schema_version": {STRUCTURED_REVIEW_SCHEMA_VERSION, "review-display.v1"},
        "phase": {"before_entry", "while_holding", "before_exit"},
        "side": {"buy", "sell"},
        "level": {"low", "medium", "high"},
    }
    if key in allowed:
        return value in allowed[key]
    if key == "model":
        return bool(re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", value))
    return False


def _validate_visible_envelope(value, *, payload: dict, model: str, response_status: str | None,
                               record_rejection: bool = True):
    try:
        leaves = _text_leaf_paths(value, allow_scalars=True, max_nodes=_ENVELOPE_MAX_NODES)
        for path, document in _display_snapshots(value):
            if path and path[-1] == "display_snapshot":
                validate_document(document)
    except (TypeError, ValueError, RecursionError):
        return "invalid_structured_output", []
    checked = set()
    for path, text in leaves:
        if _validated_control_string(path, text) or text in checked:
            continue
        checked.add(text)
        if "[데이터 확인]" in text or "[합리적 추론]" in text:
            return "safety_rejected", ["unsupported_legacy_annotation"]
        if record_rejection:
            _filtered, rule_ids = _filter_openai_review_safety(
                text, payload=payload, model=model, response_status=response_status,
            )
        else:
            rule_ids = _matched_prohibited_trade_guidance_rule_ids(text)
        if rule_ids:
            return "safety_rejected", rule_ids
    return None, []


def _display_snapshots(value):
    """Find only declared canonical documents; never compose dictionary display text."""
    stack = [((), value)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "display_snapshot":
                    yield path + (key,), child
                else:
                    stack.append((path + (key,), child))
        elif isinstance(node, list):
            stack.extend((path + (index,), child) for index, child in enumerate(node))


def _normalized_semantic_review(semantic, review_type: str) -> dict:
    """Render normalized semantics before any confidence/default substitution."""

    semantic = semantic_payload(semantic)
    return {
        "schema_version": STRUCTURED_REVIEW_SCHEMA_VERSION,
        "review_type": review_type,
        "objective": {},
        "summary": {key: semantic[key] for key in ("decision_quality", "main_issue", "next_action")},
        review_type: {key: value for key, value in semantic.items()
                      if key not in {"decision_quality", "main_issue", "next_action"}},
    }


_CHART_METRIC_TEXT = {
    "price_vs_close_pct": ("체결가와 봉 종가 차이", "%"),
    "after_5_bars": ("이후 5개 봉 변화", "%"),
    "after_later_bars": ("이후 봉 변화", "%"),
    "ma5": ("5기간 이동평균", "원"),
    "ma20": ("20기간 이동평균", "원"),
    "rsi14": ("RSI 14", ""),
    "return_10d_before": ("이전 10일 변화", "%"),
    "volume_ratio_20d": ("20일 거래량 비율", "배"),
    "next_5d_return": ("이후 5일 변화", "%"),
    "next_20d_return": ("이후 20일 변화", "%"),
}


def _canonical_chart_review(value: dict) -> dict:
    if type(value) is not dict or set(value) - {"trade_id", "title", "detail", "metrics"}:
        raise ReviewDisplayContractError("unknown chart review field")
    title, detail = value.get("title"), value.get("detail")
    if type(title) is not str or type(detail) is not str or not title or not detail:
        raise ReviewDisplayContractError("invalid chart review text")
    metrics = value.get("metrics") or {}
    if type(metrics) is not dict or set(metrics) - set(_CHART_METRIC_TEXT):
        raise ReviewDisplayContractError("unknown chart metric")
    lines = [f"{title}: {detail}"]
    for key, (label, unit) in _CHART_METRIC_TEXT.items():
        if key not in metrics or metrics[key] is None:
            continue
        metric = metrics[key]
        if type(metric) in (int, float):
            lines.append(f"{label}: {metric}{unit}")
        elif type(metric) is dict and set(metric) == {"label", "unit", "description", "value"}:
            if any(type(metric[field]) is not str for field in ("label", "unit", "description")):
                raise ReviewDisplayContractError("invalid chart metric text")
            if type(metric["value"]) not in (int, float, type(None)):
                raise ReviewDisplayContractError("invalid chart metric value")
            lines.append(f"{metric['label']}: {metric['value']}{metric['unit']} — {metric['description']}")
        else:
            raise ReviewDisplayContractError("invalid chart metric value")
    result = copy.deepcopy(value)
    result["display_snapshot"] = compile_literal_lines(lines)
    return result


def _canonical_marker(value: dict) -> dict:
    if type(value) is not dict:
        raise ReviewDisplayContractError("invalid chart marker")
    if any(type(field) is str and key not in {"time", "position", "color", "shape", "text", "side"}
           for key, field in value.items()):
        raise ReviewDisplayContractError("unmapped chart marker text")
    result = copy.deepcopy(value)
    label = result.get("text")
    if label:
        if type(label) is not str:
            raise ReviewDisplayContractError("invalid marker label")
        result["display_snapshot"] = compile_literal_text(label)
    tooltip = result.get("tooltip")
    if tooltip is not None:
        if type(tooltip) is not dict or type(tooltip.get("label")) is not str:
            raise ReviewDisplayContractError("invalid marker tooltip")
        if any(type(field) is str and key != "label" for key, field in tooltip.items()):
            raise ReviewDisplayContractError("unmapped tooltip text")
        count = tooltip.get("count")
        title = tooltip["label"] + (f" {count}건" if type(count) is int and count > 1 else "")
        lines = [title]
        if tooltip.get("avg_price") is not None or tooltip.get("total_quantity") is not None:
            lines.append(f"평균 {tooltip.get('avg_price', 0):,.0f}원 · 수량 {tooltip.get('total_quantity', 0)}")
        prices = tooltip.get("prices") or []
        if prices:
            if type(prices) is not list or any(type(price) not in (int, float) for price in prices):
                raise ReviewDisplayContractError("invalid tooltip prices")
            lines.append(", ".join(f"{price:,.0f}" for price in prices) + "원")
        if tooltip.get("profit_amount") is not None:
            lines.append(f"실현 {tooltip['profit_amount']:+,.0f}원 · {tooltip.get('return_rate') or 0:+}%")
        tooltip["display_snapshot"] = compile_literal_lines(lines)
    for trade in result.get("trades") or []:
        if type(trade) is not dict or any(type(field) is str and key != "date" for key, field in trade.items()):
            raise ReviewDisplayContractError("unmapped marker trade text")
    return result


def _canonical_chart(value: dict) -> dict:
    if type(value) is not dict:
        raise ReviewDisplayContractError("invalid chart")
    if not value:
        return {}
    allowed = {"ticker", "name", "label", "timeframe", "interval", "period", "period_label", "source",
               "candles", "markers", "trade_markers", "reviews", "rule_based_observations"}
    if set(value) - allowed:
        raise ReviewDisplayContractError("unknown chart field")
    result = copy.deepcopy(value)
    candles = result.get("candles") or []
    if type(candles) is not list:
        raise ReviewDisplayContractError("invalid candles")
    for candle in candles:
        if type(candle) is not dict or any(type(field) is str and key not in {"time", "label", "t"}
                                           for key, field in candle.items()):
            raise ReviewDisplayContractError("unmapped candle text")
    lines = ["매매 차트"]
    for key, label in (("name", "종목"), ("ticker", "종목 코드"), ("label", "차트 이름"),
                       ("timeframe", "차트 주기"),
                       ("interval", "봉 간격"), ("period", "기간"), ("period_label", "기간"),
                       ("source", "차트 출처")):
        field = result.get(key)
        if field:
            if type(field) is not str:
                raise ReviewDisplayContractError("invalid chart header")
            lines.append(f"{label}: {field}")
    result["display_snapshot"] = compile_literal_lines(lines)
    for key in ("markers", "trade_markers"):
        if key in result:
            if type(result[key]) is not list:
                raise ReviewDisplayContractError("invalid chart markers")
            result[key] = [_canonical_marker(marker) for marker in result[key]]
    for key in ("reviews", "rule_based_observations"):
        if key in result:
            if type(result[key]) is not list:
                raise ReviewDisplayContractError("invalid chart reviews")
            result[key] = [_canonical_chart_review(review) for review in result[key]]
    return result


def _canonical_context(value: dict) -> dict:
    if type(value) is not dict:
        raise ReviewDisplayContractError("invalid chart context")
    result = copy.deepcopy(value)
    lines = ["차트 컨텍스트"]
    fields = (("error", "오류"), ("date", "체결일"), ("market_date", "시장일"),
              ("ticker", "종목 코드"), ("name", "종목"), ("side", "구분"), ("memo", "메모"))
    for key, label in fields:
        field = result.get(key)
        if field:
            if type(field) is not str:
                raise ReviewDisplayContractError("invalid context text")
            lines.append(f"{label}: {field}")
    trade = result.get("trade")
    if trade is not None:
        if type(trade) is not dict:
            raise ReviewDisplayContractError("invalid context trade")
        trade_fields = (("trade_date", "체결일"), ("ticker", "종목 코드"), ("name", "종목"),
                        ("side", "구분"), ("memo", "메모"), ("source", "기록 출처"))
        for key, label in trade_fields:
            field = trade.get(key)
            if field:
                if type(field) is not str:
                    raise ReviewDisplayContractError("invalid context trade text")
                lines.append(f"거래 {label}: {field}")
        if trade.get("name") or trade.get("memo"):
            lines.append(f"거래 종목 및 메모: {trade.get('name') or ''} {trade.get('memo') or ''}")
        if any(type(field) is str and key not in dict(trade_fields) for key, field in trade.items()):
            raise ReviewDisplayContractError("unmapped context trade text")
    if any(type(field) is str and key not in dict(fields) for key, field in result.items()):
        raise ReviewDisplayContractError("unmapped context text")
    result["display_snapshot"] = compile_literal_lines(lines)
    return result


def _canonical_trade(value: dict) -> dict:
    if type(value) is not dict:
        raise ReviewDisplayContractError("invalid review trade")
    result = copy.deepcopy(value)
    labels = (("trade_date", "체결일"), ("ticker", "종목 코드"), ("name", "종목"),
              ("side", "구분"), ("memo", "메모"), ("source", "기록 출처"))
    lines = ["매매 기록"]
    for key, label in labels:
        field = result.get(key)
        if field:
            if type(field) is not str:
                raise ReviewDisplayContractError("invalid trade text")
            lines.append(f"{label}: {field}")
    if result.get("name") or result.get("memo"):
        lines.append(f"종목 및 메모: {result.get('name') or ''} {result.get('memo') or ''}")
    if any(type(field) is str and key not in dict(labels) for key, field in result.items()):
        raise ReviewDisplayContractError("unmapped trade text")
    result["display_snapshot"] = compile_literal_lines(lines)
    return result


def _canonical_review_extras(extras: dict) -> dict:
    if set(extras) - {"chart_snapshot", "chart_snapshots", "chart_contexts", "chart_reviews"}:
        raise ReviewDisplayContractError("unknown review content field")
    result = copy.deepcopy(extras)
    if "chart_snapshot" in result:
        result["chart_snapshot"] = _canonical_chart(result["chart_snapshot"])
    if "chart_snapshots" in result:
        result["chart_snapshots"] = [_canonical_chart(chart) for chart in result["chart_snapshots"]]
    if "chart_contexts" in result:
        result["chart_contexts"] = [_canonical_context(context) for context in result["chart_contexts"]]
    if "chart_reviews" in result:
        result["chart_reviews"] = [_canonical_chart_review(review) for review in result["chart_reviews"]]
    return result


def safe_legacy_history_snapshot(value: dict, *, paired_storage_enabled=True) -> dict:
    """Use one closed whole-record boundary for every history read surface."""
    from backend.core.review_history_adapter import adapt_history_record

    return adapt_history_record(
        value, unsafe_text=_contains_prohibited_trade_guidance,
        project_trade=_canonical_trade, project_chart=_canonical_chart,
        project_context=_canonical_context, project_card=_canonical_chart_review,
        paired_storage_enabled=paired_storage_enabled,
    )


def admit_ai_review_history_candidate(*, metadata: dict, result: dict) -> dict:
    """Check the exact new row through the read adapter without repairing it."""
    record = {
        # Storage assigns these two fields. Fixed valid stand-ins let the same
        # whole-record boundary check every caller-supplied field before INSERT.
        "id": 1, "created_at": "1970-01-01T00:00:00+00:00",
        "review_type": result["review_type"], "model": result.get("model") or "",
        "source": result["source"], "ai_review": copy.deepcopy(result),
        "access_snapshot": copy.deepcopy(result.get("access", {})),
    }
    if type(metadata) is not dict or record.keys() & metadata.keys():
        raise ReviewDisplayContractError("invalid history candidate metadata")
    record.update(copy.deepcopy(metadata))
    admitted = safe_legacy_history_snapshot(record)
    if admitted["history_read_status"] != "canonical":
        raise ReviewDisplayContractError("history candidate failed closed admission")
    # New metadata already owns its deterministic documents and complete trades.
    # Do not save a candidate that a read would silently project or prune.
    if any(admitted[key] != record[key] for key in metadata):
        raise ReviewDisplayContractError("history candidate differs from read projection")
    return {key: value for key, value in record.items() if key not in {"id", "created_at"}}


_NEW_HISTORY_BASIC_QUOTA = dict.fromkeys((
    "signup_remaining", "free_daily_remaining", "free_daily_max_remaining", "free_available_now",
    "rewarded_ad_available", "rewarded_ad_daily_remaining", "free_monthly_remaining",
    "free_monthly_limit", "pro_monthly_remaining", "purchased_remaining",
))
_NEW_HISTORY_ADVANCED_QUOTA = dict.fromkeys((
    "signup_remaining", "pro_monthly_remaining", "weekly_reward_remaining", "weekly_advanced_granted",
    "weekly_ad_views", "weekly_ad_views_needed", "purchased_remaining", "max_hold",
))
_NEW_HISTORY_ACCESS_SHAPE = {
    **dict.fromkeys(("auth_mode", "plan", "review_type", "source", "refunded", "idempotent_replay")),
    "quota": {"basic": _NEW_HISTORY_BASIC_QUOTA, "advanced": _NEW_HISTORY_ADVANCED_QUOTA},
    "wallet": {
        "plan": None, "basic": _NEW_HISTORY_BASIC_QUOTA, "advanced": _NEW_HISTORY_ADVANCED_QUOTA,
        "products": dict.fromkeys(
            ("basic_review_15", "basic_review_25", "advanced_review_10", "advanced_review_20"),
            dict.fromkeys(("kind", "quantity", "price_krw"))),
        "settings": {
            "allow_advanced_ticket_for_basic": None,
            "ad_policy": dict.fromkeys((
                "basic_reviews_per_rewarded_ad", "rewarded_basic_daily_max", "ads_per_advanced_ticket",
                "force_rewarded_ad_chain", "preferred_rewarded_ad_sequence",
            )),
            "free_policy": dict.fromkeys((
                "daily_basic", "rewarded_basic_daily_max", "monthly_basic_max", "weekly_advanced_max",
            )),
        },
        "validity": dict.fromkeys((
            "timezone", "daily_reset_at", "weekly_reset_at", "monthly_reset_at", "signup_pass_expires_at",
            "purchased_pass_expires_at", "weekly_reward_expires_at", "pro_allowance_resets_at",
        )),
    },
}


def _require_new_history_access_shape(value, shape=_NEW_HISTORY_ACCESS_SHAPE):
    """Both production wallet producers emit every field, including null leaves."""
    if type(value) is not dict or set(value) != set(shape):
        raise ReviewDisplayContractError("history candidate has incomplete production access")
    for key, child_shape in shape.items():
        if child_shape is not None:
            _require_new_history_access_shape(value[key], child_shape)


def admit_new_ai_review_history_candidate(*, metadata: dict, result: dict, snapshot) -> dict:
    """Require a complete new record and its original sealed display projections."""
    required = {
        "status", "source", "review_type", "model", "summary", "display_snapshot", "structured_review",
        "chart_display_snapshot", "chart_contexts", "chart_reviews", "access",
        "chart_snapshot" if result.get("review_type") == "basic" else "chart_snapshots",
    } if type(result) is dict else set()
    if (type(result) is not dict or not required <= set(result)
            or set(result) - required - {"internal_status"}
            or result["status"] not in {"ready", "missing_key"}
            or type(snapshot) is not ApprovedReviewSnapshot):
        raise ReviewDisplayContractError("history candidate lacks required new canonical fields or seal")
    _require_new_history_access_shape(result["access"])
    # Keep the legacy whole-record contract for types/content/projections, with
    # an additional required shape only at the new-write boundary.
    candidate = admit_ai_review_history_candidate(metadata=metadata, result=result)
    envelope = json.loads(snapshot.json_text)
    expected = {key: envelope[key] for key in ("status", "source", "review_type")}
    expected.update(display_snapshot=envelope["body"], summary=admit_legacy_body(envelope["body"]).summary,
                    chart_display_snapshot=approved_chart_display_snapshot(snapshot))
    actual = {key: candidate["ai_review"][key] for key in expected}
    options = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":"), "allow_nan": False}
    if json.dumps(actual, **options) != json.dumps(expected, **options):
        raise ReviewDisplayContractError("history candidate differs from sealed canonical projections")
    return candidate


def _build_structured_review(source: ValidatedReviewSource) -> dict:
    """Project the selected admitted semantic variant without default repair."""
    return structured_review_payload(source)


def _basic_evaluation_anchor(source: ValidatedReviewSource) -> dict:
    result = source.objective.result
    trade_by_id = {trade.id: trade for trade in source.trades if trade.id is not None}
    evidence = []
    for chart in source.charts:
        if type(chart) is not CompactChartSource:
            continue
        for observation in chart.rule_based_observations:
            if type(observation) is not TechnicalObservationSource:
                continue
            trade = trade_by_id.get(observation.trade_id)
            metrics = observation.metrics
            evidence.append({
                "trade_id": observation.trade_id, "side": trade.side if trade is not None else "unknown",
                "trade_date": trade.trade_date if trade is not None else None,
                "trade_price": trade.price if trade is not None else None,
                "rule_grade": observation.title, "rule_detail": observation.detail,
                "price_vs_candle_close_pct": metrics.price_vs_close_pct,
                "after_5_bars_pct": metrics.after_5_bars, "after_later_bars_pct": metrics.after_later_bars,
                "ma5": metrics.ma5, "ma20": metrics.ma20,
            })
    direction = ("open_or_incomplete" if result.weighted_buy_price is None or result.weighted_sell_price is None
                 else "profit" if result.realized_pnl > 0 else "loss" if result.realized_pnl < 0 else "flat")
    return {"symbol": {"ticker": source.objective.symbol.ticker, "name": source.objective.symbol.name},
            "outcome": {"direction": direction, "realized_pnl": result.realized_pnl,
                        "realized_return_pct": result.realized_return_pct,
                        "weighted_buy_price": result.weighted_buy_price, "weighted_sell_price": result.weighted_sell_price,
                        "buy_fill_count": result.buy_fill_count, "sell_fill_count": result.sell_fill_count},
            "execution_evidence": evidence}


def _fallback_basic_text(source: ValidatedReviewSource) -> str:
    return serialize_compatibility_summary(compile_basic_fallback_body(source))


def _fallback_advanced_text(source: ValidatedReviewSource) -> str:
    return serialize_compatibility_summary(compile_advanced_fallback_body(source))


def _fixed_safe_structured_review(review_type: str) -> dict:
    return structured_review_payload(unavailable_review_source(review_type))


def _legacy_compatibility_rejection(review_type, internal_status=None):
    """A failed body admission exposes no model/semantic/display content."""
    result = {"status": "error", "source": "none", "review_type": review_type,
              "model": None, "summary": "", "chart_contexts": [], "chart_reviews": [],
              "internal_status": ("safety_rejected" if internal_status == "safety_rejected"
                                  else "invalid_structured_output")}
    result["chart_snapshot" if review_type == "basic" else "chart_snapshots"] = {} if review_type == "basic" else []
    return result


def _canonical_history_metadata(candidate):
    """Freeze the existing opt-in history surfaces before body approval."""
    return {
        "ticker": candidate["ticker"], "name": candidate["name"],
        "trade_date": candidate["trade_date"], "target_trade_id": candidate["target_trade_id"],
        "trade_snapshot": _canonical_trade(candidate["trade_snapshot"]),
        "recent_trades_snapshot": [_canonical_trade(trade) for trade in candidate["recent_trades_snapshot"]],
        "chart_snapshot": {"charts": [_canonical_chart(chart) for chart in candidate["charts"]]},
    }


def _finalize_ai_review(
    raw_response, *, source: ValidatedReviewSource | None, review_type: str, payload: dict, model: str,
    request_failed: bool = False, source_failure: str | None = None,
    history_state: dict | None = None, approval_state: dict | None = None,
) -> dict:
    """Decide safety, select admitted variants, compile and seal once approved.

    Source failure is sticky and skips both model parsing and default fallback.
    The sealed snapshot remains internal; legacy route keys stay unchanged.
    """
    if history_state is not None:
        history_state["approved"] = None
    if approval_state is not None:
        approval_state["snapshot"] = None
    response_status = getattr(raw_response, "response_status", None)
    had_model_output = bool(raw_response)
    semantic = None
    internal_status = source_failure
    if source_failure is None:
        if type(source) is not ValidatedReviewSource:
            internal_status = source_failure = "invalid_structured_output"
        else:
            try:
                source_failure = _source_safety_issue(source, payload=payload, model=model,
                                                      response_status=response_status, history_state=history_state)
            except (TypeError, AttributeError, ValueError, RecursionError, OverflowError):
                source_failure = "invalid_structured_output"
            internal_status = source_failure
    if source_failure is None and had_model_output:
        try:
            semantic, rule_ids, _rejected = _prepare_structured_model_output(raw_response, payload=payload, model=model)
        except _StructuredModelDecodeError:
            return _legacy_compatibility_rejection(review_type)
        except (TypeError, ValueError, RecursionError, OverflowError):
            semantic, rule_ids = None, []
        if rule_ids:
            internal_status = "safety_rejected"
        elif semantic is None:
            internal_status = "invalid_structured_output"
        else:
            # Raw/decode/admitted normalized safety is decided before the
            # existing low-confidence fallback can replace model semantics.
            semantic_review = _normalized_semantic_review(semantic, review_type)
            try:
                normalized_display, normalized_paths = compile_structured_review(semantic_review)
                issue, _rules = _validate_final_review(
                    semantic_review, normalized_display, normalized_paths, payload=payload,
                    model=model, response_status=response_status)
                if not issue:
                    # A low-confidence selection must not hide a rejected model
                    # body. Admission generates no wire before sealing.
                    validate_legacy_body(normalized_display)
            except LegacyCompatibilityContractError:
                return _legacy_compatibility_rejection(review_type, internal_status)
            except (TypeError, KeyError, ValueError, RecursionError) as error:
                issue = "safety_rejected" if "unsupported legacy display annotation" in str(error) else "invalid_structured_output"
            if issue:
                internal_status, semantic = issue, None

    history_metadata_json = None
    history_prepared_content = None

    def attempt(active_semantic, *, fixed=False):
        nonlocal history_metadata_json, history_prepared_content
        history_metadata_json = None
        history_prepared_content = None
        structured = None
        try:
            if fixed:
                selected = unavailable_review_source(review_type)
                structured = _fixed_safe_structured_review(review_type)
            else:
                quality, _missing = _review_data_quality(source)
                fallback = (_default_advanced_semantics(source) if review_type == "advanced"
                            else _default_basic_semantics(source))
                chosen = fallback if active_semantic is None or quality["level"] == "low" else active_semantic
                ready = active_semantic is not None and internal_status is None and source_failure is None
                status = "ready" if ready else "error" if had_model_output or request_failed or internal_status else "missing_key"
                selected = finish_review_source(
                    source, semantic=chosen, status=status, origin="openai" if ready else "chart-rules",
                    notice=None if ready else "AI 복기 결과를 확인할 수 없어 기본 복기를 표시합니다.")
                structured = _build_structured_review(selected)
            body, covered_paths = compile_structured_review(structured)
            issue, _rules = _validate_final_review(structured, body, covered_paths, payload=payload,
                                                   model=model, response_status=response_status)
            if issue:
                return None, None, issue
            body = compile_review_body(selected)
            candidate = compile_review_envelope(selected)
            if candidate["body"] != body:
                raise ReviewDisplayContractError("structured producer differs from admitted DTO projection")
            validate_review_envelope(candidate)
            documents = [candidate["body"], candidate["notice"],
                         *(card["display"] for card in candidate["chart_cards"]),
                         *(trade["name"] for trade in candidate["trades"]),
                         *(surface for chart in candidate["charts"] for surface in (chart["header"], chart["tab"])),
                         *(surface for chart in candidate["charts"] for marker in chart["markers"]
                           for surface in (marker["label"], marker["tooltip"]))]
            for document in documents:
                if document is not None:
                    _filtered, rules = _filter_openai_review_safety(document["canonical_text"], payload=payload,
                                                                   model=model, response_status=response_status)
                    if rules:
                        return None, None, "safety_rejected"
            validate_legacy_body(candidate["body"])
            if selected.status in {"ready", "missing_key"} and history_state is not None:
                metadata = _canonical_history_metadata(copy.deepcopy(history_state["candidate"]))
                # Validate the independent value actually retained for persistence.
                metadata_json = json.dumps(metadata, ensure_ascii=False, allow_nan=False)
                issue, _rules = _validate_visible_envelope(
                    json.loads(metadata_json), payload=payload, model=model, response_status=response_status)
                if issue:
                    return None, None, issue
                history_metadata_json = metadata_json
            snapshot = seal_review_envelope(candidate)
            body = json.loads(snapshot.json_text)["body"]
            ready = selected.status == "ready"
            result = {"status": selected.status, "source": selected.origin, "review_type": review_type,
                      "model": model if ready else None, "summary": admit_legacy_body(body).summary,
                      "display_snapshot": body, "structured_review": structured,
                      "chart_contexts": [], "chart_reviews": []}
            result["chart_snapshot" if review_type == "basic" else "chart_snapshots"] = {} if review_type == "basic" else []
            if internal_status:
                result["internal_status"] = internal_status
            if history_metadata_json is not None:
                # Emit the existing approved projection here once. Preparation
                # accepts complete content only and never restores missing data.
                result["chart_display_snapshot"] = approved_chart_display_snapshot(snapshot)
                admit_ai_review_history_candidate(metadata=json.loads(history_metadata_json), result=result)
                history_prepared_content = prepare_history_content(
                    metadata=json.loads(history_metadata_json), result=result, snapshot=snapshot,
                    finalizer_model=model if ready else None, _authority=_HISTORY_CONTENT_CAPTURE,
                )
            return result, snapshot, None
        except LegacyCompatibilityContractError:
            # Terminal admission failure, including fallback/fixed variants.
            # Do not retry another template or publish an approved snapshot.
            return _legacy_compatibility_rejection(review_type, internal_status), None, None
        except (TypeError, KeyError, ValueError, RecursionError, OverflowError) as error:
            if "unsupported legacy display annotation" in str(error):
                return None, None, "safety_rejected"
            if structured is not None:
                issue, _rules = _validate_visible_envelope(structured, payload=payload, model=model,
                                                           response_status=response_status)
                if issue:
                    return None, None, issue
            return None, None, "invalid_structured_output"

    if source_failure is not None:
        result, snapshot, issue = attempt(None, fixed=True)
    else:
        result, snapshot, issue = attempt(semantic)
        if issue:
            internal_status = "safety_rejected" if issue == "safety_rejected" else internal_status or issue
            if semantic is not None:
                result, snapshot, issue = attempt(None)
            if issue:
                internal_status = "safety_rejected" if issue == "safety_rejected" else internal_status or issue
                result, snapshot, issue = attempt(None, fixed=True)
    if issue:
        raise ReviewDisplayContractError("fixed review envelope could not be approved")
    if approval_state is not None:
        approval_state["snapshot"] = snapshot
    if history_state is not None and snapshot is not None and history_metadata_json is not None:
        history_state["approved"] = {"snapshot": snapshot, "metadata_json": history_metadata_json,
                                     "prepared_content": history_prepared_content}
    return copy.deepcopy(result)


def _empty_review_result(review_type: str, approval_state: dict | None, history_state: dict | None):
    if history_state is not None:
        history_state["approved"] = None
    if approval_state is not None:
        approval_state["snapshot"] = None
    source = compose_review_source(review_type=review_type, trades=(), objective=_objective_review_snapshot(()),
                                   status="empty", origin="none")
    candidate = compile_review_envelope(source)
    _filtered, rules = _filter_openai_review_safety(candidate["body"]["canonical_text"],
                                                   payload={"review_type": review_type}, model="none")
    if rules:
        raise ReviewDisplayContractError("empty review body failed safety")
    try:
        validate_legacy_body(candidate["body"])
    except LegacyCompatibilityContractError:
        return _legacy_compatibility_rejection(review_type)
    snapshot = seal_review_envelope(candidate)
    body = json.loads(snapshot.json_text)["body"]
    summary = admit_legacy_body(body).summary
    if approval_state is not None:
        approval_state["snapshot"] = snapshot
    return {"status": "empty", "source": "none", "review_type": review_type,
            "summary": summary, "display_snapshot": body}


def _source_memo_limit():
    return _env_int("ALPHAMATE_JOURNAL_MEMO_MAX_CHARS", 2000, 1, 5000)


def _admitted_chart(value):
    return value if type(value) in (CompactChartSource, UnavailableChartSource) else admit_chart_source(value)


def _admitted_contexts(values):
    if type(values) is tuple and all(type(item) in (AnalysisContextSource, AnalysisContextErrorSource) for item in values):
        return values
    if type(values) is not list:
        raise SourceAdmissionError("expected raw context list or admitted tuple")
    return tuple(admit_analysis_context_source(item, memo_max_chars=_source_memo_limit()) for item in values)


def _source_safety_issue(source, *, payload, model, response_status=None, history_state=None):
    fields = {"trades": [trade_payload(trade) for trade in source.trades],
              "charts": [chart_payload(chart) for chart in source.charts],
              "contexts": [context_payload(item) for item in source.analysis_contexts],
              "history_candidate": history_state.get("candidate") if history_state else None}
    try:
        leaves = _text_leaf_paths(fields, allow_scalars=True, max_nodes=_ENVELOPE_MAX_NODES)
    except (TypeError, ValueError, RecursionError):
        return "invalid_structured_output"
    for text in [*(field for _path, field in leaves), *(f"{trade.name} {trade.memo}" for trade in source.trades)]:
        _filtered, rules = _filter_openai_review_safety(text, payload=payload, model=model, response_status=response_status)
        if rules:
            return "safety_rejected"
    return None


def _admission_failure_status(value, review_type):
    # Classify safety for diagnostics only. No rejected value is projected or
    # passed to a provider, fallback producer, compiler or snapshot.
    try:
        leaves = _text_leaf_paths(value, allow_scalars=True, max_nodes=_ENVELOPE_MAX_NODES)
    except (TypeError, ValueError, RecursionError):
        return "invalid_structured_output"
    for _path, text in leaves:
        _filtered, rules = _filter_openai_review_safety(text, payload={"review_type": review_type}, model="none")
        if rules:
            return "safety_rejected"
    return "invalid_structured_output"


def build_basic_ai_review(trades: list[dict], target_trade_id=None, analysis_focus: str = "balanced", *,
                          history_state: dict | None = None, approval_state: dict | None = None) -> dict:
    admission_inputs = trades
    try:
        admitted_trades = admit_trade_sources(trades, memo_max_chars=_source_memo_limit())
        target = _target_trade(admitted_trades, target_trade_id)
        if target is None:
            return _empty_review_result("basic", approval_state, history_state)
        episode = _trade_episode(admitted_trades, target)
        prompt_episode = episode[-20:]
        chart_input = _compact_chart_snapshot(prompt_episode)
        admission_inputs = chart_input
        chart = _admitted_chart(chart_input)
        context_inputs = [] if type(chart) is CompactChartSource else _contexts_for_trades(prompt_episode)
        admission_inputs = context_inputs
        context_sources = _admitted_contexts(context_inputs)
        source = compose_review_source(review_type="basic", trades=episode,
                                       objective=_objective_review_snapshot(episode), charts=(chart,),
                                       analysis_contexts=context_sources)
    except (SourceAdmissionError, TypeError, KeyError, ValueError, OverflowError):
        return _finalize_ai_review("", source=None, review_type="basic", payload={"review_type": "basic"}, model="none",
                                   source_failure=_admission_failure_status(admission_inputs, "basic"),
                                   history_state=history_state, approval_state=approval_state)
    data_quality, missing_information = _review_data_quality(source)
    focus = _normalize_basic_review_focus(analysis_focus)
    evaluation_anchor = _basic_evaluation_anchor(source)
    chart_snapshot = chart_payload(chart)
    contexts = [context_payload(item) for item in context_sources]
    payload = {
        "review_type": "basic",
        "analysis_version": "basic-review-v2",
        "analysis_focus": {
            "key": focus,
            "priority": BASIC_REVIEW_FOCUS_LABELS[focus],
        },
        "trade_episode": [trade_payload(trade) for trade in prompt_episode],
        "daily_chart_contexts": contexts,
        "trade_chart_snapshot": chart_snapshot,
        "data_integrity": {
            "confidence": data_quality,
            "missing_information": missing_information,
            "rule": "정보가 없는 사실은 만들어내지 않고, 낮은 신뢰도에서는 기술적 판단을 제한한다.",
        },
        "evaluation_anchor": evaluation_anchor,
        "consistency_policy": {
            "stable_dimensions": ["매수 시점", "매도 시점", "위험 관리", "실현 결과"],
            "rule": "동일한 evaluation_anchor라면 평가 방향과 근거가 서로 모순되면 안 된다.",
            "focus_rule": "analysis_focus는 강조 근거만 바꾸며 잘함과 아쉬움의 판정을 뒤집지 않는다.",
        },
        "output_contract": {
            "format": "structured json",
            "response_format": structured_output_format("basic"),
            "sections": ["결과/판단 품질", "잘한 점", "핵심 개선점", "다음 매매 체크", "이번에 배울 지식"],
            "length": "짧고 실전적으로",
        },
    }
    model = _env_value("OPENAI_BASIC_REVIEW_MODEL") or _env_value("OPENAI_MODEL") or "gpt-5.6-luna"
    instructions = (
        AI_REVIEW_SAFETY_RULES
        + "<role>너는 한국 주식 매매 복기 코치다. 같은 종목의 여러 분할 체결은 하나의 매매 에피소드로 평가한다.</role>\n"
        "<evidence_rules>evaluation_anchor와 trade_chart_snapshot의 실제 봉, 매수·매도 마커, 평균 체결가, "
        "실현손익을 우선 근거로 사용한다. 메모가 없어도 가격과 차트로 평가하고, 기록을 남긴 사실 자체를 칭찬하지 않는다. "
        "서로 다른 숫자 근거를 2개 이상 포함하며 근거가 없으면 추측하지 않는다.</evidence_rules>\n"
        "<consistency_rules>동일한 evaluation_anchor에는 매수 시점, 매도 시점, 위험 관리의 평가 방향을 동일하게 유지한다. "
        "analysis_focus는 이번 답변에서 우선 설명할 관점일 뿐 잘함과 아쉬움의 판정을 뒤집는 근거가 아니다. "
        "표현을 새롭게 보이게 하려고 결론을 바꾸거나 모순되는 평가를 만들지 않는다.</consistency_rules>\n"
        "<quality_rules>잘한 점을 억지로 만들지 말고, 확인된 강점이 없으면 그렇게 쓴다. 아쉬운 점과 체크리스트는 이번 거래의 "
        "가격, 수익률, 체결 횟수, 5개 봉 또는 이동평균 근거에 직접 연결한다. 어느 거래에도 붙일 수 있는 상투적인 문구만 쓰지 않는다.</quality_rules>\n"
        "<output_contract>투자 추천이나 매수·매도 지시는 하지 않는다. JSON Schema에 맞는 JSON 객체만 반환한다. "
        "결과와 판단 품질을 분리하고, decision_quality, main_issue, next_action, good_points(최대 2개), "
        "main_improvement, next_trade_checks(최대 3개), lesson을 채운다.</output_contract>"
    )
    source_issue = _source_safety_issue(source, payload=payload, model=model, history_state=history_state)
    if source_issue:
        return _finalize_ai_review("", source=source, review_type="basic", payload=payload, model=model,
                                   source_failure=source_issue, history_state=history_state, approval_state=approval_state)
    request_failed = False
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError:
        ai_text = ""
        request_failed = True
    return _finalize_ai_review(
        ai_text, source=source, review_type="basic", payload=payload, model=model, request_failed=request_failed,
        history_state=history_state, approval_state=approval_state,
    )


def build_advanced_ai_review(
    trades: list[dict],
    target_trade_id=None,
    *,
    model_override: str = "",
    allow_fallback: bool = True,
    history_state: dict | None = None,
    approval_state: dict | None = None,
) -> dict:
    admission_inputs = trades
    try:
        admitted_trades = admit_trade_sources(trades, memo_max_chars=_source_memo_limit())
        target = _target_trade(admitted_trades, target_trade_id)
        if target is None:
            return _empty_review_result("advanced", approval_state, history_state)
        recent = _trade_episode(admitted_trades, target)
        prompt_recent = recent[-20:]
        by_ticker = {}
        for trade in prompt_recent:
            by_ticker.setdefault(trade.ticker or trade.name, []).append(trade)
        charts = []
        for ticker_trades in by_ticker.values():
            chart_input = _compact_chart_snapshot(tuple(ticker_trades))
            admission_inputs = chart_input
            charts.append(_admitted_chart(chart_input))
        chart_sources = tuple(charts)
        context_inputs = [] if any(type(chart) is CompactChartSource for chart in charts) else _contexts_for_trades(prompt_recent)
        admission_inputs = context_inputs
        context_sources = _admitted_contexts(context_inputs)
        source = compose_review_source(review_type="advanced", trades=recent,
                                       objective=_objective_review_snapshot(recent), charts=chart_sources,
                                       analysis_contexts=context_sources)
    except (SourceAdmissionError, TypeError, KeyError, ValueError, OverflowError):
        return _finalize_ai_review("", source=None, review_type="advanced", payload={"review_type": "advanced"}, model="none",
                                   source_failure=_admission_failure_status(admission_inputs, "advanced"),
                                   history_state=history_state, approval_state=approval_state)
    data_quality, missing_information = _review_data_quality(source)
    chart_snapshots = [chart_payload(chart) for chart in chart_sources]
    contexts = [context_payload(item) for item in context_sources]
    payload = {
        "review_type": "advanced",
        "target_trade": trade_payload(target),
        "recent_trades": [trade_payload(trade) for trade in prompt_recent],
        "chart_contexts": contexts,
        "trade_chart_snapshots": chart_snapshots,
        "data_integrity": {
            "confidence": data_quality,
            "missing_information": missing_information,
            "rule": "정보가 없는 사실은 만들어내지 않고, 낮은 신뢰도에서는 기술적 판단을 제한한다.",
        },
        "output_contract": {
            "format": "structured json",
            "response_format": structured_output_format("advanced"),
            "must_cover": ["결과와 판단 품질 분리", "진입 가설", "당시 위험 관리", "매수·매도 대응"],
            "sections": ["결과/판단 품질", "진입 판단", "위험 관리", "매도 판단", "상세 근거", "플레이북", "매매 지식", "다음 복기 질문"],
            "length": "핵심 근거 중심으로 간결하게",
        },
        "scope_policy": {
            "rule": "recent_trades에는 사용자가 선택한 한 매매 에피소드의 체결만 들어 있다.",
            "do_not_expand": "다른 종목이나 선택하지 않은 매매를 추측하거나 분석에 포함하지 않는다.",
        },
    }
    model = str(model_override or "").strip() or _env_value("OPENAI_ADVANCED_REVIEW_MODEL") or "gpt-5.6-luna"
    fallback_model = (
        _env_value("OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL")
        or _env_value("OPENAI_BASIC_REVIEW_MODEL")
        or "gpt-5.4-mini"
    )
    instructions = (
        AI_REVIEW_SAFETY_RULES
        + "<role>너는 한국 주식 매매 복기 코치다. 사용자가 선택한 한 매매 에피소드만 깊게 분석한다.</role>\n"
        "<scope>payload의 recent_trades와 trade_chart_snapshots만 분석한다. 선택하지 않은 종목, 다른 날짜의 매매, 존재하지 않는 "
        "최근 기록을 끌어오지 않는다. 체결 수가 여러 건이어도 같은 포지션의 분할 매수·매도라면 하나의 매매로 본다.</scope>\n"
        "<judgment_rules>수익 또는 손실이라는 결과와 당시 판단의 품질을 반드시 분리한다. 매도 뒤 가격이 올랐다는 이유만으로 조기 "
        "매도라고 단정하지 않고, 매도 시점까지 확인 가능했던 봉·거래량·이동평균선·사전 규칙만으로 평가한다. 최고가를 맞히지 못한 "
        "것은 잘못으로 평가하지 않는다. 진입은 당시 가설, 확인 신호, 실제 체결의 일치 여부 순서로 연결한다. 위험 관리는 사용자가 "
        "사전에 기준을 기록했는지와 실제 행동이 그 기준과 일치했는지만 평가하고, 새로운 가격·시간·비율·조건을 만들어 지시하지 않는다."
        "</judgment_rules>\n"
        "<evidence_rules>각 판단에는 종목명, 체결 가격, 수익률, 전후 봉, 거래량 또는 이동평균선 중 실제 숫자 근거를 붙인다. 문장마다 "
        "과거 사실과 해석을 자연스러운 한국어로 구분한다. [데이터 확인], [합리적 추론] 같은 내부 분류 표시는 출력하지 않는다. "
        "메모가 없어도 차트로 판단하되 매매 이유를 지어내지 않는다. 완결된 매매가 5개 미만이면 반복 습관이라고 단정하지 말고 이번 "
        "매매에서 보인 잠정 패턴이라고 쓴다.</evidence_rules>\n"
        "<terminology>일봉 이동평균선은 '5일 이동평균', '10일 이동평균', '20일 이동평균'처럼 자연어로 쓴다. 일봉 외 차트에서는 "
        "'1분봉 차트의 5개 봉 이동평균'처럼 실제 차트 주기와 봉 개수를 함께 적는다. 같은 답변에서 처음 언급할 때 차트 주기를 "
        "함께 적고, 이후에는 자연어 이동평균 표현을 간결하게 쓴다. '5분선'처럼 차트 주기와 이동평균 기간을 혼동할 수 있는 "
        "표현은 쓰지 않는다.</terminology>\n"
        "<output_contract>결과와 당시 판단의 품질을 반드시 분리한다. JSON Schema에 맞는 JSON 객체만 반환한다. "
        "entry_review, risk_review, exit_review, detailed_analysis, next_trade_playbook, lesson, reflection_questions를 채운다. "
        "같은 원인의 문제를 여러 항목에서 반복하지 않는다. 미래의 특정 가격·시각·날짜·조건에 따른 매수·매도·손절·청산 지시를 쓰지 않는다.</output_contract>"
    )
    source_issue = _source_safety_issue(source, payload=payload, model=model, history_state=history_state)
    if source_issue:
        return _finalize_ai_review("", source=source, review_type="advanced", payload=payload, model=model,
                                   source_failure=source_issue, history_state=history_state, approval_state=approval_state)
    request_failed = False
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError:
        request_failed = True
        if allow_fallback and fallback_model and fallback_model != model:
            try:
                ai_text = _call_openai_review(payload, model=fallback_model, instructions=instructions)
                model = fallback_model
                if ai_text:
                    request_failed = False
            except RuntimeError:
                ai_text = ""
        else:
            ai_text = ""
    return _finalize_ai_review(
        ai_text, source=source, review_type="advanced", payload=payload, model=model, request_failed=request_failed,
        history_state=history_state, approval_state=approval_state,
    )
