# -*- coding: utf-8 -*-
"""
DividirDialog — Divide um apontamento em dois no horário de corte.

┌----------------------------------------------┐
│  Dividir Apontamento                     │
│                                              │
│  Projeto > Tarefa                            │
│  09:00 -> 12:00  (3h 00min)                  │
│                                              │
│  HORÁRIO DE CORTE    [10:30:00]              │
│                                              │
│  ┌--------------------------------------┐    │
│  │  Parte 1   09:00 -> 10:30   1h 30min │    │
│  │  Parte 2   10:30 -> 12:00   1h 30min │    │
│  └--------------------------------------┘    │
│                                              │
│  [ ✂️ Dividir ]        [ ✗ Cancelar ]        │
└----------------------------------------------┘
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QLabel, QVBoxLayout,
    QMessageBox,
)

from src.core.apontamento_service import ApontamentoService
from src.db.models import Apontamento
from src.db.repository import HorarioInvalidoError, ApontamentoError
from src.ui.style.tokens import ACCENT_TEXT, BORDER, DANGER, TEXT_PRIMARY, TEXT_SECONDARY
from src.ui.widgets.hora_field import HoraField
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _fmt_dur(ini: datetime, fim: datetime) -> str:
    """Formata duração entre dois datetimes como '1h 30min' ou '45min'."""
    total_s = int((fim - ini).total_seconds())
    h = total_s // 3600
    m = (total_s % 3600) // 60
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


class DividirDialog(QDialog):
    """
    Divide um apontamento finalizado em dois no horário de corte informado.
    O preview é atualizado em tempo real conforme o usuário digita.
    """

    def __init__(
        self,
        apontamento: Apontamento,
        service: ApontamentoService,
        parent=None,
    ):
        super().__init__(parent)
        self._apt = apontamento
        self._svc = service

        if apontamento.fim is None:
            raise ValueError("Só é possível dividir apontamentos finalizados.")

        self.setWindowTitle("Dividir Apontamento")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._build_ui()

    # -- Build ----------------------------------------------------------------─

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        lbl = QLabel("Dividir Apontamento")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(lbl)

        # Contexto
        proj = self._apt.projeto[:40] + "..." if len(self._apt.projeto) > 40 else self._apt.projeto
        tar  = self._apt.tarefa[:40]  + "..." if len(self._apt.tarefa) > 40  else self._apt.tarefa
        lbl_ctx = QLabel(f"{proj}  >  {tar}")
        lbl_ctx.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(lbl_ctx)

        # Período original
        ini_s  = self._apt.inicio.strftime("%H:%M:%S")
        fim_s  = self._apt.fim.strftime("%H:%M:%S")
        dur_s  = self._apt.duracao_str
        lbl_per = QLabel(f"{ini_s}  ->  {fim_s}  ({dur_s})")
        lbl_per.setStyleSheet(
            "font-family: 'JetBrains Mono','Consolas',monospace;"
            "font-size: 13px; color: #E8EAF0;"
        )
        layout.addWidget(lbl_per)

        layout.addSpacing(4)

        # Campo de corte
        layout.addWidget(self._caption("HORÁRIO DE CORTE"))
        self._campo_corte = HoraField("")
        self._campo_corte.edit.setPlaceholderText("HH:MM:SS")
        self._campo_corte.edit.textChanged.connect(self._atualizar_preview)
        layout.addWidget(self._campo_corte)

        layout.addSpacing(8)

        # Preview
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self._frame_preview = QFrame()
        self._frame_preview.setStyleSheet(
            "QFrame { background: #1A1D27; border-radius: 6px; padding: 4px; }"
        )
        preview_layout = QVBoxLayout(self._frame_preview)
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(12, 10, 12, 10)

        self._lbl_p1 = QLabel("Parte 1:  —")
        self._lbl_p2 = QLabel("Parte 2:  —")

        for lbl in (self._lbl_p1, self._lbl_p2):
            lbl.setStyleSheet(
                "font-family: 'JetBrains Mono','Consolas',monospace;"
                "font-size: 13px; color: #8B90A0;"
            )
            preview_layout.addWidget(lbl)

        layout.addWidget(self._frame_preview)

        self._lbl_aviso = QLabel("")
        self._lbl_aviso.setStyleSheet(f"font-size: 13px; color: {DANGER}; padding: 2px 0;")
        self._lbl_aviso.setWordWrap(True)
        layout.addWidget(self._lbl_aviso)

        layout.addSpacing(4)

        # Botões
        btns = QDialogButtonBox()
        self._btn_dividir  = btns.addButton("Dividir",   QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_cancelar = btns.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self._btn_dividir.setObjectName("btnIniciar")
        self._btn_cancelar.setObjectName("btnSecundario")
        self._btn_dividir.setEnabled(False)  # só habilita quando o corte for válido
        btns.accepted.connect(self._dividir)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @staticmethod
    def _caption(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setObjectName("labelFieldCaption")
        return lbl

    # -- Preview --------------------------------------------------------------─

    def _atualizar_preview(self):
        corte = self._campo_corte.valor(self._apt.inicio.date())
        self._lbl_aviso.setText("")
        self._btn_dividir.setEnabled(False)

        cor_ok  = f"font-family:'JetBrains Mono','Consolas',monospace; font-size: 13px; color:{ACCENT_TEXT};"
        cor_off = f"font-family:'JetBrains Mono','Consolas',monospace; font-size: 13px; color:{TEXT_SECONDARY};"

        if corte is None:
            self._lbl_p1.setText("Parte 1:  —")
            self._lbl_p2.setText("Parte 2:  —")
            self._lbl_p1.setStyleSheet(cor_off)
            self._lbl_p2.setStyleSheet(cor_off)
            return

        ini = self._apt.inicio
        fim = self._apt.fim  # não é None (validado no __init__)

        if not (ini < corte < fim):
            self._lbl_aviso.setText(
                f"O corte deve estar entre {ini.strftime('%H:%M:%S')} "
                f"e {fim.strftime('%H:%M:%S')}."
            )
            self._lbl_p1.setText("Parte 1:  —")
            self._lbl_p2.setText("Parte 2:  —")
            self._lbl_p1.setStyleSheet(cor_off)
            self._lbl_p2.setStyleSheet(cor_off)
            return

        # Cálculo das partes
        dur1 = _fmt_dur(ini, corte)
        dur2 = _fmt_dur(corte, fim)

        self._lbl_p1.setText(
            f"Parte 1:  {ini.strftime('%H:%M:%S')}  ->  {corte.strftime('%H:%M:%S')}   ({dur1})"
        )
        self._lbl_p2.setText(
            f"Parte 2:  {corte.strftime('%H:%M:%S')}  ->  {fim.strftime('%H:%M:%S')}   ({dur2})"
        )
        self._lbl_p1.setStyleSheet(cor_ok)
        self._lbl_p2.setStyleSheet(cor_ok)
        self._btn_dividir.setEnabled(True)

    # -- Dividir --------------------------------------------------------------─

    def _dividir(self):
        corte = self._campo_corte.valor(self._apt.inicio.date())
        if corte is None:
            QMessageBox.warning(self, "Erro", "Informe um horário de corte válido.")
            return

        try:
            p1, p2 = self._svc.dividir(self._apt.id, corte)
            logger.info(
                f"Dividido id={self._apt.id}: "
                f"{p1.inicio.strftime('%H:%M')}->{p1.fim.strftime('%H:%M')} | "
                f"{p2.inicio.strftime('%H:%M')}->{p2.fim.strftime('%H:%M')}"
            )
            self.accept()
        except HorarioInvalidoError as e:
            QMessageBox.warning(self, "Horário inválido", str(e))
        except ApontamentoError as e:
            QMessageBox.warning(self, "Erro", str(e))