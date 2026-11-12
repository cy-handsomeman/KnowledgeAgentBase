"""进程内滑动窗口限流，用于演示环境的注册、登录、问答和用户搜索。"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from api.deps import get_current_user
from core.settings import settings
from models.user import User

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = threading.Lock()
_MAX_KEYS = 5000


def _consume(key: str, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()
    with _LOCK:
        bucket = _WINDOWS[key]
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        if len(_WINDOWS) > _MAX_KEYS:
            for stale_key in list(_WINDOWS)[:-_MAX_KEYS // 2]:
                if stale_key != key:
                    _WINDOWS.pop(stale_key, None)
        return True


def _reject(window_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="请求过于频繁，请稍后再试",
        headers={"Retry-After": str(window_seconds)},
    )


def ip_rate_limit(limit: int, window_seconds: int, scope: str):
    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        client = request.client.host if request.client else "unknown"
        if not _consume(f"{scope}:ip:{client}", limit, window_seconds):
            raise _reject(window_seconds)

    return dependency


def user_rate_limit(limit: int, window_seconds: int, scope: str):
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> None:
        if not settings.rate_limit_enabled:
            return
        if not _consume(f"{scope}:user:{current_user.id}", limit, window_seconds):
            raise _reject(window_seconds)

    return dependency
