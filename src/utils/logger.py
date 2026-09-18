"""
Configuração central de logging da aplicação.

Loga em console (colorido, exceto no Windows) e em arquivo rotativo
(logs/app.log, 1MB x 10 backups). Nível configurável via env var LOG_LEVEL.

Uso:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from typing import ClassVar

# Obtém o diretório do executável ou script
if getattr(sys, "frozen", False):
    DIR_BASE = Path(sys.executable).parent
else:
    DIR_BASE = Path(__file__).resolve().parents[2]

# Pasta padrão de logs
LOG_DIR = DIR_BASE / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Arquivo de log
LOG_FILE = LOG_DIR / "app.log"

# Nível de log configurável por env var (default = INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Formato de log base
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# --- Configuração de cores no console ---
class ColorFormatter(logging.Formatter):
    """Formatter que colore a mensagem por nível de log no console (sem efeito no Windows)."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m",
    }
    RESET: ClassVar[str] = "\033[0m"

    def format(self, record):
        """Formata o record normalmente e envolve com códigos ANSI de cor (exceto no Windows)."""
        if sys.platform == "win32":
            return super().format(record)
        color = self.COLORS.get(record.levelname, "")
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


# --- Console Handler (colorido) ---
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(LOG_FORMAT, DATE_FORMAT))

# --- File Handler (Log único com crescimento controlado) ---
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,  # 1 MB
    backupCount=10,  # mantém 10 versões
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# --- Configuração principal ---
logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[console_handler, file_handler],
)


# Função auxiliar pra obter logger por módulo
def get_logger(name: str | None = None) -> logging.Logger:
    """Retorna o logger para `name` (tipicamente __name__), já configurado por basicConfig."""
    return logging.getLogger(name)


# Exemplo de uso direto (opcional)
if __name__ == "__main__":
    log = get_logger(__name__)
    log.debug("Debug ativo")
    log.info("Aplicação iniciada")
    log.warning("Aviso de teste")
    log.error("Erro simulado")
    log.critical("Falha crítica")
