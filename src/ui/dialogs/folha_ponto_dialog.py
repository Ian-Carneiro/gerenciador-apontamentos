"""Diálogo de importação de apontamentos históricos via Espelho de Ponto (PDF)"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.automacao.folha_ponto_import import PROJETO_HISTORICO, RegistroHistorico
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImportarFolhaPontoDialog(QDialog):
    """
    Prévia dos apontamentos extraídos do(s) Espelho(s) de Ponto, com um
    checkbox por linha. Dias que já têm apontamento local vêm desmarcados
    por padrão, pra evitar duplicar.
    """

    def __init__(self, registros: list[RegistroHistorico], repo, parent: QWidget | None = None):
        """Monta o diálogo de preview com um checkbox por registro extraído."""
        super().__init__(parent)
        self.setWindowTitle("Importar Folha de Ponto")
        self.resize(700, 520)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._repo = repo
        self._registros = registros
        self._checkboxes: list[QCheckBox] = []

        self._build_ui()

    def _build_ui(self):
        """Monta a tabela de preview (data/entrada/saída/horas/checkbox de importação)."""
        layout = QVBoxLayout(self)

        titulo = QLabel("📄 Apontamentos extraídos da folha de ponto")
        titulo.setObjectName("labelAppTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        n_conflitos = sum(1 for r in self._registros if r.ja_existe)
        if n_conflitos:
            layout.addWidget(
                QLabel(
                    f"⚠️ {n_conflitos} linha(s) em dias que já têm apontamento local "
                    "vêm desmarcadas — marque manualmente se quiser sobrescrever."
                )
            )

        tabela = QTableWidget(len(self._registros), 5)
        tabela.setHorizontalHeaderLabels(["Data", "Entrada", "Saída", "Horas", "Importar"])
        tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        for row, reg in enumerate(self._registros):
            tabela.setItem(row, 0, QTableWidgetItem(reg.data.strftime("%d/%m/%Y (%a)")))
            tabela.setItem(row, 1, QTableWidgetItem(reg.inicio[:5]))
            tabela.setItem(row, 2, QTableWidgetItem(reg.fim[:5]))
            tabela.setItem(row, 3, QTableWidgetItem(f"{reg.horas:.2f}h"))

            chk = QCheckBox()
            chk.setChecked(not reg.ja_existe)
            if reg.ja_existe:
                chk.setToolTip("Já existem apontamentos locais nesse dia")
            self._checkboxes.append(chk)

            cell = QWidget()
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(chk)
            tabela.setCellWidget(row, 4, cell)

        layout.addWidget(tabela)

        row_botoes = QHBoxLayout()
        row_botoes.addStretch()
        btn_ok = QPushButton("✓ Importar selecionados")
        btn_ok.setObjectName("btnConfirmar")
        btn_ok.clicked.connect(self._on_importar)
        row_botoes.addWidget(btn_ok)
        btn_cancel = QPushButton("✗ Cancelar")
        btn_cancel.setObjectName("btnSecundario")
        btn_cancel.clicked.connect(self.reject)
        row_botoes.addWidget(btn_cancel)
        row_botoes.addStretch()
        layout.addLayout(row_botoes)

    def _on_importar(self):
        """Registra via repo.registrar_retroativo cada linha marcada, ignorando sobreposição."""
        count = 0
        for reg, chk in zip(self._registros, self._checkboxes, strict=True):
            if not chk.isChecked():
                continue
            inicio_dt = datetime.combine(reg.data, datetime.strptime(reg.inicio, "%H:%M:%S").time())
            fim_dt = datetime.combine(reg.data, datetime.strptime(reg.fim, "%H:%M:%S").time())
            self._repo.registrar_retroativo(
                projeto=PROJETO_HISTORICO,
                tarefa="Importado da folha de ponto",
                inicio=inicio_dt,
                fim=fim_dt,
                nota="",
                ignorar_sobreposicao=True,
            )
            count += 1

        logger.info(f"✅ {count} apontamento(s) importado(s) da folha de ponto")
        self.accept()
