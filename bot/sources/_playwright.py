"""Общий помощник: рендер страницы headless-браузером (для Tier 3).

Playwright — опциональная зависимость. Если не установлен, источники Profi/
Яндекс просто пропускаются с понятным сообщением.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_INSTALL_HINT = (
    "Playwright не установлен. Для Profi.ru/Яндекс Услуг выполни:\n"
    "    pip install playwright\n"
    "    python -m playwright install chromium"
)


def render_html(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = 20000,
    storage_state: str | None = None,
) -> str | None:
    """Открыть URL в headless Chromium и вернуть HTML после загрузки.

    storage_state — путь к JSON c сохранённой сессией (куки после ручного входа),
    нужен для площадок, где заказы видны только авторизованному исполнителю.
    Возвращает None, если Playwright недоступен или страница не открылась.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning(_INSTALL_HINT)
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx_kwargs = {"locale": "ru-RU"}
            if storage_state:
                ctx_kwargs["storage_state"] = storage_state
            context = browser.new_context(**ctx_kwargs)
            page = context.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:  # noqa: BLE001 — селектор не появился, отдадим что есть
                    pass
            html = page.content()
            browser.close()
            return html
    except Exception as exc:  # noqa: BLE001
        log.warning("Playwright render %s не удался: %s", url, exc)
        return None
