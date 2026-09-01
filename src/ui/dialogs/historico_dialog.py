# -*- coding: utf-8 -*-
"""
HistoricoDialog — Histórico de apontamentos com edição inline.

Layout:
  ┌--------------------------------------------------------------------┐
  │  📋  Histórico de Apontamentos                         [✕ Fechar] │
  ├--------------------------------------------------------------------┤
  │  Data       Projeto          Tarefa        Início   Fim    Horas  │
  │ ----------------------------------------------------------------─  │
  │  25/08      Desenvolvimento  Feature XYZ   09:00   10:30   1h30  │
  │             [✏️]  [⏱]  [✂️]  [🗑️]                               │
  │  25/08      Reuniões         Daily         08:00   09:00   1h00  │
  │             [✏️]  [⏱]  [✂️]  [🗑️]                               │
  │  -- Total do dia: 2h 30min --------------------------------------  │
  │ ...                                                                │
  └--------------------------------------------------------------------┘

Implementação:
  - QTableWidget com linhas de dados e linhas de ações intercaladas
  - Blocos agrupados por dia com linha de total entre eles
  - Botões de ação por apontamento via setCellWidget
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QFrame, QAbstractItemView,
)
from PySide6.QtGui import QIcon

from src.core.apontamento_service import ApontamentoService
from src.db.models import Apontamento
from src.db.repository import BlocoHistorico, ApontamentoError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# -- Constantes de coluna ------------------------------------------------------
COL_DATA    = 0
COL_PROJETO = 1
COL_TAREFA  = 2
COL_INICIO  = 3
COL_FIM     = 4
COL_HORAS   = 5
COL_ACOES   = 6
N_COLUNAS   = 7

CABECALHOS = ["Data", "Projeto", "Tarefa", "Início", "Fim", "Horas", "Ações"]

# -- Cores --------------------------------------------------------------------─
COR_BG_PAR    = QColor("#1A1D27")
COR_BG_IMPAR  = QColor("#1E2235")
COR_BG_TOTAL  = QColor("#131620")
COR_TEXTO     = QColor("#E8EAF0")
COR_MUTED     = QColor("#8B90A0")
COR_VERDE     = QColor("#7EC99A")
COR_VERMELHO  = QColor("#C0392B")
COR_ACENTO    = QColor("#4D7C5F")

SVG_NOTA = """
<svg xmlns="http://www.w3.org/2000/svg"
     width="14" height="14"
     viewBox="0 0 24 24"
     fill="none"
     stroke="#7EC99A"
     stroke-width="2"
     stroke-linecap="round"
     stroke-linejoin="round">
    <path d="M14 3v4a1 1 0 0 0 1 1h4"/>
    <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2Z"/>
    <line x1="9" y1="13" x2="15" y2="13"/>
    <line x1="9" y1="17" x2="15" y2="17"/>
</svg>
"""

def _icone_nota() -> QIcon:
    from PySide6.QtGui import QPixmap
    pixmap = QPixmap()
    pixmap.loadFromData(SVG_NOTA.encode("utf-8"), "SVG")
    return QIcon(pixmap)

def _item(texto: str, cor_bg: QColor = COR_BG_PAR,
          cor_txt: QColor = COR_TEXTO,
          negrito: bool = False,
          alinhamento=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) -> QTableWidgetItem:
    """Cria QTableWidgetItem pré-configurado."""
    it = QTableWidgetItem(texto)
    it.setBackground(QBrush(cor_bg))
    it.setForeground(QBrush(cor_txt))
    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    it.setTextAlignment(alinhamento)
    if negrito:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def _item_mono(texto: str, cor_bg: QColor = COR_BG_PAR,
               cor_txt: QColor = COR_TEXTO) -> QTableWidgetItem:
    """Item com fonte monoespaçada (para horários)."""
    it = _item(texto, cor_bg, cor_txt,
               alinhamento=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
    f  = QFont("JetBrains Mono, Consolas, monospace")
    f.setPointSize(10)
    it.setFont(f)
    return it


class _BotoesAcao(QWidget):
    """Widget com os 4 botões de ação para uma linha do histórico."""

    # ------------------------------------------------------------------
    # Ícones SVG embutidos
    # ------------------------------------------------------------------

    SVG_EDITAR = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#E8EAF0"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <path d="M12 20h9"/>
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/>
    </svg>
    """

    SVG_RELOGIO = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#E8EAF0"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/>
        <polyline points="12 7 12 12 15 14"/>
    </svg>
    """

    SVG_DIVIDIR = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#E8EAF0"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <circle cx="6" cy="6" r="2"/>
        <circle cx="18" cy="18" r="2"/>
        <path d="M8 8l8 8"/>
        <path d="M16 8l-4 4"/>
        <path d="M12 12l-4 4"/>
    </svg>
    """

    SVG_LIXEIRA = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#E8EAF0"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6l-1 14H6L5 6"/>
        <path d="M10 11v5"/>
        <path d="M14 11v5"/>
        <path d="M9 6V4h6v2"/>
    </svg>
    """

    SVG_LIXEIRA_HOVER = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#FF6B6B"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6l-1 14H6L5 6"/>
        <path d="M10 11v5"/>
        <path d="M14 11v5"/>
        <path d="M9 6V4h6v2"/>
    </svg>
    """

    SVG_DISABLED = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="#555B72"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/>
        <line x1="4" y1="4" x2="20" y2="20"/>
    </svg>
    """

    def __init__(
        self,
        apontamento: Apontamento,
        dialog: "HistoricoDialog",
        parent=None
    ):
        super().__init__(parent)

        self._apt = apontamento
        self._dialog = dialog

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self._btn_editar = self._btn(
            self._icon(self.SVG_EDITAR),
            "Editar projeto/tarefa/nota"
        )

        self._btn_ajustar = self._btn(
            self._icon(self.SVG_RELOGIO),
            "Ajustar horário"
        )

        self._btn_dividir = self._btn(
            self._icon(self.SVG_DIVIDIR),
            "Dividir apontamento"
        )

        self._btn_deletar = self._btn(
            self._icon(self.SVG_LIXEIRA),
            "Deletar apontamento",
            object_name="btnDel"
        )

        layout.addWidget(self._btn_editar)
        layout.addWidget(self._btn_ajustar)
        layout.addWidget(self._btn_dividir)
        layout.addWidget(self._btn_deletar)

        layout.addStretch()

        # --------------------------------------------------------------
        # Dividir só disponível para apontamentos finalizados
        # --------------------------------------------------------------

        self._btn_dividir.setEnabled(apontamento.fim is not None)

        self._btn_dividir.setToolTip(
            "Dividir apontamento"
            if apontamento.fim
            else "Finalize o apontamento para dividir"
        )

        # --------------------------------------------------------------
        # Conexões
        # --------------------------------------------------------------

        self._btn_editar.clicked.connect(self._on_editar)
        self._btn_ajustar.clicked.connect(self._on_ajustar)
        self._btn_dividir.clicked.connect(self._on_dividir)
        self._btn_deletar.clicked.connect(self._on_deletar)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _icon(svg: str) -> QIcon:
        """
        Cria um QIcon diretamente de uma string SVG.
        Não é necessário criar arquivos externos.
        """
        from PySide6.QtGui import QPixmap

        pixmap = QPixmap()

        if not pixmap.loadFromData(
            svg.encode("utf-8"),
            "SVG"
        ):
            raise ValueError("Não foi possível carregar o SVG do ícone.")

        return QIcon(pixmap)

    @staticmethod
    def _btn(icon: QIcon, tooltip: str, object_name: str = "btnAcao") -> QPushButton:
        """Cria um botão de ação com ícone."""
        b = QPushButton()
        b.setObjectName(object_name)
        b.setIcon(icon)
        b.setIconSize(QSize(16, 16))
        b.setToolTip(tooltip)
        b.setFixedSize(QSize(32, 28))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _on_editar(self):
        from src.ui.dialogs.editar_dialog import EditarDialog

        dlg = EditarDialog(
            self._apt,
            self._dialog._svc,
            parent=self._dialog
        )

        if dlg.exec() == EditarDialog.DialogCode.Accepted:
            self._dialog.recarregar()

    def _on_ajustar(self):
        from src.ui.dialogs.ajustar_horario_dialog import AjustarHorarioDialog

        dlg = AjustarHorarioDialog(
            self._apt,
            self._dialog._svc,
            eh_ultimo=(self._apt.id == self._dialog._ultimo_apt_id),
            parent=self._dialog
        )

        if dlg.exec() == AjustarHorarioDialog.DialogCode.Accepted:
            self._dialog.recarregar()

    def _on_dividir(self):
        from src.ui.dialogs.dividir_dialog import DividirDialog

        try:
            dlg = DividirDialog(
                self._apt,
                self._dialog._svc,
                parent=self._dialog
            )

            if dlg.exec() == DividirDialog.DialogCode.Accepted:
                self._dialog.recarregar()

        except ValueError as e:
            QMessageBox.warning(
                self._dialog,
                "Erro",
                str(e)
            )

    def _on_deletar(self):
        resp = QMessageBox.question(
            self._dialog,
            "Confirmar exclusão",
            f"Deletar o apontamento?\n\n"
            f"  {self._apt.projeto}  >  {self._apt.tarefa}\n"
            f"  {self._apt.inicio.strftime('%H:%M')} - "
            f"{self._apt.fim.strftime('%H:%M') if self._apt.fim else '...'}\n\n"
            f"Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if resp == QMessageBox.StandardButton.Yes:
            self._dialog._svc.deletar(self._apt.id)

            logger.info(
                f"Deletado id={self._apt.id} via historico"
            )

            self._dialog.recarregar()


# -- HistoricoDialog ----------------------------------------------------------─

class HistoricoDialog(QDialog):
    """
    Janela de histórico de apontamentos com edição inline.
    Agrupa por dia e exibe total de horas por bloco.
    """

    def __init__(self, service: ApontamentoService, parent=None):
        super().__init__(parent)
        self._svc = service

        self.setWindowTitle("Historico de Apontamentos")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)
        self.setModal(True)
        self.setSizeGripEnabled(True)

        self._build_ui()
        self.recarregar()

    # -- Build ----------------------------------------------------------------─

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabeçalho
        header = QFrame()
        header.setObjectName("dialogHeader")
        header.setFixedHeight(52)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)

        lbl = QLabel("Historico de Apontamentos")
        lbl.setObjectName("labelAppTitle")
        h_layout.addWidget(lbl)

        h_layout.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setObjectName("btnSecundario")
        btn_fechar.clicked.connect(self.accept)
        h_layout.addWidget(btn_fechar)

        layout.addWidget(header)

        # Tabela
        self._tabela = QTableWidget()
        self._tabela.setColumnCount(N_COLUNAS)
        self._tabela.setHorizontalHeaderLabels(CABECALHOS)
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setShowGrid(False)
        self._tabela.setAlternatingRowColors(False)
        self._tabela.horizontalHeader().setHighlightSections(False)


        # Larguras das colunas
        hh = self._tabela.horizontalHeader()
        hh.setSectionResizeMode(COL_DATA,    QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_PROJETO, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(COL_TAREFA,  QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_INICIO,  QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_FIM,     QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_HORAS,   QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_ACOES,   QHeaderView.ResizeMode.Fixed)
        # Larguras iniciais — usuário pode redimensionar livremente
        self._tabela.setColumnWidth(COL_PROJETO, 280)
        self._tabela.setColumnWidth(COL_TAREFA,  320)
        self._tabela.setColumnWidth(COL_ACOES,   160)
        hh.setMinimumSectionSize(60)
        hh.setStretchLastSection(False)

        layout.addWidget(self._tabela, stretch=1)

        # Rodapé
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer.setFixedHeight(36)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 0, 16, 0)

        self._lbl_total_geral = QLabel("")
        self._lbl_total_geral.setObjectName("labelStatus")
        f_layout.addWidget(self._lbl_total_geral)
        f_layout.addStretch()

        layout.addWidget(footer)

    # -- Carregar dados --------------------------------------------------------

    def recarregar(self):
        """Recarrega todos os dados do banco e reconstrói a tabela."""
        blocos: list[BlocoHistorico] = self._svc.obter_historico(limit_dias=60)
        self._ultimo_apt_id = blocos[0].apontamentos[0].id if blocos else None
        self._tabela.setRowCount(0)

        if not blocos:
            self._tabela.setRowCount(1)
            it = _item("Nenhum apontamento registrado ainda.",
                        cor_txt=COR_MUTED)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._tabela.setItem(0, 0, it)
            self._tabela.setSpan(0, 0, 1, N_COLUNAS)
            self._lbl_total_geral.setText("")
            return

        total_geral = 0.0
        linha_idx = 0
        par = True

        # Coleta todas as linhas primeiro, depois popula
        # Isso evita que setSpan invalide setCellWidget de linhas subsequentes
        linhas: list[tuple] = []  # (tipo, dados)

        for bloco in blocos:
            total_geral += bloco.total_horas
            for apt in bloco.apontamentos:
                linhas.append(("apt", apt))
            linhas.append(("total", bloco))

        # Pré-cria todas as linhas na tabela
        self._tabela.setRowCount(len(linhas))

        for i, (tipo, dado) in enumerate(linhas):
            if tipo == "apt":
                apt = dado
                cor_bg = COR_BG_PAR if par else COR_BG_IMPAR
                par = not par

                self._tabela.setRowHeight(i, 42)

                data_str  = apt.inicio.strftime("%d/%m")
                ini_str   = apt.inicio.strftime("%H:%M:%S")
                fim_str   = apt.fim.strftime("%H:%M:%S") if apt.fim else "..."
                horas_str = apt.duracao_str if apt.fim else "em exec."

                self._tabela.setItem(i, COL_DATA,    _item(data_str, cor_bg, COR_MUTED))
                self._tabela.setItem(i, COL_PROJETO, _item(apt.projeto, cor_bg))

                item_tarefa = _item(apt.tarefa, cor_bg, COR_MUTED)
                if apt.nota:
                    item_tarefa.setIcon(_icone_nota())
                    item_tarefa.setToolTip(apt.nota)
                self._tabela.setItem(i, COL_TAREFA, item_tarefa)

                self._tabela.setItem(i, COL_INICIO,  _item_mono(ini_str, cor_bg))
                self._tabela.setItem(i, COL_FIM,
                    _item_mono(fim_str, cor_bg, COR_VERDE if apt.fim else COR_MUTED))
                self._tabela.setItem(i, COL_HORAS,
                    _item(horas_str, cor_bg, COR_VERDE if apt.fim else COR_MUTED,
                          negrito=True,
                          alinhamento=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))

            else:
                bloco = dado
                self._tabela.setRowHeight(i, 28)
                apt_ultimo = bloco.apontamentos[-1]
                total_str = (
                    f"-- {apt_ultimo.inicio.strftime('%d/%m/%Y')} "
                    f". {len(bloco.apontamentos)} apontamento(s) "
                    f". Total: {bloco.total_str} --"
                )
                it_total = _item(
                    total_str,
                    cor_bg=COR_BG_TOTAL,
                    cor_txt=COR_MUTED,
                    negrito=False,
                    alinhamento=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                )
                it_total.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._tabela.setItem(i, 0, it_total)
                self._tabela.setSpan(i, 0, 1, N_COLUNAS)

        # setCellWidget APÓS todos os setItem e setSpan — evita invalidação
        par = True
        for i, (tipo, dado) in enumerate(linhas):
            if tipo == "apt":
                apt = dado
                cor_bg = COR_BG_PAR if par else COR_BG_IMPAR
                par = not par
                btns = _BotoesAcao(apt, self)
                # btns.setProperty("bgColor", cor_bg.name())
                self._tabela.setCellWidget(i, COL_ACOES, btns)

        # Total geral no rodapé
        h = int(total_geral)
        m = int((total_geral - h) * 60)
        self._lbl_total_geral.setText(
            f"{len(blocos)} dias exibidos  .  Total geral: {h}h {m:02d}min"
        )