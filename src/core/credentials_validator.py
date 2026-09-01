"""Validador de Credenciais"""

import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CredentialsValidator:
    """Validador centralizado de credenciais (puro, sem UI)"""

    @staticmethod
    def validar_netproject() -> tuple[bool, str | None]:
        if not config.NETPROJECT_USER:
            msg = "Credencial NETPROJECT_USER não configurada no .env"
            logger.error(f"❌ {msg}")
            return False, msg
        if not config.NETPROJECT_PASS:
            msg = "Credencial NETPROJECT_PASS não configurada no .env"
            logger.error(f"❌ {msg}")
            return False, msg
        logger.debug("✅ Credenciais NetProject válidas")
        return True, None

    @staticmethod
    def validar_sgiweb() -> tuple[bool, str | None]:
        if not config.SGIWEB_USER:
            msg = "Credencial SGIWEB_USER não configurada no .env"
            logger.error(f"❌ {msg}")
            return False, msg
        if not config.SGIWEB_PASS:
            msg = "Credencial SGIWEB_PASS não configurada no .env"
            logger.error(f"❌ {msg}")
            return False, msg
        logger.debug("✅ Credenciais SGIWeb válidas")
        return True, None
