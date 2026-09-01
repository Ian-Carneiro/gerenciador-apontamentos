"""
Ponto de entrada — Apontador de Horas v5.

Ordem de bootstrap:
  1. init_db()              → cria tabelas SQLite se não existirem
  2. ApontamentoService()   → instancia repo + service
  3. QApplication + MainWindow
"""

from pathlib import Path
import sys

# Garante que src/ esteja no path ao rodar direto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.apontamento_service import ApontamentoService
from src.db.database import init_db
from src.ui.main_window import MainWindow
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    # 1. Banco de dados
    try:
        init_db()
        logger.info("✅ Banco inicializado")
    except Exception as e:
        logger.critical(f"❌ Falha ao inicializar banco: {e}", exc_info=True)
        sys.exit(1)

    # 2. Service
    service = ApontamentoService()

    # 3. Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Apontador de Horas")
    app.setApplicationVersion("5.0.0")

    # Suaviza o rendering em HiDPI
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = MainWindow(service)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
