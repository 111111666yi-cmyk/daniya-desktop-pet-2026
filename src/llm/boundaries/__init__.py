from __future__ import annotations

import time
from typing import Any, Callable

import requests


class BoundaryError(Exception):
    """边界层统一异常基类"""


class AuthError(BoundaryError):
    """鉴权失败 (401)"""


class RateLimitError(BoundaryError):
    """限流 (429)"""


class ServerError(BoundaryError):
    """服务端错误 (5xx)"""


class NetworkError(BoundaryError):
    """网络不可达"""


class MalformedResponse(BoundaryError):
    """响应解析失败"""


def _retry_request(
    fn: Callable[[], requests.Response],
    *,
    max_retries: int = 3,
    backoff_base: float = 1.0,
) -> requests.Response:
    """带退避的重试循环，只对可恢复错误重试。"""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = fn()
            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < max_retries:
                    time.sleep(retry_after if retry_after > 0 else backoff_base * (2 ** attempt))
                    continue
                raise RateLimitError("Rate limit exceeded, retries exhausted")
            if resp.status_code in (502, 503, 504):
                if attempt < max_retries:
                    time.sleep(backoff_base * (2 ** attempt))
                    continue
                raise ServerError(f"Server error: HTTP {resp.status_code}")
            if resp.status_code == 401:
                raise AuthError("Authentication failed (401)")
            resp.raise_for_status()
            return resp
        except requests.HTTPError as exc:
            # 不可重试的 HTTP 错误 (400, 402, 403, 404, 500, 501, 505+, ...)
            status = exc.response.status_code if exc.response is not None else 0
            if 400 <= status < 500:
                raise BoundaryError(f"Client error: HTTP {status}") from exc
            raise ServerError(f"Server error: HTTP {status}") from exc
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            raise NetworkError(str(exc)) from exc
    if last_exc:
        raise NetworkError(str(last_exc)) from last_exc
    raise BoundaryError("Unexpected retry loop exit")


def _parse_retry_after(resp: requests.Response) -> float:
    header = resp.headers.get("Retry-After", "")
    if header and header.isdigit():
        return float(header)
    return 0.0
