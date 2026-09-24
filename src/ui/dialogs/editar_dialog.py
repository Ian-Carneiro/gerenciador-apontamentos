"""
EditarDialog — Edita projeto, tarefa e nota de um apontamento.

┌--------------------------------------------─┐
│  Editar Apontamento                     │
│                                             │
│  PROJETO  [▼ FilterableComboBox        ]    │
│  TAREFA   [▼ FilterableComboBox        ]    │
│  NOTA     [TextEdit                    ]    │
│                                             │
│  [ ✓ Salvar ]          [ ✗ Cancelar ]       │
└--------------------------------------------─┘
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from src.core.apontamento_service import ApontamentoService
from src.db.models import Apontamento
from src.db.repository import ApontamentoError
from src.ui import messagebox_utils as mbox
from src.ui.style.tokens import TEXT_BRIGHT, TEXT_DIM
from src.ui.ui_helpers import campo_caption
from src.ui.widgets.filterable_combo import FilterableComboBox
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EditarDialog(QDialog):
    """
    Edita projeto, tarefa e nota de um apontamento existente.
    Retorna QDialog.Accepted se o usuário salvou, Rejected se cancelou.
    """

    def __init__(
        self,
        apontamento: Apontamento,
        service: ApontamentoService,
        parent=None,
    ):
        """Monta o diálogo e já preenche os campos com os dados atuais do apontamento."""
        super().__init__(parent)
        self._apt = apontamento
        self._svc = service

        self.setWindowTitle("Editar Apontamento")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._build_ui()
        self._popular_dados()

    # -- Build ----------------------------------------------------------------─

    def _build_ui(self):
        """Monta cabeçalho, info do intervalo (leitura), combos projeto/tarefa e nota."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Cabeçalho
        lbl_titulo = QLabel("Editar Apontamento")
        lbl_titulo.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_BRIGHT};")
        layout.addWidget(lbl_titulo)

        # Info do intervalo (somente leitura)
        inicio_str = self._apt.inicio.strftime("%d/%m/%Y  %H:%M:%S")
        fim_str = self._apt.fim.strftime("%H:%M:%S") if self._apt.fim else "em execução"
        lbl_info = QLabel(f"{inicio_str}  ->  {fim_str}  ({self._apt.duracao_str})")
        lbl_info.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        layout.addWidget(lbl_info)

        layout.addSpacing(4)

        # Projeto
        layout.addWidget(campo_caption("PROJETO"))
        dados_pt = self._svc._projetos_tarefas_como_dicts()
        projetos = sorted({d["projeto"] for d in dados_pt})

        self._combo_projeto = FilterableComboBox(placeholder="Selecionar projeto...")
        self._combo_projeto.set_dados(projetos)
        layout.addWidget(self._combo_projeto)

        # Tarefa
        layout.addWidget(campo_caption("TAREFA"))
        self._combo_tarefa = FilterableComboBox(placeholder="Selecionar tarefa...")
        self._combo_tarefa.set_dados_por_pai(
            dados=dados_pt,
            campo_proprio="tarefa",
            campo_pai="projeto",
            combo_pai=self._combo_projeto,
        )
        layout.addWidget(self._combo_tarefa)

        # Nota
        layout.addWidget(campo_caption("NOTA"))
        self._nota = QTextEdit()
        self._nota.setObjectName("textEditNota")
        self._nota.setFixedHeight(70)
        layout.addWidget(self._nota)

        layout.addSpacing(8)

        # Botões
        btns = QDialogButtonBox()
        self._btn_salvar = btns.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_cancelar = btns.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self._btn_salvar.setObjectName("btnIniciar")
        self._btn_cancelar.setObjectName("btnSecundario")
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _popular_dados(self):
        """Preenche os campos com os dados atuais do apontamento."""
        self._combo_projeto.set_valor(self._apt.projeto)
        self._combo_projeto.valor_selecionado.emit(self._apt.projeto)
        self._combo_tarefa.set_valor(self._apt.tarefa)
        self._nota.setPlainText(self._apt.nota)

    # -- Salvar ----------------------------------------------------------------

    def _salvar(self):
        """Valida projeto/tarefa e salva projeto/tarefa/nota alterados; fecha o diálogo em sucesso."""
        projeto = self._combo_projeto.valor_atual()
        tarefa = self._combo_tarefa.valor_atual()
        nota = self._nota.toPlainText().strip()

        if not projeto:
            self._erro("Selecione um projeto.")
            return
        if not tarefa:
            self._erro("Selecione uma tarefa.")
            return

        try:
            self._svc.atualizar_projeto_tarefa(self._apt.id, projeto, tarefa)
            if nota != self._apt.nota:
                self._svc.atualizar_nota(self._apt.id, nota)
            logger.info(f"Apontamento {self._apt.id} editado")
            self.accept()
        except ApontamentoError as e:
            self._erro(str(e))

    def _erro(self, msg: str):
        """Exibe `msg` num QMessageBox de aviso."""
        mbox.showwarning("Erro", msg, parent=self)
