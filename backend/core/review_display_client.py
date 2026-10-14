"""Client display compatibility only; this does not grant access or entitlement."""

from fastapi import HTTPException

from backend.core.review_display_capability import require_display_capability


REVIEW_DISPLAY_CONTRACT_HEADER = "X-Review-Display-Contract"
UNSUPPORTED_CLIENT_CODE = "unsupported_review_display_client"
UPDATE_REQUIRED_MESSAGE = "AI 복기를 표시하려면 앱을 업데이트해 주세요."


def require_review_display_client(values: list[str] | None) -> str:
    # FastAPI's list Header preserves duplicate field lines. Do not split,
    # strip or normalize values into apparent support for the exact contract.
    if type(values) is list and len(values) == 1:
        try:
            return require_display_capability(values[0])
        except ValueError:
            pass
    raise HTTPException(
        status_code=426,
        detail={"code": UNSUPPORTED_CLIENT_CODE, "message": UPDATE_REQUIRED_MESSAGE},
    )
