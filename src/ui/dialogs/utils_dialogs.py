"""
utils_dialogs.py — Diálogos utilitários genéricos de entrada de dados.

Funções:
    pedir_data()                   — seletor de data com QDateEdit
    selecionar_recurso_netproject() — combo editável para escolher recurso
"""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.ui.ui_helpers import linha_botoes_confirmar_cancelar
from src.ui.widgets.filterable_combo import FilterableComboBox


def pedir_data(titulo: str = "Selecionar Data", parent: QWidget | None = None) -> str | None:
    """Diálogo simples com QDateEdit; retorna a data escolhida como "dd/MM/yyyy", ou None se cancelado."""
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

    layout.addLayout(linha_botoes_confirmar_cancelar(_confirmar, dlg.reject))
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

    combo = FilterableComboBox(placeholder="Digite ou selecione...")
    combo.set_dados(recursos)
    layout.addWidget(combo)

    resultado: dict = {"valor": None}

    def _confirmar():
        valor = combo.valor_atual()
        if not valor:
            return
        resultado["valor"] = valor
        dlg.accept()

    layout.addLayout(linha_botoes_confirmar_cancelar(_confirmar, dlg.reject))
    dlg.exec()
    return resultado["valor"]
