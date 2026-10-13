"""Pure paired storage admission and public consistency checksums; no store."""
from datetime import datetime
import hashlib
import re

from backend.core import review_history_content_contract as content
from backend.core import review_source_contract as source
from backend.core.review_approval_bundle import validate_bundle_structure
from backend.core.review_display_v2_contract import ReviewDisplayV2Error
from backend.core.review_envelope_contract import (
    ReviewEnvelopeContractError, validate_chart_display_snapshot,
)
from backend.core.review_history_write_contract import HistoryWriteContractError, validate_new_history_access
from backend.core.review_history_adapter import _check_content
from backend.core.review_history_json_codec import (
    CODEC_VERSION, DurableStorageError, canonical_json, decode_json, decode_outer,
    decode_sql, outer_json, require, sql_json, validate_json_tree, check_byte_limit, MAX_PAYLOAD_BYTES,
)

STORAGE_VERSION = "review-history-paired.v1"
KIND = "paired_v1_v2"
CONTEXT_KEYS = ("id", "user_id", "review_type", "ticker", "name", "trade_date",
                "target_trade_id", "model", "source", "created_at")
SNAPSHOT_KEYS = ("trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "access_snapshot")
OUTER_KEYS = ("storage_schema_version", "kind", "codec_version", "payload", "payload_digest")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COUNTS = ("trade_count", "closed_count", "buy_fill_count", "sell_fill_count", "symbol_count")
_NUMBERS = ("realized_pnl", "realized_return_pct", "win_rate_pct", "weighted_buy_price",
            "weighted_sell_price", "total_fee", "total_tax", "open_quantity")


def exact(value, keys):
    require(type(value) is dict and value.keys() == set(keys), "INVALID_KEYS")


def checksum(buffer):
    require(type(buffer) is bytes, "INVALID_BYTES")
    return hashlib.sha256(buffer).hexdigest()


def _framed(*buffers):
    return b"".join(len(buffer).to_bytes(8, "big") + buffer for buffer in buffers)


def payload_digest(payload, *, storage_version=STORAGE_VERSION, kind=KIND, codec=CODEC_VERSION):
    require(type(payload) is bytes and all(type(v) is str for v in (storage_version, kind, codec)), "INVALID_TYPE")
    return checksum(b"StockBoda-review-history-paired-v1\x00" + _framed(
        storage_version.encode("utf-8"), kind.encode("utf-8"), codec.encode("utf-8"), payload))


def snapshot_digest(field, value):
    require(field in SNAPSHOT_KEYS, "INVALID_SNAPSHOT_FIELD")
    return checksum(b"StockBoda-review-history-snapshot-v1\x00" + _framed(
        CODEC_VERSION.encode("utf-8"), field.encode("utf-8"), sql_json(value)))


def validate_context(value):
    exact(value, CONTEXT_KEYS)
    validate_json_tree(value)
    try:
        content._id(value["id"], "id")
        content._string(120)(value["user_id"], "user_id")
        content._enum("basic", "advanced")(value["review_type"], "review_type")
        content._ticker(value["ticker"], "ticker")
        content._string(120)(value["name"], "name")
        content._trade_date(value["trade_date"], "trade_date")
        content._nullable(content._id)(value["target_trade_id"], "target_trade_id")
        content._string(100)(value["model"], "model")
        require(re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", value["model"]) is not None, "INVALID_ROW_CONTEXT")
        require(type(value["source"]) is str and value["source"] == "openai", "INVALID_ROW_CONTEXT")
        stamp = value["created_at"]
        require(type(stamp) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00", stamp)
                is not None, "INVALID_ROW_CONTEXT")
        datetime.fromisoformat(stamp)
    except (HistoryWriteContractError, ValueError) as error:
        if isinstance(error, DurableStorageError):
            raise
        raise DurableStorageError("INVALID_ROW_CONTEXT") from error


def _dto(value, name, keys):
    exact(value, ("dto", "fields"))
    require(type(value["dto"]) is str and value["dto"] == name, "INVALID_OBJECTIVE")
    exact(value["fields"], keys)
    return value["fields"]


def validate_objective(value):
    """Validate the pinned DTO tree without constructing or normalizing a DTO."""
    try:
        root = _dto(value, "ObjectiveSource", ("symbol", "period", "result"))
        symbol = _dto(root["symbol"], "ObjectiveSymbol", ("ticker", "name", "symbol_kind"))
        period = _dto(root["period"], "ObjectivePeriod", ("first_trade_date", "last_trade_date"))
        result = _dto(root["result"], "ObjectiveResult", (*_COUNTS, *_NUMBERS))
        kind = source._symbol(symbol["ticker"], symbol["name"], "objective.symbol")
        require(type(symbol["symbol_kind"]) is str and symbol["symbol_kind"] == kind, "INVALID_OBJECTIVE")
        first = source._date_time(period["first_trade_date"], "first", date_allowed=True)
        last = source._date_time(period["last_trade_date"], "last", date_allowed=True)
        require(first[:10] <= last[:10], "INVALID_OBJECTIVE")
        for key in _COUNTS:
            source._count(result[key], key)
        require(result["closed_count"] <= result["trade_count"] and
                result["buy_fill_count"] + result["sell_fill_count"] == result["trade_count"], "INVALID_OBJECTIVE")
        for key in _NUMBERS:
            source._number(result[key], key, nullable=key.startswith("weighted_"),
                           minimum=0 if key in ("total_fee", "total_tax", "open_quantity") else None)
        for key in ("weighted_buy_price", "weighted_sell_price"):
            require(result[key] is None or result[key] > 0, "INVALID_OBJECTIVE")
    except source.SourceAdmissionError as error:
        raise DurableStorageError("INVALID_OBJECTIVE") from error


def validate_auxiliary(value):
    try:
        validate_chart_display_snapshot(value)
        content._object(value, {
            "charts": content._array(content._display_chart, 8),
            "chart_cards": content._array(content._display_card, 100),
        }, "chart_display_snapshot")
    except (ReviewEnvelopeContractError, HistoryWriteContractError) as error:
        raise DurableStorageError("INVALID_CHART_AUXILIARY") from error


def metadata(context, snapshots):
    return {**{key: context[key] for key in ("ticker", "name", "trade_date", "target_trade_id")},
            **{key: snapshots[key] for key in SNAPSHOT_KEYS[:3]}}


def admit_sql_snapshots(context, sql_snapshots):
    exact(sql_snapshots, SNAPSHOT_KEYS)
    values = {field: decode_sql(sql_snapshots[field]) for field in SNAPSHOT_KEYS}
    try:
        content._plain_tree(values)
        content.validate_new_history_metadata(metadata(context, values))
        validate_new_history_access(values["access_snapshot"], review_type=context["review_type"], status="ready")
    except HistoryWriteContractError as error:
        raise DurableStorageError("INVALID_SQL_SNAPSHOT") from error
    return values


def validate_payload(payload):
    canonical_json(payload)  # Resource/plain-type checks before semantic callbacks.
    exact(payload, ("row_context", "snapshot_digests", "objective", "bundle", "chart_display_snapshot"))
    validate_context(payload["row_context"])
    exact(payload["snapshot_digests"], SNAPSHOT_KEYS)
    require(all(type(v) is str and _HEX.fullmatch(v) for v in payload["snapshot_digests"].values()), "INVALID_DIGEST")
    validate_objective(payload["objective"])
    bundle = payload["bundle"]
    try:
        validate_bundle_structure(bundle)
    except ReviewDisplayV2Error as error:
        raise DurableStorageError("BUNDLE_" + error.code) from error
    require(bundle["kind"] == KIND and bundle["status"] == "ready", "INVALID_BUNDLE_KIND")
    require(all(_HEX.fullmatch(bundle[key]) for key in ("source_identity", "objective_identity")), "INVALID_IDENTITY")
    require(bundle["review_type"] == payload["row_context"]["review_type"], "REVIEW_TYPE_MISMATCH")
    require(checksum(canonical_json(payload["objective"])) == bundle["objective_identity"], "OBJECTIVE_IDENTITY_MISMATCH")
    validate_auxiliary(payload["chart_display_snapshot"])


def encode_envelope(payload):
    """Public consistency helper; its bytes grant NO durable write authority."""
    validate_payload(payload)
    buffer = canonical_json(payload)
    return outer_json(dict(storage_schema_version=STORAGE_VERSION, kind=KIND,
                           codec_version=CODEC_VERSION, payload=buffer.decode("utf-8"),
                           payload_digest=payload_digest(buffer)))


def admit_envelope(buffer, *, row_context, sql_snapshots):
    """Full paired admission only. No legacy retry, compiler, I/O or repair."""
    outer = decode_outer(buffer)
    exact(outer, OUTER_KEYS)
    require(all(type(value) is str for value in outer.values()), "INVALID_TYPE")
    require(outer["storage_schema_version"] == STORAGE_VERSION, "INVALID_STORAGE_VERSION")
    require(outer["kind"] == KIND, "INVALID_STORAGE_KIND")
    require(outer["codec_version"] == CODEC_VERSION, "INVALID_CODEC_VERSION")
    require(_HEX.fullmatch(outer["payload_digest"]) is not None, "INVALID_DIGEST")
    inner = outer["payload"].encode("utf-8")
    check_byte_limit(inner, MAX_PAYLOAD_BYTES)
    require(payload_digest(inner) == outer["payload_digest"], "DIGEST_MISMATCH")
    payload = decode_json(inner, canonical=True)
    validate_payload(payload)
    validate_context(row_context)
    require(canonical_json(row_context) == canonical_json(payload["row_context"]), "ROW_CONTEXT_MISMATCH")
    snapshots = admit_sql_snapshots(row_context, sql_snapshots)
    require(all(snapshot_digest(key, snapshots[key]) == payload["snapshot_digests"][key]
                for key in SNAPSHOT_KEYS), "SNAPSHOT_DIGEST_MISMATCH")
    return payload, snapshots


def validate_read_safety(payload, snapshots, *, unsafe_text):
    """Reuse the current whole-record walk and caller's pure safety policy.

    No default-allow predicate or runtime-generation import. Callback bugs must
    propagate; only the existing walk's controlled contract rejection is mapped.
    """
    require(callable(unsafe_text), "INVALID_SAFETY_PREDICATE")

    class PredicateFault(Exception):
        pass

    def checked(text):
        try:
            decision = unsafe_text(text)
        except Exception as error:
            raise PredicateFault from error
        require(type(decision) is bool, "INVALID_SAFETY_PREDICATE")
        require(not decision, "UNSAFE_CONTENT")
        return False

    try:
        _check_content({"payload": payload, "sql_snapshots": snapshots}, checked)
    except PredicateFault as error:
        raise error.__cause__
    except ValueError as error:
        if isinstance(error, DurableStorageError):
            raise
        raise DurableStorageError("UNSAFE_CONTENT") from error
