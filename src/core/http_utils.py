"""
HTTP helpers: retries with backoff for flaky networks (models, FFmpeg zip, etc.).
"""

from __future__ import annotations

import time
from typing import Any

import requests

# Transient errors worth retrying
_RETRY_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def requests_get_stream_with_retries(
    url: str,
    *,
    attempts: int = 3,
    base_delay_s: float = 1.5,
    session: requests.Session | None = None,
    **kwargs: Any,
) -> requests.Response:
    """
    GET with ``stream=True``, retrying on connection/timeout/chunk errors and HTTP 5xx.
    Returns a context manager response (caller must use ``with`` or ``close()``).
    """
    sess = session or requests.Session()
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            r = sess.get(url, stream=True, **kwargs)
            if r.status_code >= 500 and attempt < attempts - 1:
                r.close()
                time.sleep(base_delay_s * (2**attempt))
                continue
            r.raise_for_status()
            return r
        except _RETRY_EXCEPTIONS as e:
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(base_delay_s * (2**attempt))
        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code >= 500 and attempt < attempts - 1:
                try:
                    resp.close()
                except Exception:
                    pass
                time.sleep(base_delay_s * (2**attempt))
                last_exc = e
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("requests_get_stream_with_retries: exhausted without response")
