"""Process-local whole execution approval; no persistence or replay ledger."""
import json
import math
from datetime import datetime, timezone
from weakref import WeakKeyDictionary

from backend.core.review_approval_bundle import ApprovedReviewBundle, approve_v1_only, validate_bundle
from backend.core.review_envelope_contract import (
    ApprovedReviewSnapshot, validate_envelope, approved_chart_display_snapshot,
)
from backend.core.review_envelope_compiler import compile_review_envelope
from backend.core.review_display_capability import V1_CAPABILITY, require_display_capability, select_admitted_body

_ISSUED = WeakKeyDictionary()


def _require(condition):
    if not condition:
        raise ValueError("invalid approved cached execution")


def _bytes(value):
    """Own exact plain JSON values, including numeric types, without a durable codec."""
    active = set()

    def visit(node):
        kind = type(node)
        _require(kind in (dict, list, str, bool, int, float, type(None)))
        if kind is str:
            _require(not any(0xD800 <= ord(char) <= 0xDFFF for char in node))
        elif kind is float:
            _require(math.isfinite(node))
        elif kind in (dict, list):
            _require(id(node) not in active)
            active.add(id(node))
            if kind is dict:
                for key, child in node.items():
                    _require(type(key) is str)
                    visit(key)
                    visit(child)
            else:
                for child in node:
                    visit(child)
            active.remove(id(node))

    try:
        visit(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, UnicodeError, OverflowError, RecursionError) as error:
        raise ValueError("invalid approved cached execution") from error


class ApprovedCachedExecution:
    """Factory receipt for one key/body/time plus complete response/access/history."""
    __slots__ = ("_receipt", "__weakref__")

    def __init__(self, *args, **kwargs):
        raise TypeError("use approve_cached_execution")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("cached execution cannot be subclassed")

    def __setattr__(self, name, value):
        raise AttributeError("cached execution is immutable")

    def __delattr__(self, name):
        raise AttributeError("cached execution is immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("cached execution is process-local")

    def __deepcopy__(self, memo):
        # Like the original snapshot, an immutable receipt is shared, not rebuilt.
        _receipt(self)
        return self

    @property
    def bundle(self):
        return _receipt(self)[5]


def _receipt(approval):
    _require(type(approval) is ApprovedCachedExecution)
    receipt = _ISSUED.get(approval)
    _require(receipt is not None and getattr(approval, "_receipt", None) is receipt)
    return receipt


def _check_content(result, snapshot, bundle):
    if snapshot is None:
        # Safety/invalid-output terminals have no body; never invent a bundle.
        _require(bundle is None and result.get("status") == "error" and result.get("source") == "none"
                 and result.get("summary") == "" and result.get("internal_status") in
                 {"safety_rejected", "invalid_structured_output"}
                 and not ({"display_snapshot", "structured_review", "chart_display_snapshot"} & result.keys()))
        return
    _require(type(snapshot) is ApprovedReviewSnapshot and type(bundle) is ApprovedReviewBundle)
    envelope = json.loads(snapshot.json_text)
    validate_envelope(envelope)
    document = bundle.document
    validate_bundle(document, approval=bundle)
    v1 = document["representations"]["v1"]
    _require(_bytes(v1["document"]) == _bytes(envelope["body"])
             and _bytes(result.get("display_snapshot")) == _bytes(v1["document"])
             and result.get("summary") == v1["summary"]
             and all(result.get(key) == envelope[key] for key in ("status", "source", "review_type"))
             and document["status"] == envelope["status"] and document["review_type"] == envelope["review_type"]
             and _bytes(result.get("chart_display_snapshot")) == _bytes(approved_chart_display_snapshot(snapshot)))


def approve_cached_execution(*, cache_key, fingerprint, expires_at, result, snapshot, bundle=None):
    """Capture already approved v1 results, or an explicitly supplied live paired bundle.

    Production callers supply no paired bundle. The optional live bundle is a
    storage boundary, never a flag or raw-dict route to paired generation.
    """
    _require(type(result) is dict)
    _require(type(cache_key) is str and bool(cache_key) and type(fingerprint) is str
             and len(fingerprint) == 64 and all(char in "0123456789abcdef" for char in fingerprint)
             and type(expires_at) is datetime and expires_at.tzinfo is timezone.utc)
    if "review_history_id" in result:
        # Preserve the existing v1 SQL identity domain; paired SQL owns its own bound.
        _require(type(result["review_history_id"]) is int and result["review_history_id"] >= 1)
    if bundle is None and snapshot is not None:
        bundle = approve_v1_only(snapshot)
    _check_content(result, snapshot, bundle)
    if bundle is not None:
        if bundle.document["kind"] == "v1_only":
            _require(bundle._owner_kind == "v1_snapshot" and bundle._owner is snapshot)
        else:
            # Establish original source-to-snapshot association ONCE on publication.
            # Cache admission below only checks frozen values and receipts.
            _require(bundle._owner_kind == "source"
                     and _bytes(compile_review_envelope(bundle._owner)) == snapshot._json)
    receipt = (cache_key, fingerprint, expires_at, snapshot,
               None if snapshot is None else snapshot._json, bundle,
               None if bundle is None else bundle.json_text, _bytes(result))
    approval = object.__new__(ApprovedCachedExecution)
    object.__setattr__(approval, "_receipt", receipt)
    _ISSUED[approval] = receipt
    validate_cached_execution(approval, cache_key=cache_key, fingerprint=fingerprint,
                              expires_at=expires_at, result=result, snapshot=snapshot)
    return approval


def validate_cached_execution(approval, *, cache_key, fingerprint, expires_at, result, snapshot,
                              display_capability=V1_CAPABILITY):
    """Validate the whole original execution before selecting its owned body."""
    require_display_capability(display_capability)
    receipt = _receipt(approval)
    _require(type(cache_key) is str and cache_key == receipt[0]
             and type(fingerprint) is str and fingerprint == receipt[1]
             and type(expires_at) is type(receipt[2]) and expires_at == receipt[2]
             and snapshot is receipt[3] and _bytes(result) == receipt[7])
    bundle = receipt[5]
    if snapshot is not None:
        _require(type(snapshot) is ApprovedReviewSnapshot and snapshot._json == receipt[4])
        _require(type(bundle) is ApprovedReviewBundle and bundle.json_text == receipt[6])
    _check_content(result, snapshot, bundle)
    projection = json.loads(receipt[7])
    if bundle is not None:
        document = bundle.document
        projection["display_snapshot"] = select_admitted_body(document, capability=display_capability)
        projection["summary"] = document["representations"]["v1"]["summary"]
    return projection
