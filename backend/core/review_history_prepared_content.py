"""Finalizer-owned immutable content bound to its original review seal.

Access belongs to the later route/write boundary. Preparation never creates a
seal, reads a store, or repairs a missing projection. The existing envelope has
no model/metadata/full-semantic field: those bytes bind at finalizer capture and
must subsequently match exactly, together with the original snapshot identity.
"""

import hashlib
import json
import re

from backend.core import review_history_content_contract as content
from backend.core.review_envelope_contract import ApprovedReviewSnapshot, validate_envelope
from backend.core.review_history_write_contract import HistoryWriteContractError


_CAPTURE = object()
_OPTIONS = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":"), "allow_nan": False}


def _require(condition, path):
    if not condition:
        raise HistoryWriteContractError("invalid prepared-history identity: " + path)


def _encode(value):
    try:
        return json.dumps(value, **_OPTIONS).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        raise HistoryWriteContractError("invalid prepared-history serialization") from None


def _seal_bytes(snapshot):
    _require(type(snapshot) is ApprovedReviewSnapshot, "snapshot_type")
    try:
        sealed = object.__getattribute__(snapshot, "_json")
    except AttributeError:
        raise HistoryWriteContractError("invalid prepared-history snapshot") from None
    _require(type(sealed) is bytes, "snapshot_bytes")
    return sealed


def _validate_finalized_result(result):
    """The same Step 3 content shapes, before route-owned access exists.

Reuse the pure Step 3 field checks without supplying a fictitious access object
or changing its complete pre-write result validator. The factory requires an
already emitted projection and never derives one from the snapshot.
"""
    content._plain_tree(result)
    _require(type(result) is dict and type(result.get("review_type")) is str
             and result["review_type"] in ("basic", "advanced"), "review_type")
    review_type = result["review_type"]
    fields = {
        "status": content._enum("ready", "missing_key"), "source": content._enum("openai", "chart-rules"),
        "review_type": content._enum(review_type), "model": content._nullable(content._string(100)),
        "summary": content._string(16384), "display_snapshot": content._document,
        "structured_review": lambda v, p: content.validate_new_history_structured_review(v, review_type=review_type),
        "chart_display_snapshot": lambda v, p: content._object(v, {
            "charts": content._array(content._display_chart, 8),
            "chart_cards": content._array(content._display_card, 100),
        }, p),
        "chart_contexts": content._array(lambda v, p: None, 0),
        "chart_reviews": content._array(lambda v, p: None, 0),
    }
    fields["chart_snapshot" if review_type == "basic" else "chart_snapshots"] = (
        (lambda v, p: content._object(v, {}, p)) if review_type == "basic" else content._array(lambda v, p: None, 0))
    content._object(result, fields, "finalized_result")
    if result["status"] == "ready":
        _require(result["source"] == "openai" and type(result["model"]) is str
                 and re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", result["model"]), "ready_origin")
        try:
            body, _paths = content.compile_structured_review(result["structured_review"])
        except content.ReviewDisplayContractError:
            raise HistoryWriteContractError("invalid prepared-history ready body") from None
        _require(_encode(result["display_snapshot"]) == _encode(body), "ready_body")
    else:
        _require(result["source"] == "chart-rules" and result["model"] is None, "missing_key_origin")
    _require(all(block["type"] == "paragraph" for block in result["display_snapshot"]["blocks"]), "body_blocks")


def _match_seal(result, sealed):
    try:
        envelope = json.loads(sealed)
        validate_envelope(envelope)
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        raise HistoryWriteContractError("invalid prepared-history sealed envelope") from None
    expected = {key: envelope[key] for key in ("status", "source", "review_type")}
    expected["display_snapshot"] = envelope["body"]
    expected["chart_display_snapshot"] = {key: envelope[key] for key in ("charts", "chart_cards")}
    # This serializes already sealed runs only; it admits/repairs no legacy text.
    expected["summary"] = "".join(
        "".join("**" + run["text"] + "**" if run["type"] == "strong" else run["text"]
                for run in block["runs"]) + block["separator_after"] for block in envelope["body"]["blocks"])
    actual = {key: result[key] for key in expected}
    _require(_encode(actual) == _encode(expected), "sealed_projection")
    fields = ("trade_count", "realized_pnl", "realized_return_pct", "win_rate_pct", "weighted_buy_price")
    objective = result["structured_review"]["objective"]["result"]
    _require(_encode({key: objective[key] for key in fields})
             == _encode({key: envelope["objective"][key] for key in fields}), "sealed_objective")


def _digest(*buffers):
    digest = hashlib.sha256()
    for buffer in buffers:
        digest.update(len(buffer).to_bytes(8, "big"))
        digest.update(buffer)
    return digest.hexdigest()


class PreparedHistoryContent:
    """Independent immutable UTF-8 bytes; neither write approval nor storage."""

    __slots__ = ("_origin", "_snapshot", "_seal", "_metadata", "_result", "_structured", "_digest")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("prepared history content cannot be subclassed")

    def __init__(self, *args, **kwargs):
        raise TypeError("prepared history content requires finalizer capture")

    def __setattr__(self, name, value):
        raise AttributeError("prepared history content is immutable")

    def __delattr__(self, name):
        raise AttributeError("prepared history content is immutable")

    def __getstate__(self):
        raise TypeError("prepared history content serialization is unsupported")

    def __setstate__(self, state):
        raise TypeError("prepared history content restoration is unsupported")

    def __reduce__(self):
        raise TypeError("prepared history content serialization is unsupported")

    def __reduce_ex__(self, protocol):
        raise TypeError("prepared history content serialization is unsupported")

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def metadata_bytes(self):
        return self._metadata

    @property
    def result_bytes(self):
        return self._result

    @property
    def structured_review_bytes(self):
        return self._structured

    @property
    def metadata_json(self):
        return self._metadata.decode("utf-8")

    @property
    def result_json(self):
        return self._result.decode("utf-8")

    @property
    def digest(self):
        return self._digest

    def __repr__(self):
        return f"PreparedHistoryContent(digest={self.digest})"


def prepare_history_content(*, metadata, result, snapshot, finalizer_model, _authority=None):
    """Capture once at finalizer approval, using its existing snapshot/model.

The caller is the trusted finalizer, never the writer/restoration path. Model
has no envelope field; its exact finalizer value and all otherwise unsealed
metadata/semantic fields become part of this immutable approval association.
"""
    _require(_authority is _CAPTURE, "finalizer_capture_authority")
    sealed = _seal_bytes(snapshot)
    content.validate_new_history_metadata(metadata)
    _validate_finalized_result(result)
    _require(type(finalizer_model) is str or finalizer_model is None, "finalizer_model_type")
    _require(type(finalizer_model) is type(result["model"]) and finalizer_model == result["model"], "finalizer_model")
    _match_seal(result, sealed)
    metadata_bytes, result_bytes = _encode(metadata), _encode(result)
    frozen_metadata, frozen_result = json.loads(metadata_bytes), json.loads(result_bytes)
    # Admit the independently serialized values, not only the mutable originals.
    content.validate_new_history_metadata(frozen_metadata)
    _validate_finalized_result(frozen_result)
    _require(type(finalizer_model) is type(frozen_result["model"])
             and finalizer_model == frozen_result["model"], "serialized_model")
    _match_seal(frozen_result, sealed)
    _require(_encode(metadata) == metadata_bytes and _encode(result) == result_bytes
             and _seal_bytes(snapshot) == sealed, "capture_mutation")
    structured_bytes = _encode(frozen_result["structured_review"])
    prepared = object.__new__(PreparedHistoryContent)
    for name, value in (("_origin", _CAPTURE), ("_snapshot", snapshot),
                        ("_seal", memoryview(sealed).tobytes()), ("_metadata", metadata_bytes),
                        ("_result", result_bytes), ("_structured", structured_bytes),
                        ("_digest", _digest(sealed, metadata_bytes, result_bytes, structured_bytes))):
        object.__setattr__(prepared, name, value)
    return prepared


def validate_prepared_history_content(prepared, *, metadata, result, snapshot):
    """Match a complete pre-write result to its original frozen approval.

Access is checked by the unchanged Step 2/3 validator, and is not frozen into
content or treated as write authorization. No seal is created or substituted.
"""
    _require(type(prepared) is PreparedHistoryContent, "prepared_type")
    try:
        _require(prepared._origin is _CAPTURE, "prepared_origin")
        buffers = prepared._seal, prepared._metadata, prepared._result, prepared._structured
        _require(all(type(buffer) is bytes for buffer in buffers), "prepared_bytes")
        _require(type(prepared._digest) is str and prepared._digest == _digest(*buffers), "prepared_integrity")
        _require(snapshot is prepared._snapshot, "original_snapshot")
    except AttributeError:
        raise HistoryWriteContractError("invalid unprepared history content") from None
    _require(_seal_bytes(snapshot) == prepared._seal, "snapshot_mutation")
    content.validate_new_history_metadata(metadata)
    content.validate_new_history_result(result)
    finalized = {key: value for key, value in result.items() if key != "access"}
    _require(_encode(metadata) == prepared._metadata, "metadata_replacement")
    _require(_encode(finalized) == prepared._result, "result_replacement")
    _require(_encode(result["structured_review"]) == prepared._structured, "structured_replacement")
    _match_seal(finalized, prepared._seal)
