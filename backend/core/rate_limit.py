import math
import threading
import time


class InMemoryRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> dict:
        current = float(time.time() if now is None else now)
        safe_limit = max(1, int(limit or 1))
        safe_window = max(1, int(window_seconds or 1))
        cutoff = current - safe_window

        with self._lock:
            hits = [item for item in self._hits.get(str(key or ""), []) if item > cutoff]
            if len(hits) >= safe_limit:
                retry_after = max(1, math.ceil((hits[0] + safe_window) - current))
                self._hits[str(key or "")] = hits
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after_seconds": retry_after,
                    "limit": safe_limit,
                    "window_seconds": safe_window,
                }

            hits.append(current)
            self._hits[str(key or "")] = hits
            return {
                "allowed": True,
                "remaining": max(0, safe_limit - len(hits)),
                "retry_after_seconds": 0,
                "limit": safe_limit,
                "window_seconds": safe_window,
            }
