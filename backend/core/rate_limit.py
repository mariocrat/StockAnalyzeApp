import math
import threading
import time


class InMemoryRateLimiter:
    def __init__(self, max_keys: int = 10000):
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}
        self._max_keys = max(1, int(max_keys or 1))

    def _prune_expired_keys(self, cutoff: float) -> None:
        expired_keys = [
            key
            for key, hits in self._hits.items()
            if not [item for item in hits if item > cutoff]
        ]
        for key in expired_keys:
            self._hits.pop(key, None)

    def _evict_oldest_key(self) -> None:
        if not self._hits:
            return
        oldest_key = min(self._hits, key=lambda key: max(self._hits[key]) if self._hits[key] else 0)
        self._hits.pop(oldest_key, None)

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
            safe_key = str(key or "")
            if safe_key not in self._hits and len(self._hits) >= self._max_keys:
                self._prune_expired_keys(cutoff)
                if len(self._hits) >= self._max_keys:
                    self._evict_oldest_key()

            hits = [item for item in self._hits.get(safe_key, []) if item > cutoff]
            if len(hits) >= safe_limit:
                retry_after = max(1, math.ceil((hits[0] + safe_window) - current))
                self._hits[safe_key] = hits
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after_seconds": retry_after,
                    "limit": safe_limit,
                    "window_seconds": safe_window,
                }

            hits.append(current)
            self._hits[safe_key] = hits
            return {
                "allowed": True,
                "remaining": max(0, safe_limit - len(hits)),
                "retry_after_seconds": 0,
                "limit": safe_limit,
                "window_seconds": safe_window,
            }
