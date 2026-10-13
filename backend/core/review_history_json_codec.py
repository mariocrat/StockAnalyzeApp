"""Bounded, deterministic JSON for the pure durable history contract.

No I/O or authentication. Byte/node/depth checks precede semantic validators.
"""
import json
import math

CODEC_VERSION = "review-history-json.v1"
MAX_PAYLOAD_BYTES = 1_310_720
MAX_OUTER_BYTES = 2_622_464
MAX_NODES = 32_768
MAX_DEPTH = 16
MAX_STRING = 16_384


class DurableStorageError(ValueError):
    """Controlled contract failure; the code never includes rejected content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise DurableStorageError(code)


def check_byte_limit(buffer, maximum):
    require(type(buffer) is bytes, "INVALID_BYTES")
    require(bool(buffer) and (maximum is None or len(buffer) <= maximum), "BYTE_LIMIT")


def validate_json_tree(value, *, max_depth=MAX_DEPTH, max_nodes=MAX_NODES, max_string=MAX_STRING):
    """Count value nodes once (not keys), root depth zero, without coercion."""
    count, active = 0, set()

    def text(item, maximum):
        require(maximum is None or len(item) <= maximum, "STRING_LIMIT")
        require(not any(0xD800 <= ord(char) <= 0xDFFF for char in item), "SURROGATE")

    def visit(node, depth):
        nonlocal count
        count += 1
        require(count <= max_nodes, "NODE_LIMIT")
        require(depth <= max_depth, "DEPTH_LIMIT")
        kind = type(node)
        if kind in (dict, list):
            require(id(node) not in active, "JSON_CYCLE")
            require(len(node) <= max_nodes, "NODE_LIMIT")
            active.add(id(node))
            if kind is dict:
                for key in node:
                    require(type(key) is str, "INVALID_JSON_TYPE")
                    text(key, 64)
                children = node.values()
            else:
                children = node
            for child in children:
                visit(child, depth + 1)
            active.remove(id(node))
        elif kind is str:
            text(node, max_string)
        elif kind is float:
            require(math.isfinite(node), "NONFINITE")
        else:
            require(kind in (int, bool, type(None)), "INVALID_JSON_TYPE")

    visit(value, 0)
    return count


def canonical_json(value, *, max_bytes=MAX_PAYLOAD_BYTES, max_depth=MAX_DEPTH,
                   max_nodes=MAX_NODES, max_string=MAX_STRING):
    validate_json_tree(value, max_depth=max_depth, max_nodes=max_nodes, max_string=max_string)
    try:
        buffer = json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError) as error:
        raise DurableStorageError("INVALID_JSON") from error
    check_byte_limit(buffer, max_bytes)
    return buffer


def _lexical_depth(text, maximum):
    # Scan before json.loads so an adversarial nested carrier never reaches its
    # recursive decoder. Braces inside escaped strings are not nesting.
    nesting, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            nesting += 1
            require(nesting <= maximum + 1, "DEPTH_LIMIT")
        elif char in "]}":
            nesting -= 1


def decode_json(buffer, *, max_bytes=MAX_PAYLOAD_BYTES, max_depth=MAX_DEPTH,
                max_nodes=MAX_NODES, max_string=MAX_STRING, canonical=False):
    check_byte_limit(buffer, max_bytes)

    def unique(pairs):
        value = {}
        for key, child in pairs:
            require(key not in value, "DUPLICATE_KEY")
            value[key] = child
        return value

    def constant(_value):
        raise DurableStorageError("NONFINITE")

    try:
        text = buffer.decode("utf-8", errors="strict")
        _lexical_depth(text, max_depth)
        value = json.loads(text, object_pairs_hook=unique, parse_constant=constant)
    except (ValueError, UnicodeError, OverflowError, RecursionError) as error:
        if isinstance(error, DurableStorageError):
            raise
        raise DurableStorageError("INVALID_JSON") from error
    validate_json_tree(value, max_depth=max_depth, max_nodes=max_nodes, max_string=max_string)
    if canonical:
        require(canonical_json(value, max_bytes=max_bytes, max_depth=max_depth,
                               max_nodes=max_nodes, max_string=max_string) == buffer, "NONCANONICAL_JSON")
    return value


def outer_json(value):
    return canonical_json(value, max_bytes=MAX_OUTER_BYTES, max_depth=1,
                          max_nodes=6, max_string=None)


def decode_outer(buffer):
    return decode_json(buffer, max_bytes=MAX_OUTER_BYTES, max_depth=1,
                       max_nodes=6, max_string=None, canonical=True)


def sql_json(value):
    """SQL snapshots keep their existing 32/100000/16384 budgets."""
    return canonical_json(value, max_bytes=None, max_depth=32, max_nodes=100_000)


def decode_sql(buffer):
    # SQL spacing/key order is insignificant, but duplicate/nonfinite input is not.
    if type(buffer) is str:
        try:
            buffer = buffer.encode("utf-8")
        except UnicodeError as error:
            raise DurableStorageError("SURROGATE") from error
    return decode_json(buffer, max_bytes=None, max_depth=32, max_nodes=100_000)
