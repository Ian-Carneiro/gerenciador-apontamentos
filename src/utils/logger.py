import logging
import os
from pathlib import Path
import sys
from logging.handlers import RotatingFileHandler

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
    COLORS = {
        "DEBUG": "\033[94m",  # Azul
        "INFO": "\033[92m",  # Verde
        "WARNING": "\033[93m",  # Amarelo
        "ERROR": "\033[91m",  # Vermelho
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


# --- Console Handler (colorido) ---
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(LOG_FORMAT, DATE_FORMAT))

# --- File Handler (Log único com crescimento controlado) ---
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,  # 1 MB
    backupCount=10  # mantém 10 versões
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# --- Configuração principal ---
logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[console_handler, file_handler],
)


# Função auxiliar pra obter logger por módulo
def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)


# Exemplo de uso direto (opcional)
if __name__ == "__main__":
    log = get_logger(__name__)
    log.debug("Debug ativo")
    log.info("Aplicação iniciada")
    log.warning("Aviso de teste")
    log.error("Erro simulado")
    log.critical("Falha crítica")
