"""Closed display capability and selection AFTER whole bundle admission."""
from core.review_display_contract import SCHEMA_VERSION as V1_CAPABILITY

DUAL_CAPABILITY = "review-display.v2"


def require_display_capability(value):
    if type(value) is not str or value not in (V1_CAPABILITY, DUAL_CAPABILITY):
        raise ValueError("unsupported review display capability")
    return value


def select_admitted_body(bundle, *, capability):
    """Select owned decoded content; this function grants no admission/authority.

    Callers must first validate the COMPLETE bundle and its live receipt or
    durable row admission, including the unrequested representation/auxiliary.
    The v1 summary stays a compatibility alias, never a source for v2 content.
    """
    require_display_capability(capability)
    if bundle["kind"] not in ("v1_only", "paired_v1_v2"):
        raise ValueError("invalid admitted review bundle kind")
    version = "v2" if capability == DUAL_CAPABILITY and bundle["kind"] == "paired_v1_v2" else "v1"
    return bundle["representations"][version]["document"]
