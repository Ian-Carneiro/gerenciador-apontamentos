"""
RelatorioDialog — Relatório de horas: hoje, mês e banco de horas.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.apontamento_service import ApontamentoService, RelatorioJornada


def _fmt_horas(h: float, decimal: bool = False) -> str:
    sinal = "-" if h < 0 else ""
    h = abs(h)
    if decimal:
        arredondado = Decimal(str(h)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{sinal}{arredondado}h"
    horas = int(h)
    minutos = round((h - horas) * 60)
    if minutos == 60:
        horas += 1
        minutos = 0
    return f"{sinal}{horas}h {minutos:02d}min"


def _fmt_saldo(h: float, decimal: bool = False) -> str:
    fmt = _fmt_horas(h, decimal)
    return f"+{fmt}" if h >= 0 else fmt


class _CardRelatorio(QFrame):
    def __init__(self, titulo: str, parent=None):
        super().__init__(parent)
        self.setObjectName("cardRelatorio")
        v = QVBoxLayout(self)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setObjectName("labelFieldCaption")
        v.addWidget(lbl_titulo)
        self.lbl_valor = QLabel("—")
        self.lbl_valor.setObjectName("labelRelatorioValor")
        v.addWidget(self.lbl_valor)


class RelatorioDialog(QDialog):
    def __init__(self, service: ApontamentoService, parent: QWidget | None = None):
        super().__init__(parent)
        self._svc = service
        self.setWindowTitle("Relatório de Apontamentos")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._recarregar()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        linha_data = QHBoxLayout()
        linha_data.addWidget(QLabel("Data de referência:"))
        self._data_ref = QDateEdit(QDate.currentDate())
        self._data_ref.setCalendarPopup(True)
        self._data_ref.setDisplayFormat("dd/MM/yyyy")
        self._data_ref.dateChanged.connect(self._recarregar)
        linha_data.addWidget(self._data_ref)
        linha_data.addStretch()
        self._chk_sem_segundos = QCheckBox("Ignorar segundos")
        self._chk_sem_segundos.setChecked(True)
        self._chk_sem_segundos.toggled.connect(self._recarregar)
        linha_data.addWidget(self._chk_sem_segundos)
        self._chk_decimal = QCheckBox("Horas em decimal")
        self._chk_decimal.setChecked(False)
        self._chk_decimal.toggled.connect(self._recarregar)
        linha_data.addWidget(self._chk_decimal)
        layout.addLayout(linha_data)

        self._card_hoje = _CardRelatorio("HOJE", self)
        self._card_mes = _CardRelatorio("MÊS", self)
        self._card_banco = _CardRelatorio("BANCO DE HORAS", self)
        for card in (self._card_hoje, self._card_mes, self._card_banco):
            layout.addWidget(card)

        self._lbl_detalhe = QLabel()
        layout.addWidget(self._lbl_detalhe)
        self._tabela = QTableWidget(0, 4)
        self._tabela.setHorizontalHeaderLabels(["Data", "Esperado", "Trabalhado", "Saldo"])
        self._tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._tabela, stretch=1)

        row = QHBoxLayout()
        row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        row.addWidget(btn_fechar)
        layout.addLayout(row)

    def _recarregar(self):
        qd = self._data_ref.date()
        data_ref = date(qd.year(), qd.month(), qd.day())
        rel: RelatorioJornada = self._svc.calcular_relatorio(
            data_ref, sem_segundos=self._chk_sem_segundos.isChecked()
        )

        dec = self._chk_decimal.isChecked()

        def _h(v: float) -> str:
            return _fmt_horas(v, dec)

        def _s(v: float) -> str:
            return _fmt_saldo(v, dec)

        self._card_hoje.lbl_valor.setText(
            f"Trabalhado: {_h(rel.trabalhado_hoje)}   Faltam: {_h(rel.falta_hoje)}"
        )
        mes_range = f"{rel.periodo_mes_inicio.strftime('%d/%m')} – {rel.periodo_mes_fim.strftime('%d/%m/%Y')}"
        self._lbl_detalhe.setText(f"Detalhe do mês ({mes_range}):")
        self._card_mes.lbl_valor.setText(f"{mes_range}   Saldo: {_s(rel.saldo_mes)}")
        banco_range = f"{rel.periodo_banco_inicio.strftime('%d/%m')} – {rel.periodo_banco_fim.strftime('%d/%m/%Y')}"
        self._card_banco.lbl_valor.setText(
            f"{banco_range}   Saldo: {_s(rel.saldo_banco)}   "
            f"Dias úteis restantes: {rel.dias_uteis_restantes_banco}"
        )

        self._tabela.setRowCount(0)
        for dia_rel in reversed(rel.dias_mes):
            row = self._tabela.rowCount()
            self._tabela.insertRow(row)
            data_txt = dia_rel.data.strftime("%d/%m")
            if dia_rel.excecao is not None:
                data_txt += " 🔁" if dia_rel.excecao.recorrente else " •"
            self._tabela.setItem(row, 0, QTableWidgetItem(data_txt))
            self._tabela.setItem(row, 1, QTableWidgetItem(_h(dia_rel.esperado)))
            self._tabela.setItem(row, 2, QTableWidgetItem(_h(dia_rel.trabalhado)))
            self._tabela.setItem(row, 3, QTableWidgetItem(_s(dia_rel.saldo)))
