"""
confirmacao_dialogs.py — Diálogos de confirmação de envio para automações.

Funções:
    confirmar_apontamentos_netproject() — tabela de apontamentos NetProject
    confirmar_horarios_sgiweb()         — tabela de marcações SGIWeb

Para diálogos genéricos de entrada de dados (pedir_data, selecionar_recurso),
use src.ui.dialogs.utils_dialogs.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


def confirmar_apontamentos_netproject(
    apontamentos: list[dict], data_str: str, parent: QWidget | None = None
) -> bool:
    """Exibe diálogo de confirmação visual para apontamentos NetProject"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Confirmar Apontamentos - NetProject")
    dlg.resize(1000, 500)
    dlg.setModal(True)
    dlg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(dlg)
    layout.addWidget(_label_titulo(f"📋 Apontamentos do dia {data_str}"))
    layout.addWidget(QLabel(f"Total: {len(apontamentos)} apontamento(s)"))

    tabela = QTableWidget(len(apontamentos), 5)
    tabela.setHorizontalHeaderLabels(["Projeto", "Tarefa", "Início", "Fim", "Horas"])
    tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

    for row, apt in enumerate(apontamentos):
        hora_fim = apt["hora_fim"] or "Em andamento"
        horas = (
            f"{apt['horas_trabalhadas']:.2f}h" if apt.get("horas_trabalhadas") else "Em andamento"
        )
        for col, valor in enumerate(
            [apt["projeto"], apt["tarefa"], apt["hora_inicio"], hora_fim, horas]
        ):
            tabela.setItem(row, col, QTableWidgetItem(str(valor)))

    layout.addWidget(tabela)

    confirmado = {"valor": False}

    def confirmar():
        confirmado["valor"] = True
        dlg.accept()

    layout.addLayout(_botoes(confirmar, dlg.reject))
    dlg.exec()
    return confirmado["valor"]


def confirmar_horarios_sgiweb(
    horarios: list[str], data_str: str, parent: QWidget | None = None
) -> bool:
    """Exibe diálogo de confirmação visual para horários SGIWeb"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Confirmar Apontamentos - SGIWeb")
    dlg.resize(600, 400)
    dlg.setModal(True)
    dlg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(dlg)
    layout.addWidget(_label_titulo(f"📋 Horários para {data_str}"))
    layout.addWidget(QLabel(f"Total: {len(horarios)} marcação(ões)"))

    tabela = QTableWidget(len(horarios), 2)
    tabela.setHorizontalHeaderLabels(["Tipo", "Horário"])
    tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

    for row, horario in enumerate(horarios):
        tipo = "🟢 Entrada" if row % 2 == 0 else "🔴 Saída"
        tabela.setItem(row, 0, QTableWidgetItem(tipo))
        item_h = QTableWidgetItem(horario)
        item_h.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tabela.setItem(row, 1, item_h)

    layout.addWidget(tabela)

    if len(horarios) % 2 != 0:
        aviso = QLabel(
            "⚠️ ATENÇÃO: Número ímpar de marcações detectado!\n"
            "Última saída será ignorada pelo sistema."
        )
        aviso.setObjectName("lblAvisoAlerta")
        layout.addWidget(aviso)

    confirmado = {"valor": False}

    def confirmar():
        confirmado["valor"] = True
        dlg.accept()

    layout.addLayout(_botoes(confirmar, dlg.reject))
    dlg.exec()
    return confirmado["valor"]


def _label_titulo(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setObjectName("labelAppTitle")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


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
