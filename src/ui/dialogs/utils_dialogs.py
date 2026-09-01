"""
utils_dialogs.py — Diálogos utilitários genéricos de entrada de dados.

Funções:
    pedir_data()                   — seletor de data com QDateEdit
    selecionar_recurso_netproject() — combo editável para escolher recurso
"""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def pedir_data(titulo: str = "Selecionar Data", parent: QWidget | None = None) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(titulo)
    dlg.setModal(True)
    dlg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Selecione a data a ser processada:"))

    campo_data = QDateEdit(QDate.currentDate())
    campo_data.setCalendarPopup(True)
    campo_data.setDisplayFormat("dd/MM/yyyy")
    layout.addWidget(campo_data)

    resultado: dict = {"data": None}

    def _confirmar():
        resultado["data"] = campo_data.date().toString("dd/MM/yyyy")
        dlg.accept()

    layout.addLayout(_botoes(_confirmar, dlg.reject))
    dlg.exec()
    return resultado["data"]


def selecionar_recurso_netproject(recursos: list[str], parent: QWidget | None = None) -> str | None:
    """
    Diálogo para escolher o nome do recurso (usuário) no NetProject,
    usado para filtrar tarefas atribuídas a você nos XMLs.

    Returns:
        Nome escolhido, ou None se cancelado.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle("Selecionar Recurso - NetProject")
    dlg.setModal(True)
    dlg.setMinimumWidth(360)
    dlg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Selecione seu nome como cadastrado no NetProject:"))

    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems(recursos)
    combo.setCurrentIndex(-1)
    layout.addWidget(combo)

    resultado: dict = {"valor": None}

    def _confirmar():
        valor = combo.currentText().strip()
        if not valor:
            return
        resultado["valor"] = valor
        dlg.accept()

    layout.addLayout(_botoes(_confirmar, dlg.reject))
    dlg.exec()
    return resultado["valor"]


# ── Helpers internos ──────────────────────────────────────────────────────────


def _botoes(on_confirmar, on_cancelar) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addStretch()

    btn_ok = QPushButton("✓ Confirmar")
    btn_ok.setObjectName("btnConfirmar")
    btn_ok.clicked.connect(on_confirmar)

    btn_cancel = QPushButton("✗ Cancelar")
    btn_cancel.setObjectName("btnSecundario")
    btn_cancel.clicked.connect(on_cancelar)

    row.addWidget(btn_ok)
    row.addWidget(btn_cancel)
    row.addStretch()
    return row
