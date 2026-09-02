"""Page Object Model - Classe Base - PLAYWRIGHT"""

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, ViewportSize
from screeninfo import get_monitors

import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BasePage:
    """Classe base para Page Objects (Playwright)"""

    def __init__(self, page: Page):
        self.page = page

    def sleep(self, seconds: float = config.TIMEOUT_CURTO):
        self.page.wait_for_timeout(seconds * 1000)


class BrowserManager:
    """Gerenciador de browser com configurações otimizadas"""

    @staticmethod
    def obter_monitor():
        """Obtém monitor secundário ou principal"""
        try:
            monitors = get_monitors()
            if len(monitors) > 1:
                monitor = next(
                    (m for m in monitors if not getattr(m, "is_primary", False)), monitors[0]
                )
                x, y = monitor.x, monitor.y
                logger.info(f"🖥️ Monitor secundário: {monitor.name or 'sem nome'}")
            else:
                monitor = monitors[0]
                x = y = 0
                logger.info("🖥️ Monitor principal")
            return monitor, x, y
        except Exception as e:
            logger.warning(f"⚠️ Erro ao detectar monitores: {e}. Usando padrão.")

            class MonitorPadrao:
                width = 1920
                height = 1080

            return MonitorPadrao(), 0, 0

    @staticmethod
    def criar_pagina(playwright: Playwright) -> tuple[Browser, BrowserContext, Page]:
        """Cria browser + context (com cookies salvos, se houver) + page"""
        monitor, x, y = BrowserManager.obter_monitor()

        browser = playwright.chromium.launch(
            headless=False,
            args=[f"--window-position={x},{y}"],
        )

        state_path = Path(config.STATE_FILE)
        context = browser.new_context(
            viewport=ViewportSize(width=monitor.width, height=monitor.height),
            storage_state=str(state_path) if state_path.exists() else None,
        )
        context.set_default_timeout(config.TIMEOUT_LONGO * 1000)

        page = context.new_page()
        logger.info("✅ Browser Playwright inicializado")
        return browser, context, page
