"""Diálogo de mesclagem/ajuste de apontamentos locais + Mikael"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

from src.automacao.mesclar_apontamentos import (
    AjusteGap,
    Intervalo,
    aplicar_ajustes,
    calcular_ajustes,
    construir_intervalos_locais,
    construir_intervalos_mikael,
    mesclar,
)
from src.automacao.mikael_automacao import obter_apontamentos_mikael
from src.utils.logger import get_logger

logger = get_logger(__name__)

_FMT = "%H:%M:%S"


class MesclarApontamentosDialog(QDialog):
    """
    Exibe apontamentos locais + Mikael mesclados, com checkboxes
    para cada gap, permitindo ao usuário decidir quais ajustar.

    Após confirmar, salva as alterações no banco via `repo`.
    """

    def __init__(
        self,
        apontamentos_db: list,
        data_str: str,
        repo,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Mesclar / Ajustar Apontamentos")
        self.resize(900, 560)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._repo = repo
        self._data_str = data_str
        self._apontamentos_db = apontamentos_db

        self._intervalos: list[Intervalo] = []
        self._ajustes: list[AjusteGap] = []
        self._checkboxes: list[QCheckBox] = []

        self._build_ui()
        self._carregar()

    # -- UI --------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        titulo = QLabel(f"📋 Mesclagem de apontamentos — {self._data_str}")
        titulo.setObjectName("labelAppTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        layout.addWidget(QLabel("Apontamentos após mesclagem com Mikael:"))

        self._tabela = QTableWidget()
        self._tabela.setColumnCount(6)
        self._tabela.setHorizontalHeaderLabels(
            ["Origem", "Início", "Fim", "Projeto", "Tarefa", "Ajustar"]
        )
        self._tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._tabela)

        layout.addWidget(
            QLabel(
                'Marque "Ajustar" para fechar o gap automaticamente (passe o mouse para ver detalhes).'
            )
        )

        # Botões
        row = QHBoxLayout()
        row.addStretch()

        btn_aplicar = QPushButton("✓ Aplicar ajustes")
        btn_aplicar.setObjectName("btnConfirmar")
        btn_aplicar.clicked.connect(self._on_aplicar)
        row.addWidget(btn_aplicar)

        btn_cancelar = QPushButton("✗ Cancelar")
        btn_cancelar.setObjectName("btnSecundario")
        btn_cancelar.clicked.connect(self.reject)
        row.addWidget(btn_cancelar)

        row.addStretch()
        layout.addLayout(row)

    # -- Lógica ----------------------------------------------------------------

    def _carregar(self):
        locais = construir_intervalos_locais(self._apontamentos_db)

        logger.info("🔄 Baixando apontamentos do Mikael...")
        mikael_raw = obter_apontamentos_mikael(self._data_str)
        mikael = construir_intervalos_mikael(mikael_raw)

        self._intervalos = mesclar(locais, mikael)
        self._ajustes = calcular_ajustes(self._intervalos, self._apontamentos_db)

        self._preencher_tabela(self._intervalos)
        self._preencher_checkboxes()
        self._atualizar_preview()

    def _preencher_tabela(self, intervalos: list[Intervalo] | None = None):
        intervalos = self._intervalos if intervalos is None else intervalos
        self._tabela.setRowCount(len(intervalos))
        for row, iv in enumerate(intervalos):
            self._tabela.setItem(row, 0, QTableWidgetItem(iv.origem.capitalize()))
            self._tabela.setItem(row, 1, QTableWidgetItem(iv.inicio.strftime(_FMT)))
            self._tabela.setItem(row, 2, QTableWidgetItem(iv.fim.strftime(_FMT)))
            self._tabela.setItem(row, 3, QTableWidgetItem(iv.projeto))
            self._tabela.setItem(row, 4, QTableWidgetItem(iv.tarefa))

    def _atualizar_preview(self):
        """Recalcula a tabela aplicando os ajustes marcados, sem alterar os dados originais."""
        copia = [replace(iv) for iv in self._intervalos]
        aplicar_ajustes(copia, self._ajustes)
        self._preencher_tabela(copia)

    def _preencher_checkboxes(self):
        """Coloca um checkbox na linha que efetivamente muda de valor ao fechar cada gap."""
        ajustes_por_linha: dict[int, list[AjusteGap]] = {}
        for aj in self._ajustes:
            # Mikael nunca muda: a linha afetada é sempre a do lado "local".
            row = (
                aj.idx_anterior
                if self._intervalos[aj.idx_proximo].origem == "mikael"
                else aj.idx_proximo
            )
            ajustes_por_linha.setdefault(row, []).append(aj)

        for row, ajustes_linha in ajustes_por_linha.items():
            cell = QWidget()
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(2, 0, 2, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for aj in ajustes_linha:
                chk = QCheckBox()
                chk.setChecked(aj.aplicar)
                chk.setToolTip(aj.descricao)
                chk.toggled.connect(lambda checked, a=aj: self._on_gap_toggled(a, checked))
                lay.addWidget(chk)
            self._tabela.setCellWidget(row, 5, cell)

    def _preencher_gaps(self):
        while self._gaps_layout.count():
            item = self._gaps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()

        if not self._ajustes:
            self._lbl_gaps.setText("✅ Sem gaps detectados entre os apontamentos.")
            return

        self._lbl_gaps.setText("Gaps detectados (marque para fechar automaticamente):")
        for aj in self._ajustes:
            chk = QCheckBox(aj.descricao)
            chk.setChecked(aj.aplicar)  # já calculado corretamente em calcular_ajustes
            chk.toggled.connect(lambda checked, a=aj: self._on_gap_toggled(a, checked))
            self._gaps_layout.addWidget(chk)
            self._checkboxes.append(chk)

    def _on_gap_toggled(self, ajuste: AjusteGap, checked: bool):
        ajuste.aplicar = checked
        self._atualizar_preview()

    def _ja_registrado(self, inicio_dt: datetime, fim_dt: datetime) -> bool:
        """Evita duplicar um intervalo do Mikael já gravado em uma aplicação anterior."""
        return any(
            apt.projeto == "Mikael Apontamentos" and apt.inicio == inicio_dt and apt.fim == fim_dt
            for apt in self._apontamentos_db
        )

    def _on_aplicar(self):

        intervalos_ajustados = aplicar_ajustes(self._intervalos, self._ajustes)
        data = datetime.strptime(self._data_str, "%d/%m/%Y").date()

        for iv in intervalos_ajustados:
            # Reconstrói datetime completo com a data real
            inicio_dt = datetime.combine(data, iv.inicio.time())
            fim_dt = datetime.combine(data, iv.fim.time())

            if iv.origem == "local" and iv.id_local:
                apt_original = next((a for a in self._apontamentos_db if a.id == iv.id_local), None)
                if apt_original:
                    if inicio_dt != apt_original.inicio:
                        self._repo.ajustar_inicio(iv.id_local, inicio_dt, ignorar_sobreposicao=True)
                    if fim_dt != apt_original.fim:
                        self._repo.ajustar_fim(iv.id_local, fim_dt, ignorar_sobreposicao=True)

            elif iv.origem == "mikael":
                if self._ja_registrado(inicio_dt, fim_dt):
                    continue

                self._repo.registrar_retroativo(
                    projeto=iv.projeto,
                    tarefa=iv.tarefa,
                    inicio=inicio_dt,
                    fim=fim_dt,
                    nota=iv.nota or "",
                    ignorar_sobreposicao=True,
                )

        logger.info("✅ Ajustes aplicados no banco")
        self.accept()
