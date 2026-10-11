"""Legacy-safe body admission and deterministic sealed-body serialization.

This is a conservative grammar admission, not a Markdown/frontend parser.
Only the validated canonical document is read. No text is repaired, normalized,
or recovered from a semantic tree or raw summary. Display text (not wire bytes)
and each strong range are the compatibility invariant.
"""

from dataclasses import dataclass
import re

from backend.core.review_display_contract import ReviewDisplayContractError, validate_document


CONTRACT_VERSION = "review-legacy-compatibility.v1"
# Reserve whole visible tokens even when markup would interrupt them on wire.
# Intentionally broader than the frontend's contextual patterns.
_BASIC_TOKENS = re.compile(r"총평|잘한[ \n]*점|아쉬운[ \n]*점|다음[ \n]*체크리스트")
_MA_TOKEN = re.compile(r"ma[ \n]*[0-9]", re.IGNORECASE | re.ASCII)
_BLOCK_PREFIX = re.compile(r"^(?:[-+] |[0-9]+[.)](?: |$)|-{3,}$)")
_LITERAL_MARKUP = frozenset("*_`[]#\\<>")


class LegacyCompatibilityContractError(ValueError):
    """Explicit rejection with a stable code; never include input text."""

    def __init__(self, code, block_index=None):
        self.code = code
        self.block_index = block_index
        super().__init__(code)


@dataclass(frozen=True)
class LegacyCompatibilitySummary:
    summary: str
    status: str = "success"
    contract_version: str = CONTRACT_VERSION


def validate_legacy_body(document):
    """Admit the complete canonical body without generating compatibility wire.

    Grammar: body / paragraph+ / (text | strong)+. Intermediate separators
    are exactly two LF characters and the last is empty. Paragraphs have no
    edge whitespace, non-ASCII-space whitespace, BOM or consecutive spaces.
    Strong runs also have no edge spaces. Literal markup delimiters, list/
    divider prefixes, basic-section tokens, and MA-number tokens are reserved.
    Lexical checks inspect joined visible paragraph text, and reserved patterns
    also inspect the complete canonical text, so run/paragraph boundaries cannot
    bypass admission. Text runs serialize verbatim; strong runs serialize as
    **text**, without normalization.
    """
    try:
        canonical = validate_document(document, expected_surface="body")
    except ReviewDisplayContractError as error:
        raise LegacyCompatibilityContractError("invalid_canonical_body") from error

    for index, block in enumerate(document["blocks"]):
        def reject(code):
            raise LegacyCompatibilityContractError(code, index)

        if block["type"] != "paragraph":
            reject("unsupported_block")
        expected_separator = "\n\n" if index + 1 < len(document["blocks"]) else ""
        if block["separator_after"] != expected_separator:
            reject("unsupported_separator")
        paragraph = "".join(run["text"] for run in block["runs"])
        if any((char.isspace() and char != " ") or char == "\ufeff" for char in paragraph):
            reject("unsupported_whitespace")
        if paragraph[0] == " " or paragraph[-1] == " ":
            reject("paragraph_edge_whitespace")
        if "  " in paragraph:
            reject("consecutive_whitespace")
        if any(run["type"] == "strong" and (run["text"][0] == " " or run["text"][-1] == " ")
               for run in block["runs"]):
            reject("strong_edge_whitespace")
        if _BASIC_TOKENS.search(paragraph):
            reject("reserved_basic_section")
        if _MA_TOKEN.search(paragraph):
            reject("reserved_ma_token")
        if "[데이터 확인]" in paragraph or "[합리적 추론]" in paragraph:
            reject("reserved_display_token")
        if any(char in _LITERAL_MARKUP for char in paragraph) or _BLOCK_PREFIX.search(paragraph):
            reject("literal_markdown")
    # Whitespace-sensitive legacy tokens may span the owned paragraph separators.
    # Reserve them over the whole canonical sequence without altering any bytes.
    if _BASIC_TOKENS.search(canonical):
        raise LegacyCompatibilityContractError("reserved_basic_section")
    if _MA_TOKEN.search(canonical):
        raise LegacyCompatibilityContractError("reserved_ma_token")


def admit_legacy_body(document):
    """Serialize an approved canonical body verbatim using the A1 wire grammar."""
    validate_legacy_body(document)
    wire = []
    for block in document["blocks"]:
        wire.extend(run["text"] if run["type"] == "text" else "**" + run["text"] + "**"
                    for run in block["runs"])
        wire.append(block["separator_after"])
    return LegacyCompatibilitySummary("".join(wire))
