# -*- coding: utf-8 -*-
"""
HoraField — widget reutilizável de entrada de horário HH:MM:SS.

Composto por um QLabel (caption) + QLineEdit monospace com máscara
automática de dígitos.

Uso:
    campo = HoraField("INÍCIO")
    campo.set_valor(datetime.now())
    dt = campo.valor()   # datetime ou None se inválido
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget


# ── Helpers (também importáveis diretamente) ───────────────────────────────────

def hora_validator() -> QRegularExpressionValidator:
    """Aceita HH:MM:SS (00:00:00 – 23:59:59)."""
    return QRegularExpressionValidator(
        QRegularExpression(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
    )


def parse_hora(texto: str, data_base: Optional[date] = None) -> Optional[datetime]:
    """Converte 'HH:MM:SS' para datetime na data_base (ou hoje, se omitida)."""
    try:
        t = datetime.strptime(texto.strip(), "%H:%M:%S")
        base = data_base or datetime.now().date()
        return datetime.combine(base, t.time())
    except ValueError:
        return None


# ── Widget ────────────────────────────────────────────────────────────────────

class HoraField(QWidget):
    """Label + QLineEdit monospace para um horário HH:MM:SS."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setObjectName("labelFieldCaption")
        lbl.setFixedWidth(52)
        layout.addWidget(lbl)

        self.edit = QLineEdit()
        self.edit.setObjectName("lineEditHora")
        self.edit.setPlaceholderText("HH:MM:SS")
        self.edit.setMaxLength(8)
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.textEdited.connect(self._aplicar_mascara)
        layout.addWidget(self.edit)

    # ── API pública ───────────────────────────────────────────────────────────

    def valor(self, data_base: Optional[date] = None) -> Optional[datetime]:
        """Retorna datetime na data_base (ou hoje) com o horário digitado, ou None."""
        return parse_hora(self.edit.text(), data_base)

    def limpar(self):
        self.edit.clear()

    def set_valor(self, dt: datetime):
        self.edit.setText(dt.strftime("%H:%M:%S"))

    def setEnabled(self, enabled: bool):  # noqa: N802
        super().setEnabled(enabled)
        self.edit.setEnabled(enabled)

    # ── Máscara automática ────────────────────────────────────────────────────

    def _aplicar_mascara(self, texto: str):
        """Insere ':' automaticamente enquanto o usuário digita."""
        apenas_digitos = texto.replace(":", "")[:6]
        formatado = apenas_digitos
        if len(apenas_digitos) >= 3:
            formatado = apenas_digitos[:2] + ":" + apenas_digitos[2:]
        if len(apenas_digitos) >= 5:
            formatado = (
                apenas_digitos[:2] + ":" +
                apenas_digitos[2:4] + ":" +
                apenas_digitos[4:]
            )
        if formatado != texto:
            self.edit.blockSignals(True)
            self.edit.setText(formatado)
            self.edit.blockSignals(False)