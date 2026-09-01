"""
AjustarHorarioDialog — Ajusta início e/ou fim de um apontamento.

┌----------------------------------------------┐
│  Ajustar Horario                          │
│  Projeto > Tarefa                            │
│                                              │
│  INÍCIO ATUAL    09:00:00                    │
│  NOVO INÍCIO     [09:00:00]                  │
│                                              │
│  FIM ATUAL       11:30:00                    │
│  NOVO FIM        [11:30:00]                  │
│                                              │
│  Duração resultante: 2h 30min               │
│                                              │
│  [ ✓ Salvar ]          [ ✗ Cancelar ]        │
└----------------------------------------------┘
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from src.core.apontamento_service import ApontamentoService
from src.db.models import Apontamento
from src.db.repository import ApontamentoError, HorarioInvalidoError, SobreposicaoError
from src.ui.style.tokens import ACCENT_TEXT, BORDER, DANGER, TEXT_PRIMARY, TEXT_SECONDARY
from src.ui.widgets.hora_field import HoraField
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AjustarHorarioDialog(QDialog):
    """
    Permite ajustar início e/ou fim de um apontamento já salvo.
    Ambos os campos são opcionais — preencha só o que quer mudar.
    """

    def __init__(
        self,
        apontamento: Apontamento,
        service: ApontamentoService,
        eh_ultimo: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._apt = apontamento
        self._svc = service
        self._eh_ultimo = eh_ultimo

        self.setWindowTitle("Ajustar Horário")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._build_ui()

    # -- Build ----------------------------------------------------------------─

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        lbl = QLabel("Ajustar Horario")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(lbl)

        # Contexto
        proj = self._apt.projeto[:40] + "..." if len(self._apt.projeto) > 40 else self._apt.projeto
        tar = self._apt.tarefa[:40] + "..." if len(self._apt.tarefa) > 40 else self._apt.tarefa
        lbl_ctx = QLabel(f"{proj}  >  {tar}")
        lbl_ctx.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(lbl_ctx)

        layout.addSpacing(4)

        # -- Início ----------------------------------------------------------─
        layout.addWidget(self._caption("INÍCIO"))
        row_ini = QHBoxLayout()
        lbl_ini_atual = QLabel(self._apt.inicio.strftime("%H:%M:%S"))
        lbl_ini_atual.setStyleSheet(
            "font-family: 'JetBrains Mono','Consolas',monospace;"
            "font-size: 13px; color: #555A6E; min-width: 80px;"
        )
        row_ini.addWidget(QLabel("atual:"))
        row_ini.addWidget(lbl_ini_atual)
        row_ini.addStretch()
        layout.addLayout(row_ini)

        self._campo_inicio = HoraField("novo:")
        self._campo_inicio.set_valor(self._apt.inicio)
        self._campo_inicio.edit.textChanged.connect(self._atualizar_preview)
        layout.addWidget(self._campo_inicio)

        # -- Fim --------------------------------------------------------------─
        if self._apt.fim is not None:
            layout.addSpacing(8)
            layout.addWidget(self._caption("FIM"))
            row_fim = QHBoxLayout()
            lbl_fim_atual = QLabel(self._apt.fim.strftime("%H:%M:%S"))
            lbl_fim_atual.setStyleSheet(
                "font-family: 'JetBrains Mono','Consolas',monospace;"
                "font-size: 13px; color: #555A6E; min-width: 80px;"
            )
            row_fim.addWidget(QLabel("atual:"))
            row_fim.addWidget(lbl_fim_atual)
            row_fim.addStretch()
            layout.addLayout(row_fim)

            self._campo_fim = HoraField("novo:")
            self._campo_fim.set_valor(self._apt.fim)
            self._campo_fim.edit.textChanged.connect(self._atualizar_preview)
            layout.addWidget(self._campo_fim)

            if self._eh_ultimo:
                self._chk_remover_fim = QCheckBox("Remover fim (reabrir apontamento)")
                self._chk_remover_fim.toggled.connect(self._on_toggle_remover_fim)
                layout.addWidget(self._chk_remover_fim)
            else:
                self._chk_remover_fim = None
        else:
            self._campo_fim = None
            self._chk_remover_fim = None

        layout.addSpacing(8)

        # -- Preview de duração ------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self._lbl_preview = QLabel()
        self._lbl_preview.setStyleSheet("font-size: 13px; color: #7EC99A; padding: 4px 0;")
        layout.addWidget(self._lbl_preview)
        self._atualizar_preview()

        layout.addSpacing(4)

        # -- Botões ------------------------------------------------------------
        btns = QDialogButtonBox()
        self._btn_salvar = btns.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_cancelar = btns.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self._btn_salvar.setObjectName("btnIniciar")
        self._btn_cancelar.setObjectName("btnSecundario")
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @staticmethod
    def _caption(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setObjectName("labelFieldCaption")
        return lbl

    # -- Preview --------------------------------------------------------------─

    def _atualizar_preview(self):
        ini = self._campo_inicio.valor(self._apt.inicio.date())
        remover_fim = bool(self._chk_remover_fim and self._chk_remover_fim.isChecked())
        fim_data_base = self._apt.fim.date() if self._apt.fim else self._apt.inicio.date()
        fim = (
            None
            if remover_fim
            else (self._campo_fim.valor(fim_data_base) if self._campo_fim else None)
        )

        if remover_fim:
            self._lbl_preview.setText("Apontamento voltará a ficar em execução")
            self._lbl_preview.setStyleSheet(
                f"font-size: 13px; color: {TEXT_SECONDARY}; padding: 4px 0;"
            )
            return

        if ini and fim:
            if fim > ini:
                delta = fim - ini
                total_s = int(delta.total_seconds())
                h = total_s // 3600
                m = (total_s % 3600) // 60
                s = total_s % 60
                dur = f"{h}h {m:02d}min" if h > 0 else f"{m:02d}:{s:02d}"
                self._lbl_preview.setText(f"Duração resultante: {dur}")
                self._lbl_preview.setStyleSheet(
                    f"font-size: 13px; color: {ACCENT_TEXT}; padding: 4px 0;"
                )
            else:
                self._lbl_preview.setText("Fim deve ser posterior ao inicio")
                self._lbl_preview.setStyleSheet(
                    f"font-size: 13px; color: {DANGER}; padding: 4px 0;"
                )
        elif ini and not fim:
            self._lbl_preview.setText("Apontamento em execução a partir do novo início")
            self._lbl_preview.setStyleSheet(
                f"font-size: 13px; color: {TEXT_SECONDARY}; padding: 4px 0;"
            )
        else:
            self._lbl_preview.setText("")

    def _on_toggle_remover_fim(self, marcado: bool):
        self._campo_fim.setEnabled(not marcado)
        self._atualizar_preview()

    # -- Salvar ----------------------------------------------------------------

    def _salvar(self):
        novo_inicio = self._campo_inicio.valor(self._apt.inicio.date())
        fim_data_base = self._apt.fim.date() if self._apt.fim else self._apt.inicio.date()
        novo_fim = self._campo_fim.valor(fim_data_base) if self._campo_fim else None

        if novo_inicio is None:
            self._erro("Início inválido. Use o formato HH:MM:SS.")
            return

        if self._campo_fim and novo_fim is None:
            self._erro("Fim inválido. Use o formato HH:MM:SS.")
            return

        try:
            if self._chk_remover_fim and self._chk_remover_fim.isChecked():
                self._svc.reabrir(self._apt.id)
                logger.info(f"Fim removido (reaberto): id={self._apt.id}")
                self.accept()
                return

            delta_ini = novo_inicio - self._apt.inicio if novo_inicio != self._apt.inicio else None
            delta_fim = (
                (novo_fim - self._apt.fim)
                if (self._apt.fim and novo_fim and novo_fim != self._apt.fim)
                else None
            )

            if delta_ini or delta_fim:
                self._svc.slide_adjacentes(self._apt, delta_ini=delta_ini, delta_fim=delta_fim)

            if novo_inicio != self._apt.inicio:
                # fim antigo ainda não foi atualizado aqui; se ele também vai mudar,
                # o intervalo intermediário pode colidir com o vizinho já deslocado
                self._svc.ajustar_inicio(
                    self._apt.id, novo_inicio, ignorar_sobreposicao=bool(delta_fim)
                )

            if (self._apt.fim is not None and novo_fim is not None) and novo_fim != self._apt.fim:
                self._svc.ajustar_fim(self._apt.id, novo_fim)

            logger.info(f"Horario ajustado: id={self._apt.id}")
            self.accept()

        except HorarioInvalidoError as e:
            self._erro(str(e))
        except SobreposicaoError as e:
            c = e.conflito
            self._erro(
                f"Novo intervalo conflita com:\n\n"
                f"  {c.projeto}  >  {c.tarefa}\n"
                f"  {c.inicio.strftime('%H:%M')} - "
                f"{c.fim.strftime('%H:%M') if c.fim else '...'}"
            )
        except ApontamentoError as e:
            self._erro(str(e))

    def _erro(self, msg: str):
        QMessageBox.warning(self, "Erro", msg)
