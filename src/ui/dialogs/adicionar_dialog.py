"""
AdicionarApontamentoDialog — Insere um novo apontamento antes ou depois
de um apontamento existente, deslocando o vizinho para evitar buraco/sobreposição.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from src.core.apontamento_service import ApontamentoService
from src.db.models import Apontamento
from src.db.repository import ApontamentoError, HorarioInvalidoError, SobreposicaoError
from src.ui.style.tokens import ACCENT_TEXT, BORDER, DANGER, TEXT_PRIMARY, TEXT_SECONDARY
from src.ui.widgets.filterable_combo import FilterableComboBox
from src.ui.widgets.hora_field import HoraField
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AdicionarApontamentoDialog(QDialog):
    """Adiciona um apontamento imediatamente antes ou depois de `apontamento`."""

    def __init__(self, apontamento: Apontamento, service: ApontamentoService, parent=None):
        super().__init__(parent)
        self._apt = apontamento
        self._svc = service

        self.setWindowTitle("Adicionar Apontamento")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._build_ui()
        self._atualizar_preview()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel("Adicionar Apontamento")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(lbl)

        proj = self._apt.projeto[:40] + "..." if len(self._apt.projeto) > 40 else self._apt.projeto
        tar = self._apt.tarefa[:40] + "..." if len(self._apt.tarefa) > 40 else self._apt.tarefa
        lbl_ctx = QLabel(f"Referência: {proj}  >  {tar}")
        lbl_ctx.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(lbl_ctx)

        ini_s = self._apt.inicio.strftime("%H:%M:%S")
        fim_s = self._apt.fim.strftime("%H:%M:%S") if self._apt.fim else "..."
        lbl_per = QLabel(f"{ini_s}  ->  {fim_s}")
        lbl_per.setStyleSheet(
            "font-family: 'JetBrains Mono','Consolas',monospace;font-size: 13px; color: #E8EAF0;"
        )
        layout.addWidget(lbl_per)

        layout.addSpacing(4)

        pos_row = QHBoxLayout()
        self._rb_antes = QRadioButton("Adicionar antes")
        self._rb_depois = QRadioButton("Adicionar depois")
        self._grp_pos = QButtonGroup(self)
        self._grp_pos.addButton(self._rb_antes)
        self._grp_pos.addButton(self._rb_depois)
        self._rb_antes.setChecked(True)
        self._rb_depois.setEnabled(self._apt.fim is not None)
        if self._apt.fim is None:
            self._rb_depois.setToolTip("Finalize o apontamento para adicionar depois")
        pos_row.addWidget(self._rb_antes)
        pos_row.addWidget(self._rb_depois)
        pos_row.addStretch()
        layout.addLayout(pos_row)
        self._rb_antes.toggled.connect(self._atualizar_preview)

        layout.addSpacing(4)

        layout.addWidget(self._caption("PROJETO"))
        self._combo_projeto = FilterableComboBox(placeholder="Selecionar projeto...")
        self._combo_projeto.valor_selecionado.connect(self._atualizar_preview)
        layout.addWidget(self._combo_projeto)

        layout.addWidget(self._caption("TAREFA"))
        self._combo_tarefa = FilterableComboBox(placeholder="Selecionar tarefa...")
        self._combo_tarefa.valor_selecionado.connect(self._atualizar_preview)
        layout.addWidget(self._combo_tarefa)

        self._popular_combos()

        layout.addWidget(self._caption("NOTA (opcional)"))
        self._campo_nota = QLineEdit()
        layout.addWidget(self._campo_nota)

        layout.addSpacing(4)
        layout.addWidget(self._caption("HORÁRIO"))
        self._campo_horario = HoraField("")
        self._campo_horario.edit.setPlaceholderText("HH:MM:SS")
        self._campo_horario.edit.textChanged.connect(self._atualizar_preview)
        layout.addWidget(self._campo_horario)

        layout.addSpacing(8)

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

        self._lbl_novo = QLabel("Novo:  —")
        self._lbl_vizinho = QLabel("")
        for lbl in (self._lbl_novo, self._lbl_vizinho):
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

        btns = QDialogButtonBox()
        self._btn_adicionar = btns.addButton("Adicionar", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_cancelar = btns.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self._btn_adicionar.setObjectName("btnIniciar")
        self._btn_cancelar.setObjectName("btnSecundario")
        self._btn_adicionar.setEnabled(False)
        btns.accepted.connect(self._adicionar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _popular_combos(self):
        dados_pt = self._svc.listar_projetos_tarefas()
        dicts = [{"projeto": pt.projeto, "tarefa": pt.tarefa} for pt in dados_pt]
        self._combo_projeto.set_dados(sorted({d["projeto"] for d in dicts}))
        self._combo_tarefa.set_dados_por_pai(
            dados=dicts,
            campo_proprio="tarefa",
            campo_pai="projeto",
            combo_pai=self._combo_projeto,
        )

    @staticmethod
    def _caption(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setObjectName("labelFieldCaption")
        return lbl

    def _posicao(self) -> str:
        return "antes" if self._rb_antes.isChecked() else "depois"

    def _atualizar_preview(self):
        horario = self._campo_horario.valor(self._apt.inicio.date())
        self._lbl_aviso.setText("")
        self._btn_adicionar.setEnabled(False)

        cor_ok = f"font-family:'JetBrains Mono','Consolas',monospace; font-size: 13px; color:{ACCENT_TEXT};"
        cor_off = f"font-family:'JetBrains Mono','Consolas',monospace; font-size: 13px; color:{TEXT_SECONDARY};"

        if horario is None:
            self._lbl_novo.setText("Novo:  —")
            self._lbl_vizinho.setText("")
            self._lbl_novo.setStyleSheet(cor_off)
            return

        if self._posicao() == "antes":
            if horario >= self._apt.inicio:
                self._lbl_aviso.setText(
                    f"O início deve ser anterior a {self._apt.inicio.strftime('%H:%M:%S')}."
                )
                self._lbl_novo.setText("Novo:  —")
                self._lbl_novo.setStyleSheet(cor_off)
                return
            self._lbl_novo.setText(
                f"Novo:  {horario.strftime('%H:%M:%S')}  ->  {self._apt.inicio.strftime('%H:%M:%S')}"
            )
            self._lbl_vizinho.setText("O apontamento anterior (se houver) terá o fim ajustado.")
        else:
            if self._apt.fim is None or horario <= self._apt.fim:
                fim_ref = self._apt.fim.strftime("%H:%M:%S") if self._apt.fim else "..."
                self._lbl_aviso.setText(f"O fim deve ser posterior a {fim_ref}.")
                self._lbl_novo.setText("Novo:  —")
                self._lbl_novo.setStyleSheet(cor_off)
                return
            self._lbl_novo.setText(
                f"Novo:  {self._apt.fim.strftime('%H:%M:%S')}  ->  {horario.strftime('%H:%M:%S')}"
            )
            self._lbl_vizinho.setText("O apontamento seguinte (se houver) terá o início ajustado.")

        self._lbl_novo.setStyleSheet(cor_ok)
        if self._combo_projeto.valor_atual() and self._combo_tarefa.valor_atual():
            self._btn_adicionar.setEnabled(True)

    def _adicionar(self):
        horario = self._campo_horario.valor(self._apt.inicio.date())
        projeto = self._combo_projeto.valor_atual()
        tarefa = self._combo_tarefa.valor_atual()

        if horario is None:
            QMessageBox.warning(self, "Erro", "Informe um horário válido.")
            return
        if not projeto or not tarefa:
            QMessageBox.warning(self, "Erro", "Informe Projeto e Tarefa.")
            return

        try:
            novo = self._svc.inserir_apontamento(
                apt_referencia=self._apt,
                posicao=self._posicao(),
                projeto=projeto,
                tarefa=tarefa,
                horario=horario,
                nota=self._campo_nota.text().strip(),
            )
            logger.info(f"Adicionado id={novo.id} ({self._posicao()} de id={self._apt.id})")
            self.accept()
        except (HorarioInvalidoError, SobreposicaoError, ApontamentoError, ValueError) as e:
            QMessageBox.warning(self, "Erro", str(e))
