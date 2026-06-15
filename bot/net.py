"""Тонкая обёртка над httpx: GET с ретраями, таймаутом и вежливыми паузами."""
from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def get(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = 20.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> httpx.Response:
    """GET с ретраями. Бросает последнюю ошибку, если все попытки провалились."""
    last_exc: Exception | None = None
    hdrs = {"User-Agent": DEFAULT_UA, "Accept-Language": "ru,en;q=0.8"}
    if headers:
        hdrs.update(headers)

    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(
                url, headers=hdrs, params=params, timeout=timeout, follow_redirects=True
            )
            if resp.status_code == 200:
                return resp
            log.warning("GET %s -> HTTP %s (попытка %s/%s)", url, resp.status_code, attempt, retries)
            last_exc = httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )
        except Exception as exc:  # noqa: BLE001 — нам важно дотерпеть до ретрая
            log.warning("GET %s -> %s (попытка %s/%s)", url, exc, attempt, retries)
            last_exc = exc

        if attempt < retries:
            time.sleep(backoff * attempt)

    assert last_exc is not None
    raise last_exc
