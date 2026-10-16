"""Pure admission of a complete new history row into immutable SQL-ready values.

No caller, clock, store, writer or legacy adapter is consulted. Authentication
and storage consent belong to the eventual caller. Every row value is required;
only the already retained finalizer content and original seal can authorize it.
"""

from datetime import datetime
import hashlib
import json
import re

from core import review_history_content_contract as content
from core.review_history_prepared_content import validate_prepared_history_content
from core.review_history_write_contract import HistoryWriteContractError, validate_new_history_access


SQL_BIND_COLUMNS = (
    "user_id", "review_type", "ticker", "name", "trade_date", "target_trade_id",
    "trade_snapshot_json", "recent_trades_snapshot_json", "chart_snapshot_json",
    "ai_review_json", "access_snapshot_json", "model", "source", "created_at",
)
JSON_SNAPSHOT_FIELDS = (
    "trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot",
)
_METADATA_FIELDS = (
    "ticker", "name", "trade_date", "target_trade_id", "trade_snapshot",
    "recent_trades_snapshot", "chart_snapshot",
)
_ISSUER = object()
_OPTIONS = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":"), "allow_nan": False}
_CREATED_AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00")


def _require(condition, path):
    if not condition:
        raise HistoryWriteContractError("invalid approved-history write: " + path)


def _encode(value):
    try:
        text = json.dumps(value, **_OPTIONS)
        _require(type(text) is str, "serialization_type")
        return text.encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        raise HistoryWriteContractError("invalid approved-history serialization") from None


def _decode(buffer):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    _require(type(buffer) is bytes, "serialized_bytes")
    try:
        value = json.loads(buffer.decode("utf-8"), object_pairs_hook=unique_object)
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        raise HistoryWriteContractError("invalid approved-history serialized JSON") from None
    _require(_encode(value) == buffer, "canonical_serialization")
    return value


def _tree_identity(value):
    """Independent immutable comparison, including exact classes and float bits."""
    content._plain_tree(value)

    def freeze(node):
        if type(node) is dict:
            return (dict, tuple((key, freeze(node[key])) for key in sorted(node)))
        if type(node) is list:
            return (list, tuple(freeze(child) for child in node))
        if type(node) is float:
            return (float, node.hex())
        return (type(node), node)

    return freeze(value)


def _created_at(value, path):
    _require(type(value) is str and _CREATED_AT.fullmatch(value) is not None, path)
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise HistoryWriteContractError("invalid approved-history write: " + path) from None


def _metadata(record):
    return {key: record[key] for key in _METADATA_FIELDS}


def _validate_record(record):
    content._plain_tree(record)
    fields = {
        "user_id": content._string(120), "review_type": content._enum("basic", "advanced"),
        "model": content._string(100, nonempty=False), "source": content._enum("openai", "chart-rules"),
        "created_at": _created_at,
        **dict.fromkeys(_METADATA_FIELDS, lambda v, p: None),
        "ai_review": lambda v, p: _require(type(v) is dict, p),
        "access_snapshot": lambda v, p: _require(type(v) is dict, p),
    }
    content._object(record, fields, "record")
    content.validate_new_history_metadata(_metadata(record))
    review = record["ai_review"]
    content.validate_new_history_result(review)
    validate_new_history_access(record["access_snapshot"], review_type=record["review_type"], status=review["status"])
    _require(record["review_type"] == review["review_type"] and record["source"] == review["source"], "row_origin")
    # Both are explicit required values: never convert result None to row "".
    _require(record["model"] == review["model"] if review["status"] == "ready"
             else record["model"] == "" and review["model"] is None, "row_model")
    _require(_tree_identity(record["access_snapshot"]) == _tree_identity(review["access"]), "access_identity")


def _validate_candidate(record, prepared_content, snapshot):
    _validate_record(record)
    validate_prepared_history_content(prepared_content, metadata=_metadata(record),
                                      result=record["ai_review"], snapshot=snapshot)


def _prepare_bind_values(record, snapshots):
    json_values = {field + "_json": buffer.decode("utf-8")
                   for field, buffer in zip(JSON_SNAPSHOT_FIELDS, snapshots)}
    return tuple(json_values[column] if column in json_values else record[column]
                 for column in SQL_BIND_COLUMNS)


def _validate_serialized_write(record_bytes, snapshots, bind_values):
    """Read back the actual JSON/bind values; reconstruct only for verification."""
    _require(type(snapshots) is tuple and len(snapshots) == len(JSON_SNAPSHOT_FIELDS)
             and all(type(buffer) is bytes for buffer in snapshots), "snapshot_bytes")
    _require(type(bind_values) is tuple and len(bind_values) == len(SQL_BIND_COLUMNS), "bind_tuple")
    record = _decode(record_bytes)
    _validate_record(record)
    rebound = {}
    for column, value in zip(SQL_BIND_COLUMNS, bind_values):
        if column == "target_trade_id":
            _require(value is None or type(value) is int and 1 <= value <= 2**53 - 1, "bind_target")
        else:
            _require(type(value) is str, "bind_string")
        if column.endswith("_json"):
            field = column[:-5]
            try:
                buffer = value.encode("utf-8")
            except UnicodeError:
                raise HistoryWriteContractError("invalid approved-history bind encoding") from None
            _require(buffer == snapshots[JSON_SNAPSHOT_FIELDS.index(field)], "bind_snapshot_bytes")
            rebound[field] = _decode(buffer)
            _require(buffer == _encode(record[field]), "snapshot_record_identity")
        else:
            rebound[column] = value
    _validate_record(rebound)
    _require(_tree_identity(rebound) == _tree_identity(record)
             and _encode(rebound) == record_bytes, "bind_record_identity")
    return rebound


def _digest(record_bytes, snapshots, bind_values, content_digest):
    digest = hashlib.sha256()
    for buffer in (record_bytes, *snapshots, _encode(list(bind_values)), content_digest.encode("ascii")):
        digest.update(len(buffer).to_bytes(8, "big"))
        digest.update(buffer)
    return digest.hexdigest()


class ApprovedHistoryWrite:
    """Admission-issued bytes and fourteen immutable SQL parameters; no I/O."""

    __slots__ = ("_origin", "_record", "_snapshots", "_bind_values", "_content_digest", "_digest")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("approved history write cannot be subclassed")

    def __init__(self, *args, **kwargs):
        raise TypeError("approved history write requires complete admission")

    def __setattr__(self, name, value):
        raise AttributeError("approved history write is immutable")

    def __delattr__(self, name):
        raise AttributeError("approved history write is immutable")

    def __getstate__(self):
        raise TypeError("approved history write serialization is unsupported")

    def __setstate__(self, state):
        raise TypeError("approved history write restoration is unsupported")

    def __reduce__(self):
        raise TypeError("approved history write serialization is unsupported")

    def __reduce_ex__(self, protocol):
        raise TypeError("approved history write serialization is unsupported")

    @property
    def record_bytes(self):
        return self._record

    @property
    def record_json(self):
        return self._record.decode("utf-8")

    @property
    def json_snapshot_bytes(self):
        return self._snapshots

    @property
    def bind_values(self):
        return self._bind_values

    @property
    def prepared_content_digest(self):
        return self._content_digest

    @property
    def digest(self):
        return self._digest

    def __repr__(self):
        return f"ApprovedHistoryWrite(digest={self.digest})"


def approve_history_write(*, record, prepared_content, snapshot):
    """Issue only after strict source, original-seal, serialization and bind checks."""
    _validate_candidate(record, prepared_content, snapshot)
    original = _tree_identity(record)
    record_bytes = _encode(record)
    frozen = _decode(record_bytes)
    _require(_tree_identity(frozen) == original, "serialized_record_identity")
    _validate_candidate(frozen, prepared_content, snapshot)
    snapshots = tuple(_encode(frozen[field]) for field in JSON_SNAPSHOT_FIELDS)
    bind_values = _prepare_bind_values(frozen, snapshots)
    rebound = _validate_serialized_write(record_bytes, snapshots, bind_values)
    _validate_candidate(rebound, prepared_content, snapshot)
    content_digest = prepared_content.digest
    digest = _digest(record_bytes, snapshots, bind_values, content_digest)
    _validate_candidate(record, prepared_content, snapshot)
    _require(_tree_identity(record) == original and _encode(record) == record_bytes
             and _tree_identity(record) == original, "admission_mutation")
    approved = object.__new__(ApprovedHistoryWrite)
    for name, value in (("_origin", _ISSUER), ("_record", record_bytes), ("_snapshots", snapshots),
                        ("_bind_values", bind_values), ("_content_digest", content_digest), ("_digest", digest)):
        object.__setattr__(approved, name, value)
    return approved


def validate_approved_history_write(approved):
    """Pure integrity check of an issued object; never recapture or reapprove it."""
    _require(type(approved) is ApprovedHistoryWrite, "approved_type")
    try:
        _require(approved._origin is _ISSUER, "approved_origin")
        _require(type(approved._content_digest) is str
                 and re.fullmatch(r"[0-9a-f]{64}", approved._content_digest), "content_digest")
        _validate_serialized_write(approved._record, approved._snapshots, approved._bind_values)
        _require(type(approved._digest) is str
                 and approved._digest == _digest(approved._record, approved._snapshots,
                                                approved._bind_values, approved._content_digest), "approved_integrity")
    except AttributeError:
        raise HistoryWriteContractError("invalid unapproved history write") from None
