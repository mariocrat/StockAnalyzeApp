"""Paired SQL read carriers and admitted v1 history projection; no DB or generation."""
import json
from dataclasses import dataclass

from core.review_durable_storage_approval import DurableReadAdmission, read_durable_history
from core.review_durable_storage_contract import CONTEXT_KEYS, SNAPSHOT_KEYS, validate_read_safety
from core.review_history_json_codec import DurableStorageError, MAX_OUTER_BYTES, require, sql_json
from core.review_display_capability import V1_CAPABILITY, select_admitted_body

RESERVED_KEYS = frozenset(("storage_schema_version", "kind", "codec_version", "payload", "payload_digest",
                          "representations", "source_identity", "objective_identity"))


def paired_marker(value):
    return type(value) is dict and (bool(value.keys() & RESERVED_KEYS)
        or value.get("schema_version") == "review-approval-bundle.v1")


def paired_marker_in_text(text):
    """Scan only root member names, before allocating/decoding a paired tree.

    This is dispatch, not JSON admission: the bounded strict codec still validates
    every paired byte. Nested keys and quoted text cannot select paired dispatch.
    Legacy values keep their existing size/admission contract.
    """
    if type(text) is not str:
        return True
    depth, index = 0, 0
    while index < len(text):
        char = text[index]
        if char == '"':
            start = index
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == '"':
                    break
                else:
                    index += 1
            end = index + 1
            tail = end
            while tail < len(text) and text[tail] in " \r\n\t":
                tail += 1
            if depth == 1 and tail < len(text) and text[tail] == ":":
                # Reserved names are ASCII and at most 22 characters; even
                # escaped spellings need at most six bytes per character.
                if end - start > 2 + 6 * max(map(len, RESERVED_KEYS | {"schema_version"})):
                    index = end
                    continue
                try:
                    key = json.loads(text[start:end])
                except ValueError:
                    return True
                if key in RESERVED_KEYS:
                    return True
                if key == "schema_version":
                    value_start = tail + 1
                    while value_start < len(text) and text[value_start] in " \r\n\t":
                        value_start += 1
                    if text.startswith('"review-approval-bundle.v1"', value_start):
                        return True
            index = end
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        index += 1
    return False


@dataclass(frozen=True, slots=True)
class StoredPairedHistoryRow:
    """Actual SQL scalars/raw TEXT, retained internally until whole admission."""
    context_values: tuple
    snapshot_values: tuple
    raw_review: str

    @classmethod
    def from_row(cls, row):
        return cls(tuple(row[key] for key in CONTEXT_KEYS),
                   tuple(row[key + "_json"] for key in SNAPSHOT_KEYS), row["ai_review_json"])

    @property
    def context(self):
        return dict(zip(CONTEXT_KEYS, self.context_values))

    def __getitem__(self, key):
        # Identity access is useful to storage callers; content is never a dict.
        if key not in {"id", "review_type"}:
            raise KeyError(key)
        return self.context[key]


def admit_stored_paired_history(row, *, unsafe_text):
    require(type(row) is StoredPairedHistoryRow, "INVALID_STORED_ROW")
    require(type(row.raw_review) is str, "INVALID_BYTES")
    require(len(row.raw_review) <= MAX_OUTER_BYTES, "BYTE_LIMIT")
    try:
        raw = row.raw_review.encode("utf-8")
    except (AttributeError, UnicodeError) as error:
        raise DurableStorageError("INVALID_BYTES") from error
    return read_durable_history(raw, row_context=row.context,
        sql_snapshots=dict(zip(SNAPSHOT_KEYS, row.snapshot_values)), unsafe_text=unsafe_text)


def paired_history_projection(admission, *, unsafe_text, display_capability=V1_CAPABILITY):
    """Preserve admitted body/B and original SQL A/trades/access without compilers."""
    require(type(admission) is DurableReadAdmission, "INVALID_READ_AUTHORITY")
    from core.review_history_adapter import _restorable
    from core.review_display_contract import compile_literal_text

    context, snapshots = admission.payload["row_context"], admission.sql_snapshots
    record = {key: value for key, value in context.items() if key != "user_id"}
    record.update(snapshots)
    record["ai_review"] = dict(admission.projection, status="ready", source=context["source"],
        review_type=context["review_type"], model=context["model"], access=snapshots["access_snapshot"])
    record["ai_review"]["display_snapshot"] = select_admitted_body(
        admission.payload["bundle"], capability=display_capability)
    record["display_snapshot"] = compile_literal_text(
        f"종목: {context['ticker']} {context['name']}" if context["ticker"] or context["name"] else "저장된 복기")
    record["history_read_status"] = "canonical"
    record["trade_restore_allowed"] = bool(_restorable(snapshots["trade_snapshot"])
        or any(_restorable(trade) for trade in snapshots["recent_trades_snapshot"]))
    validate_read_safety(record, {}, unsafe_text=unsafe_text)
    return json.loads(sql_json(record))
