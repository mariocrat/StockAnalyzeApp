"""Pure atomic content approval for v1-only/paired bodies; never grants access or writes."""
import json
import re
from weakref import WeakKeyDictionary

from backend.core.review_body_compiler import compile_review_body
from backend.core.review_display_contract import (
    ReviewDisplayContractError, compile_structured_review, validate_document as validate_v1,
)
from backend.core.review_legacy_compatibility import LegacyCompatibilityContractError, admit_legacy_body
from backend.core.review_envelope_contract import ApprovedReviewSnapshot, validate_envelope
from backend.core.review_display_v2_contract import require, exact_keys, ReviewDisplayV2Error, validate_document as validate_v2
from backend.core.review_display_v2_compiler import (
    COMPILER_VERSION, capture_source, compile_body, encode, identity, require_ready, text_leaf_paths, _dto_tree,
    _compile_projected,
)
from backend.core.review_source_projection import structured_review_payload, semantic_payload

BUNDLE_VERSION = "review-approval-bundle.v1"
V1_COMPILER_VERSION = "review-body.v1.0"
_CAPTURE = object()
_ISSUED = WeakKeyDictionary()
_LABEL = re.compile(r"[a-zA-Z0-9._/-]{1,128}\Z")


def _v1_summary(document):
    try:
        validate_v1(document)
        return admit_legacy_body(document).summary
    except (ReviewDisplayContractError, LegacyCompatibilityContractError) as error:
        raise ReviewDisplayV2Error("V1_DOCUMENT_INVALID") from error


def validate_bundle_structure(bundle):
    """Validate both sides even when only one representation would be displayed."""
    require(type(bundle) is dict, "INVALID_TYPE")
    kind = bundle.get("kind")
    require(type(kind) is str and kind in ("v1_only", "paired_v1_v2"), "INVALID_BUNDLE_KIND")
    paired = kind == "paired_v1_v2"
    keys = ("schema_version", "kind", "review_type", "status", "representations")
    exact_keys(bundle, (*keys, "source_identity", "objective_identity") if paired else keys, "$")
    require(bundle["schema_version"] == BUNDLE_VERSION, "INVALID_VERSION")
    require(type(bundle["review_type"]) is str and bundle["review_type"] in ("basic", "advanced"), "INVALID_REVIEW_TYPE")
    require(type(bundle["status"]) is str and bundle["status"] in
            (("ready",) if paired else ("ready", "missing_key", "error", "empty")), "INVALID_BUNDLE_STATUS")
    reps = bundle["representations"]
    require(type(reps) is dict, "INVALID_TYPE", "$.representations")
    require("v1" in reps, "V1_MISSING")
    if paired:
        require("v2" in reps, "V2_MISSING")
    exact_keys(reps, ("v1", "v2") if paired else ("v1",), "$.representations")
    if paired:
        for field in ("source_identity", "objective_identity"):
            require(type(bundle[field]) is str and _LABEL.fullmatch(bundle[field]) is not None,
                    "INVALID_IDENTITY", "$." + field)
    for version in (("v1", "v2") if paired else ("v1",)):
        rep = reps[version]
        keys = ("document", "summary") if version == "v1" else ("document",)
        exact_keys(rep, (*keys, "compiler_version", "source_identity", "objective_identity", "review_type")
                   if paired else keys, "$.representations." + version)
        if paired:
            require(rep["compiler_version"] == (V1_COMPILER_VERSION if version == "v1" else COMPILER_VERSION),
                    "COMPILER_VERSION_MISMATCH")
            require(rep["review_type"] == bundle["review_type"], "REVIEW_TYPE_MISMATCH")
            require(rep["source_identity"] == bundle["source_identity"], "SOURCE_IDENTITY_MISMATCH")
            require(rep["objective_identity"] == bundle["objective_identity"], "OBJECTIVE_IDENTITY_MISMATCH")
        if version == "v1":
            summary = _v1_summary(rep["document"])
            require(type(rep["summary"]) is str and rep["summary"] == summary, "A1_SUMMARY_MISMATCH")
        else:
            validate_v2(rep["document"])
            require(rep["document"]["review_type"] == bundle["review_type"], "REVIEW_TYPE_MISMATCH")


def _validate_candidate(candidate, expected):
    """Compare to already compiled trusted outputs; does not allocate approval.

    Internal expected data comes only from the compiler factory or sealed receipt.
    This function never reads raw semantics, repairs a side, or selects a version.
    """
    validate_bundle_structure(candidate)
    require(candidate["kind"] == expected["kind"], "BUNDLE_IDENTITY_MISMATCH")
    require(candidate["review_type"] == expected["review_type"], "REVIEW_TYPE_MISMATCH")
    require(candidate["status"] == expected["status"], "BUNDLE_IDENTITY_MISMATCH")
    if candidate["kind"] == "paired_v1_v2":
        require(candidate["source_identity"] == expected["source_identity"], "SOURCE_IDENTITY_MISMATCH")
        require(candidate["objective_identity"] == expected["objective_identity"], "OBJECTIVE_IDENTITY_MISMATCH")
    for version, rep in candidate["representations"].items():
        require(encode(rep["document"]) == encode(expected["representations"][version]["document"]),
                "COMPILER_OUTPUT_MISMATCH")
    require(encode(candidate) == encode(expected), "BUNDLE_IDENTITY_MISMATCH")


def _digest(bundle, source, objective):
    return identity(b"review-approval-bundle.v1\x00" + b"".join(len(b).to_bytes(8, "big") + b
                                                             for b in (bundle, source, objective)))


class ApprovedReviewBundle:
    """Factory-only immutable bytes associated with their original admitted owner."""
    __slots__ = ("_origin", "_json", "_source", "_objective", "_digest", "_owner", "_owner_kind", "__weakref__")

    def __init__(self, *args, **kwargs):
        raise TypeError("use compile_approval_bundle or approve_v1_only")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("approved bundles cannot be subclassed")

    def __setattr__(self, name, value):
        raise AttributeError("approved bundle is immutable")

    def __delattr__(self, name):
        raise AttributeError("approved bundle is immutable")

    def __getstate__(self):
        raise TypeError("approved bundle serialization is unsupported")

    def __setstate__(self, state):
        raise TypeError("approved bundle restoration is unsupported")

    def __reduce__(self):
        raise TypeError("approved bundle serialization is unsupported")

    def __reduce_ex__(self, protocol):
        raise TypeError("approved bundle serialization is unsupported")

    @property
    def json_text(self):
        return _approved_bytes(self).decode("utf-8")

    @property
    def document(self):
        return json.loads(self.json_text)

    @property
    def digest(self):
        _approved_bytes(self)
        return self._digest


def _approved_bytes(approval):
    require(type(approval) is ApprovedReviewBundle, "INVALID_APPROVAL")
    receipt = _ISSUED.get(approval)
    require(receipt is not None, "INVALID_APPROVAL")
    try:
        require(approval._origin is _CAPTURE, "INVALID_APPROVAL")
        buffers = approval._json, approval._source, approval._objective
        require(all(type(v) is bytes for v in buffers), "INVALID_APPROVAL")
        require(buffers == receipt[:3] and approval._digest == receipt[3]
                and approval._owner is receipt[4] and approval._owner_kind == receipt[5], "APPROVAL_MUTATION")
        require(approval._digest == _digest(*buffers), "APPROVAL_MUTATION")
        if approval._owner_kind == "source":
            require(encode(_dto_tree(approval._owner)) == approval._source, "SOURCE_MUTATION")
        else:
            require(approval._owner_kind == "v1_snapshot" and type(approval._owner) is ApprovedReviewSnapshot,
                    "INVALID_APPROVAL")
            require(object.__getattribute__(approval._owner, "_json") == approval._source, "SOURCE_MUTATION")
        validate_bundle_structure(json.loads(approval._json))
    except AttributeError as error:
        raise ReviewDisplayV2Error("INVALID_APPROVAL") from error
    return approval._json


def _allocate(candidate, *, owner, owner_kind, source, objective):
    # Validate serialized bytes too, then publish once. No partially initialized
    # approval leaves this function, and source aliases must still match.
    validate_bundle_structure(candidate)
    frozen = encode(candidate)
    _validate_candidate(json.loads(frozen), candidate)
    require(encode(candidate) == frozen, "APPROVAL_MUTATION")
    current = encode(_dto_tree(owner)) if owner_kind == "source" else object.__getattribute__(owner, "_json")
    require(current == source, "SOURCE_MUTATION")
    result = object.__new__(ApprovedReviewBundle)
    for key, value in dict(_origin=_CAPTURE, _json=frozen, _source=source, _objective=objective,
                           _digest=_digest(frozen, source, objective), _owner=owner, _owner_kind=owner_kind).items():
        object.__setattr__(result, key, value)
    # Instance-local fields alone are not authority: object.__setattr__ plus a
    # recomputed hash must not turn changed content into an issued approval.
    # Weak ownership is factory bookkeeping, never the request/idempotency cache.
    _ISSUED[result] = (frozen, source, objective, result._digest, owner, owner_kind)
    return result


def compile_approval_bundle(source, *, kind="paired_v1_v2"):
    frozen = capture_source(source)
    require(kind in ("v1_only", "paired_v1_v2"), "INVALID_BUNDLE_KIND")
    if kind == "paired_v1_v2":
        require_ready(source)
    v1 = compile_review_body(source)
    summary = _v1_summary(v1)
    objective = encode(_dto_tree(source.objective))
    candidate = dict(schema_version=BUNDLE_VERSION, kind=kind, review_type=source.review_type,
                     status=source.status, representations={"v1": dict(document=v1, summary=summary)})
    if kind == "paired_v1_v2":
        projected = structured_review_payload(source)
        expected_v1, coverage = compile_structured_review(projected)
        model_paths = set(text_leaf_paths(semantic_payload(source.semantic)))
        common = {"decision_quality", "main_issue", "next_action"}
        expected_paths = {("summary" if path[0] in common else source.review_type, *path) for path in model_paths}
        require(coverage == expected_paths, "SEMANTIC_COVERAGE_MISMATCH")
        require(encode(v1) == encode(expected_v1), "COMPILER_OUTPUT_MISMATCH")
        v2 = compile_body(source)
        validate_v2(v2)
        expected_v2, _coverage = _compile_projected(projected)
        require(encode(v2) == encode(expected_v2), "COMPILER_OUTPUT_MISMATCH")
        candidate["source_identity"] = identity(frozen)
        candidate["objective_identity"] = identity(objective)
        for version, document in (("v1", v1), ("v2", v2)):
            candidate["representations"][version] = dict(
                compiler_version=V1_COMPILER_VERSION if version == "v1" else COMPILER_VERSION,
                source_identity=candidate["source_identity"], objective_identity=candidate["objective_identity"],
                review_type=source.review_type, document=document,
                **({"summary": summary} if version == "v1" else {}))
    require(capture_source(source) == frozen, "SOURCE_MUTATION")
    return _allocate(candidate, owner=source, owner_kind="source", source=frozen, objective=objective)


def approve_v1_only(snapshot):
    """Wrap an existing admitted v1 seal without a source reconstruction or upgrade."""
    if type(snapshot) is not ApprovedReviewSnapshot:
        raise TypeError("expected ApprovedReviewSnapshot")
    try:
        frozen = object.__getattribute__(snapshot, "_json")
    except AttributeError as error:
        raise ReviewDisplayV2Error("INVALID_APPROVAL") from error
    require(type(frozen) is bytes, "INVALID_APPROVAL")
    envelope = json.loads(frozen)
    validate_envelope(envelope)
    candidate = dict(schema_version=BUNDLE_VERSION, kind="v1_only", review_type=envelope["review_type"],
                     status=envelope["status"], representations={"v1": dict(document=envelope["body"],
                     summary=_v1_summary(envelope["body"]))})
    return _allocate(candidate, owner=snapshot, owner_kind="v1_snapshot", source=frozen,
                     objective=encode(envelope["objective"]))


def validate_bundle(candidate, *, approval):
    """Full comparison to original immutable approval, without compilation/read repair."""
    expected = json.loads(_approved_bytes(approval))
    _validate_candidate(candidate, expected)
