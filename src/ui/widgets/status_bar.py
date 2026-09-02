"""
StatusBar — barra de estado da janela principal.

Exibe:
  - Estado inativo: "● Nenhum apontamento em execução"
  - Estado ativo:   "● Em execução . Projeto > Tarefa . 1h 23min"
    (tempo decorrido atualizado a cada segundo via QTimer)

O led (●) muda de cor via propriedade dinâmica Qt + QSS:
  QLabel#ledStatus[status="idle"]   -> cinza
  QLabel#ledStatus[status="active"] -> verde musgo
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from src.db.models import Apontamento
from src.ui.style.tokens import GREEN, TEXT_MUTED


class StatusBar(QFrame):
    """
    Barra de estado que reflete o apontamento em execução.

    Uso:
        bar = StatusBar(parent)
        bar.set_ativo(apontamento)   # ao iniciar
        bar.set_inativo()            # ao parar
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelStatus")
        self.setFixedHeight(56)

        self._ativo: Apontamento | None = None
        self._inicio: datetime | None = None

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)  # 1 segundo
        self._timer.timeout.connect(self._tick)
        self._total_hoje_str = "0h 00min"

        self.set_inativo()

    # -- API pública ----------------------------------------------------------─

    def set_ativo(self, apontamento: Apontamento):
        """Exibe estado ativo e inicia o contador de tempo."""
        self._ativo = apontamento
        self._inicio = apontamento.inicio

        projeto = apontamento.projeto
        tarefa = apontamento.tarefa
        # Trunca para caber na barra
        if len(projeto) > 55:
            projeto = projeto[:53] + "..."
        if len(tarefa) > 55:
            tarefa = tarefa[:53] + "..."

        self._set_led_status("active")
        self._label_contexto.setText(f"{projeto}\n{tarefa}")
        self._label_contexto.setStyleSheet(f"color: {GREEN}; font-size: 11px; font-weight: 600;")
        self._tick()
        self._timer.start()

    def set_inativo(self):
        """Exibe estado inativo e para o contador."""
        self._ativo = None
        self._inicio = None

        self._timer.stop()
        self._led.setText("o")
        self._set_led_status("idle")
        self._label_contexto.setText("Nenhum apontamento em execucao")
        self._label_contexto.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")

    def set_total_hoje(self, total_horas: float):
        """Atualiza o contador total do dia no canto direito."""
        h = int(total_horas)
        m = int((total_horas - h) * 60)
        self._total_hoje_str = f"{h}h {m:02d}min"
        self._label_info.setText(f"...\nHoje: {self._total_hoje_str}")

    # -- Internos --------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # LED ●
        self._led = QLabel("●")
        self._led.setObjectName("ledStatus")
        self._led.setFixedWidth(14)
        self._led.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._led)

        # Contexto (projeto > tarefa)
        self._label_contexto = QLabel()
        self._label_contexto.setObjectName("labelStatus")
        layout.addWidget(self._label_contexto)

        self._label_tempo = QLabel()
        self._label_tempo.setObjectName("labelStatusActive")
        self._label_tempo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label_tempo)

        # Espaço elástico
        layout.addStretch()

        # Total do dia
        self._label_info = QLabel("Hoje: 0h 00min")
        self._label_info.setObjectName("labelTotalHoje")
        self._label_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label_info)

    def _tick(self):
        """Atualiza o tempo decorrido a cada segundo."""
        if self._inicio is None:
            return
        delta = datetime.now() - self._inicio
        total_s = int(delta.total_seconds())
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        tempo = f"{h}h {m:02d}min" if h > 0 else f"{m:02d}:{s:02d}"
        self._label_info.setText(f"{tempo}\nHoje: {self._total_hoje_str}")

    def _set_led_status(self, status: str):
        """Aplica propriedade dinâmica para o QSS reagir."""
        self._led.setProperty("status", status)
        self._led.style().unpolish(self._led)
        self._led.style().polish(self._led)
