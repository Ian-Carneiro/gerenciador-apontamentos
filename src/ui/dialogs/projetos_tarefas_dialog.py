"""Diálogo de edição de Projetos/Tarefas - corrige typos de entrada manual"""

from functools import lru_cache
import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.repository import ApontamentoRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)

COL_PROJETO, COL_TAREFA, COL_ATIVO = range(3)


@lru_cache(maxsize=1024)
def _normalizar(texto: str) -> str:
    """Remove acentos e converte para minúscula (com cache)"""
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


class ProjetosTarefasDialog(QDialog):
    """Permite corrigir typos de projeto/tarefa direto na base (SQLite)"""

    def __init__(self, repo: ApontamentoRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Editar Projetos / Tarefas")
        self.resize(700, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Duplo clique para editar. A correção é aplicada em todos os\n"
                "apontamentos já lançados com esse par (histórico incluído)."
            )
        )

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("🔍 Filtrar por projeto ou tarefa...")
        self.campo_busca.textChanged.connect(self._filtrar)
        layout.addWidget(self.campo_busca)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Projeto", "Tarefa", "Ativo"])
        self.tabela.horizontalHeader().setSectionResizeMode(
            COL_PROJETO, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            COL_TAREFA, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.tabela)

        botoes = QHBoxLayout()
        btn_excluir = QPushButton("🗑 Excluir Selecionada")
        btn_excluir.clicked.connect(self._excluir_selecionada)
        botoes.addWidget(btn_excluir)
        botoes.addStretch()

        btn_salvar = QPushButton("💾 Salvar Alterações")
        btn_salvar.setStyleSheet(
            "background:#4CAF50; color:white; font-weight:700; padding:6px 16px;"
        )
        btn_salvar.clicked.connect(self._salvar)
        botoes.addWidget(btn_salvar)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.reject)
        botoes.addWidget(btn_fechar)

        layout.addLayout(botoes)
        self._carregar()

    def _carregar(self):
        registros = self.repo.listar_projetos_tarefas(apenas_ativos=False)
        self.tabela.setRowCount(len(registros))

        for row, pt in enumerate(registros):
            item_projeto = QTableWidgetItem(pt.projeto)
            item_projeto.setData(Qt.ItemDataRole.UserRole, (pt.projeto, pt.tarefa))
            item_tarefa = QTableWidgetItem(pt.tarefa)

            item_ativo = QTableWidgetItem()
            item_ativo.setFlags(item_ativo.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item_ativo.setCheckState(Qt.CheckState.Checked if pt.ativo else Qt.CheckState.Unchecked)

            self.tabela.setItem(row, COL_PROJETO, item_projeto)
            self.tabela.setItem(row, COL_TAREFA, item_tarefa)
            self.tabela.setItem(row, COL_ATIVO, item_ativo)

    def _filtrar(self, texto: str):
        texto = _normalizar(texto.strip())
        for row in range(self.tabela.rowCount()):
            if not texto:
                self.tabela.setRowHidden(row, False)
                continue
            projeto = _normalizar(self.tabela.item(row, COL_PROJETO).text())
            tarefa = _normalizar(self.tabela.item(row, COL_TAREFA).text())
            self.tabela.setRowHidden(row, texto not in projeto and texto not in tarefa)

    def _excluir_selecionada(self):
        row = self.tabela.currentRow()
        if row < 0:
            return

        projeto = self.tabela.item(row, COL_PROJETO).text()
        tarefa = self.tabela.item(row, COL_TAREFA).text()

        resposta = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"Remover '{projeto} / {tarefa}' da lista de sugestões?\n\n"
            "Apontamentos já lançados com esse par NÃO serão apagados.",
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return

        self.repo.deletar_projeto_tarefa(projeto, tarefa)
        self.tabela.removeRow(row)

    def _salvar(self):
        alteracoes = 0

        for row in range(self.tabela.rowCount()):
            item_projeto = self.tabela.item(row, COL_PROJETO)
            item_tarefa = self.tabela.item(row, COL_TAREFA)
            item_ativo = self.tabela.item(row, COL_ATIVO)

            projeto_original, tarefa_original = item_projeto.data(Qt.ItemDataRole.UserRole)
            projeto_novo = item_projeto.text().strip()
            tarefa_novo = item_tarefa.text().strip()
            ativo_novo = item_ativo.checkState() == Qt.CheckState.Checked

            if not projeto_novo or not tarefa_novo:
                continue

            if (projeto_novo, tarefa_novo) != (projeto_original, tarefa_original):
                afetados = self.repo.renomear_projeto_tarefa(
                    projeto_original, tarefa_original, projeto_novo, tarefa_novo
                )
                item_projeto.setData(Qt.ItemDataRole.UserRole, (projeto_novo, tarefa_novo))
                alteracoes += 1
                logger.info(
                    f"✏️ '{projeto_original}/{tarefa_original}' → "
                    f"'{projeto_novo}/{tarefa_novo}' ({afetados} apontamentos)"
                )

            self.repo.atualizar_ativo_projeto_tarefa(projeto_novo, tarefa_novo, ativo_novo)

        QMessageBox.information(self, "Concluído", f"{alteracoes} par(es) corrigido(s).")
        self.accept()
