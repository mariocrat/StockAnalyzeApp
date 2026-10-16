"""Typed live capture/write authority and separate restart-safe read admission.

The activated finalizer supplies original live approvals. Its capability is
process-local application bookkeeping, never an authentication secret or HMAC.
"""
import json
from weakref import WeakKeyDictionary

from core.review_approval_bundle import ApprovedReviewBundle, validate_bundle
from core.review_display_v2_compiler import _dto_tree, capture_source
from core.review_display_v2_contract import ReviewDisplayV2Error
from core.review_envelope_contract import ApprovedReviewSnapshot, validate_envelope
from core.review_envelope_compiler import compile_review_envelope
from core.review_source_contract import ValidatedReviewSource
from core import review_history_prepared_content as prepared
from core.review_history_approved_write import ApprovedHistoryWrite, validate_approved_history_write
from core.review_history_write_contract import HistoryWriteContractError
from core.review_source_projection import structured_review_payload
from core.review_durable_storage_contract import (
    CONTEXT_KEYS, SNAPSHOT_KEYS, DurableStorageError, admit_envelope, canonical_json,
    encode_envelope, require, snapshot_digest, sql_json, validate_context, validate_read_safety,
)

_FINALIZER_CAPTURE = object()
_ISSUED = WeakKeyDictionary()


class _Immutable:
    __slots__ = ("_receipt", "__weakref__")

    def __init__(self, *args, **kwargs):
        raise TypeError("use the typed durable factory")

    def __setattr__(self, key, value):
        raise AttributeError("durable approval is immutable")

    def __delattr__(self, key):
        raise AttributeError("durable approval is immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("durable authority cannot be restored")

    def __getstate__(self):
        raise TypeError("durable authority cannot be restored")

    def __setstate__(self, state):
        raise TypeError("durable authority cannot be restored")


class LivePairedHistoryApproval(_Immutable):
    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        raise TypeError("live approval is final")


class ApprovedDurableHistoryEnvelope(_Immutable):
    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        raise TypeError("durable write approval is final")

    @property
    def bytes(self):
        validate_durable_write(self)
        return _receipt(self, ApprovedDurableHistoryEnvelope)[0]

    @property
    def json_text(self):
        return self.bytes.decode("utf-8")

    @property
    def sql_bind_values(self):
        """The original approved SQL values, with actual ID and complete wrapper."""
        validate_durable_write(self)
        buffer, _capture, write, row_id, _record, _digest = _receipt(self, ApprovedDurableHistoryEnvelope)
        values = list(write.bind_values)
        values[9] = buffer.decode("utf-8")  # Existing ai_review_json TEXT column.
        return (row_id, *values)


class DurableReadAdmission(_Immutable):
    """Admitted display bytes only; contains no capture/source/write authority."""
    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        raise TypeError("durable read admission is final")

    @property
    def payload(self):
        return json.loads(_receipt(self, DurableReadAdmission)[0])

    @property
    def projection(self):
        value = self.payload
        v1 = value["bundle"]["representations"]["v1"]
        return {"display_snapshot": v1["document"], "summary": v1["summary"],
                "chart_display_snapshot": value["chart_display_snapshot"]}

    @property
    def journal_chart_snapshot(self):
        return json.loads(_receipt(self, DurableReadAdmission)[1])["chart_snapshot"]

    @property
    def sql_snapshots(self):
        return json.loads(_receipt(self, DurableReadAdmission)[1])


def _receipt(value, expected_type):
    require(type(value) is expected_type, "INVALID_AUTHORITY")
    receipt = _ISSUED.get(value)
    require(receipt is not None, "INVALID_AUTHORITY")
    require(getattr(value, "_receipt", None) is receipt, "AUTHORITY_MUTATION")
    return receipt


def _issue(kind, receipt):
    value = object.__new__(kind)
    object.__setattr__(value, "_receipt", receipt)
    _ISSUED[value] = receipt
    return value


def _live_values(source, snapshot, prepared_content, bundle):
    require(type(source) is ValidatedReviewSource and type(bundle) is ApprovedReviewBundle and type(snapshot) is ApprovedReviewSnapshot
            and type(prepared_content) is prepared.PreparedHistoryContent, "INVALID_AUTHORITY")
    try:
        bundle_value = bundle.document
        validate_bundle(bundle_value, approval=bundle)
        require(bundle_value["kind"] == "paired_v1_v2", "INVALID_BUNDLE_KIND")
        # Original source object ownership is mandatory. Equal bytes alone cannot
        # associate a separately compiled source with this finalizer capture.
        require(bundle._owner_kind == "source" and bundle._owner is source, "SOURCE_OWNER_MISMATCH")
        source_bytes = capture_source(source)
        require(prepared_content._origin is prepared._CAPTURE
                and prepared_content.snapshot is snapshot, "ORIGINAL_SNAPSHOT_REQUIRED")
        seal = prepared._seal_bytes(snapshot)
        require(prepared_content._seal == seal, "SNAPSHOT_MUTATION")
        # Capture establishes the whole ORIGINAL source-to-seal relationship,
        # including auxiliaries; equal body/objective alone is insufficient.
        # This live-only pure check never belongs to the durable read path.
        require(sql_json(compile_review_envelope(source)) == seal, "SOURCE_SNAPSHOT_MISMATCH")
        buffers = seal, prepared_content.metadata_bytes, prepared_content.result_bytes, prepared_content.structured_review_bytes
        require(all(type(b) is bytes for b in buffers), "INVALID_AUTHORITY")
        require(prepared_content.digest == prepared._digest(*buffers), "PREPARED_MUTATION")
        meta, result = json.loads(buffers[1]), json.loads(buffers[2])
        prepared.content.validate_new_history_metadata(meta)
        prepared._validate_finalized_result(result)
        prepared._match_seal(result, seal)
        validate_envelope(json.loads(seal))
        require(sql_json(result["structured_review"]) == prepared_content.structured_review_bytes,
                "PREPARED_MUTATION")
        require(sql_json(structured_review_payload(source)) == prepared_content.structured_review_bytes,
                "SOURCE_CONTENT_MISMATCH")
        v1 = bundle_value["representations"]["v1"]
        require(canonical_json(v1["document"]) == canonical_json(result["display_snapshot"])
                and v1["summary"] == result["summary"], "BODY_CAPTURE_MISMATCH")
        require(result["review_type"] == bundle_value["review_type"] and result["status"] == "ready"
                and result["source"] == "openai", "CAPTURE_ORIGIN_MISMATCH")
        return (source_bytes, *buffers, bundle.json_text.encode("utf-8"))
    except (HistoryWriteContractError, ReviewDisplayV2Error) as error:
        raise DurableStorageError("INVALID_LIVE_CAPTURE") from error


def capture_live_paired_history(*, source, snapshot, prepared_content, bundle, _authority=None):
    """Finalizer-only association of ORIGINAL live objects before typed SQL write."""
    require(_authority is _FINALIZER_CAPTURE, "FINALIZER_AUTHORITY_REQUIRED")
    frozen = _live_values(source, snapshot, prepared_content, bundle)
    require(_live_values(source, snapshot, prepared_content, bundle) == frozen, "CAPTURE_MUTATION")
    return _issue(LivePairedHistoryApproval, (source, snapshot, prepared_content, bundle, frozen))


def _validated_write_components(capture, approved_write):
    source, snapshot, prepared_content, bundle, frozen = _receipt(capture, LivePairedHistoryApproval)
    require(_live_values(source, snapshot, prepared_content, bundle) == frozen, "CAPTURE_MUTATION")
    require(type(approved_write) is ApprovedHistoryWrite, "INVALID_WRITE_AUTHORITY")
    try:
        validate_approved_history_write(approved_write)
        record = json.loads(approved_write.record_bytes)
        require(approved_write.prepared_content_digest == prepared_content.digest, "PREPARED_MUTATION")
        prepared.validate_prepared_history_content(prepared_content,
            metadata={key: record[key] for key in json.loads(prepared_content.metadata_bytes)},
            result=record["ai_review"], snapshot=snapshot)
    except HistoryWriteContractError as error:
        raise DurableStorageError("INVALID_WRITE_AUTHORITY") from error
    return source, snapshot, prepared_content, bundle, record


def validate_paired_history_input(capture, approved_write):
    """Check original live/write association before a store opens any SQL DB."""
    _validated_write_components(capture, approved_write)


def _write_payload(capture, approved_write, row_id):
    source, snapshot, prepared_content, bundle, record = _validated_write_components(capture, approved_write)
    context = {key: row_id if key == "id" else record[key] for key in CONTEXT_KEYS}
    validate_context(context)
    result = json.loads(prepared_content.result_bytes)
    auxiliary = record["ai_review"]["chart_display_snapshot"]
    sealed = json.loads(snapshot.json_text)
    require(canonical_json(auxiliary) == canonical_json(result["chart_display_snapshot"])
            == canonical_json({key: sealed[key] for key in ("charts", "chart_cards")}), "CHART_CAPTURE_MISMATCH")
    objective = _dto_tree(source.objective)
    require(canonical_json(objective) == bundle._objective, "OBJECTIVE_CAPTURE_MISMATCH")
    payload = dict(row_context=context,
                   snapshot_digests={key: snapshot_digest(key, record[key]) for key in SNAPSHOT_KEYS},
                   objective=objective, bundle=bundle.document, chart_display_snapshot=auxiliary)
    sql = {key: sql_json(record[key]) for key in SNAPSHOT_KEYS}
    return payload, sql, approved_write.record_bytes, approved_write.digest


def issue_durable_history(*, capture, approved_write, row_id):
    """Own full bytes after typed write/capture checks; reserves no SQL row."""
    payload, sql, record, digest = _write_payload(capture, approved_write, row_id)
    buffer = encode_envelope(payload)
    admitted, _snapshots = admit_envelope(buffer, row_context=payload["row_context"], sql_snapshots=sql)
    require(canonical_json(admitted) == canonical_json(payload), "SERIALIZATION_MUTATION")
    current, _sql, current_record, current_digest = _write_payload(capture, approved_write, row_id)
    require(canonical_json(current) == canonical_json(payload) and current_record == record
            and current_digest == digest, "CAPTURE_MUTATION")
    return _issue(ApprovedDurableHistoryEnvelope, (buffer, capture, approved_write, row_id, record, digest))


def validate_durable_write(approval):
    buffer, capture, write, row_id, record, digest = _receipt(approval, ApprovedDurableHistoryEnvelope)
    payload, _sql, current_record, current_digest = _write_payload(capture, write, row_id)
    require(current_record == record and current_digest == digest and encode_envelope(payload) == buffer,
            "AUTHORITY_MUTATION")


def read_durable_history(buffer, *, row_context, sql_snapshots, unsafe_text=None):
    """Restart-equivalent display admission; never constructs a live/write token."""
    payload, snapshots = admit_envelope(buffer, row_context=row_context, sql_snapshots=sql_snapshots)
    validate_read_safety(payload, snapshots, unsafe_text=unsafe_text)
    return _issue(DurableReadAdmission, (canonical_json(payload), sql_json(snapshots)))
