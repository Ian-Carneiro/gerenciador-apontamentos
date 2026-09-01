"""Configuração centralizada da aplicação"""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv

# Obtém o diretório do executável ou script
if getattr(sys, "frozen", False):
    DIR_BASE = Path(os.path.dirname(sys.executable))
else:
    DIR_BASE = Path(os.path.dirname(os.path.abspath(__file__)))

# Carrega .env
load_dotenv(dotenv_path=DIR_BASE / ".env")

# Diretórios
DATA_DIR = DIR_BASE / "data"
LOG_DIR = DIR_BASE / "logs"
CACHE_DIR = DATA_DIR / ".cache"
RESOURCES_DIR = DIR_BASE / "resources"

# Cria diretórios necessários
for d in [DATA_DIR, LOG_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# Arquivos
ARQUIVO_APONTAMENTOS = DATA_DIR / "apontamentos.csv"
ARQUIVO_LOG = LOG_DIR / "app.log"
STATE_FILE = CACHE_DIR / "state.json"

# Credenciais NetProject
NETPROJECT_USER = os.getenv("USUARIO_NET_PROJECT", "")
NETPROJECT_PASS = os.getenv("SENHA_NET_PROJECT", "")

# Credenciais SGIWeb
SGIWEB_USER = os.getenv("SGI_WEB_LOGIN_USUARIO", "")
SGIWEB_PASS = os.getenv("SGI_WEB_LOGIN_SENHA", "")

# Chrome/Selenium
CHROME_BINARY = os.getenv("CHROME_BINARY", RESOURCES_DIR / "chrome-linux64/chrome")
CHROMEDRIVER_PATH = os.getenv(
    "CHROMEDRIVER_PATH", RESOURCES_DIR / "chromedriver-linux64/chromedriver"
)

# Timeouts
TIMEOUT_CURTO = 0.5
TIMEOUT_MEDIO = 2.0
TIMEOUT_LONGO = 10.0
SELENIUM_IMPLICIT_WAIT = 5

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 10

# Versão
VERSAO = "4.3.0"

# UI
WINDOW_MIN_WIDTH = 500
WINDOW_MIN_HEIGHT = 400
