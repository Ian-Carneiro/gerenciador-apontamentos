"""
JornadaConfigDialog — Configuração de jornada e dias de exceção
(feriados, dayoffs, atestados).
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.apontamento_service import ApontamentoService
from src.db.models import DiaExcecao
from src.ui import messagebox_utils as mbox
from src.ui.ui_helpers import botao_com_icone, icone_de_svg

_DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_TIPOS_LABEL = {
    DiaExcecao.FERIADO: "Feriado",
    DiaExcecao.DAYOFF: "Dayoff",
    DiaExcecao.ATESTADO: "Atestado",
}

_SVG_HINT = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="#8a93a3" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="9"/>
    <line x1="12" y1="11" x2="12" y2="16.5"/>
    <circle cx="12" cy="7.4" r="1" fill="#8a93a3" stroke="none"/>
</svg>"""


def _label_com_hint(texto: str, tooltip: str) -> QWidget:
    """Label de formulário com um ícone de hint (ⓘ) ao lado, exibindo `tooltip` no hover."""
    from PySide6.QtGui import QPixmap

    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(QLabel(texto))

    pixmap = QPixmap()
    pixmap.loadFromData(_SVG_HINT.encode("utf-8"), "SVG")  # type: ignore[arg-type]
    lbl_icone = QLabel()
    lbl_icone.setPixmap(
        pixmap.scaled(
            14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    )
    lbl_icone.setToolTip(tooltip)
    lbl_icone.setCursor(Qt.CursorShape.WhatsThisCursor)
    lay.addWidget(lbl_icone)
    lay.addStretch()
    return container


def _ymd(d: date) -> tuple[int, int, int]:
    """Decompõe uma date em (ano, mês, dia), formato esperado por QDate(*args)."""
    return d.year, d.month, d.day


class _BotoesExcecao(QWidget):
    """Botões de editar/remover de uma linha da tabela de exceções."""

    SVG_EDITAR = """
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
         fill="none" stroke="#E8EAF0" stroke-width="1.8"
         stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 20h9"/>
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/>
    </svg>"""

    SVG_LIXEIRA = """
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
         fill="none" stroke="#E8EAF0" stroke-width="1.8"
         stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6l-1 14H6L5 6"/>
        <path d="M10 11v5"/>
        <path d="M14 11v5"/>
        <path d="M9 6V4h6v2"/>
    </svg>"""

    def __init__(self, exc: DiaExcecao, dialog: JornadaConfigDialog, parent=None):
        """Monta os botões editar/remover, ligados aos handlers de `dialog` para `exc`."""
        super().__init__(parent)
        self._exc = exc
        self._dialog = dialog

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self._btn_editar = botao_com_icone(icone_de_svg(self.SVG_EDITAR), "Editar exceção")
        self._btn_deletar = botao_com_icone(
            icone_de_svg(self.SVG_LIXEIRA), "Remover exceção", object_name="btnDel"
        )

        layout.addWidget(self._btn_editar)
        layout.addWidget(self._btn_deletar)
        layout.addStretch()

        self._btn_editar.clicked.connect(lambda: dialog._on_editar_excecao(exc))
        self._btn_deletar.clicked.connect(lambda: dialog._on_deletar_excecao(exc))


def _somar_meses(d: date, meses: int) -> date:
    """Soma `meses` a `d`, mantendo o mesmo dia (assume dia <= 28, ver validação no diálogo)."""
    mes_total = d.month - 1 + meses
    return date(d.year + mes_total // 12, mes_total % 12 + 1, d.day)


def _gerar_preview_periodos(inicio: date, meses: int, quantidade: int = 3) -> str:
    """Gera uma string com os `quantidade` primeiros períodos (início→fim) de `meses` meses cada, a partir de `inicio`."""
    partes = []
    cursor = inicio
    for _ in range(quantidade):
        fim = _somar_meses(cursor, meses) - timedelta(days=1)
        partes.append(cursor.strftime("%d/%m/%Y"))
        partes.append(fim.strftime("%d/%m/%Y"))
        cursor = fim + timedelta(days=1)
    return " → ".join(partes) + " → ..."


class JornadaConfigDialog(QDialog):
    """Configura jornada diária, período do banco de horas e a lista de dias de exceção."""

    def __init__(self, service: ApontamentoService, parent: QWidget | None = None):
        """Monta a janela e carrega a config e as exceções atuais."""
        super().__init__(parent)
        self._svc = service
        self.setWindowTitle("Configurar Jornada de Trabalho")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._carregar_config()
        self._carregar_excecoes()

    def _build_ui(self):
        """Monta o form de jornada/banco de horas, os checkboxes de dias úteis e a tabela de exceções."""
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._spin_jornada = QDoubleSpinBox()
        self._spin_jornada.setRange(1.0, 24.0)
        self._spin_jornada.setSingleStep(0.5)
        self._spin_jornada.setSuffix(" h/dia")
        form.addRow("Jornada por dia:", self._spin_jornada)

        self._spin_meses = QSpinBox()
        self._spin_meses.setRange(1, 24)
        self._spin_meses.setSuffix(" meses")
        form.addRow("Duração do período:", self._spin_meses)
        self._spin_meses.valueChanged.connect(self._atualizar_preview_periodos)

        self._inicio_periodo = QDateEdit(QDate.currentDate())
        self._inicio_periodo.setCalendarPopup(True)
        self._inicio_periodo.setDisplayFormat("dd/MM/yyyy")
        tooltip_ancora = (
            "Qualquer data de início de período já conhecido — os demais são calculados "
            "automaticamente a partir dela"
        )
        self._inicio_periodo.setToolTip(tooltip_ancora)
        self._inicio_periodo.dateChanged.connect(self._atualizar_preview_periodos)
        form.addRow(
            _label_com_hint("Data-âncora do banco de horas:", tooltip_ancora), self._inicio_periodo
        )

        layout.addLayout(form)

        self._lbl_preview_periodos = QLabel()
        self._lbl_preview_periodos.setWordWrap(True)
        self._lbl_preview_periodos.setStyleSheet("color: #8a93a3; font-size: 12px;")
        layout.addWidget(self._lbl_preview_periodos)

        layout.addWidget(QLabel("Dias considerados na jornada:"))
        linha_dias = QHBoxLayout()
        self._checks_dias: list[QCheckBox] = []
        for label in _DIAS_SEMANA:
            chk = QCheckBox(label)
            self._checks_dias.append(chk)
            linha_dias.addWidget(chk)
        layout.addLayout(linha_dias)
        layout.addSpacing(8)

        linha_titulo = QHBoxLayout()
        linha_titulo.addWidget(QLabel("Dias de Exceção"))
        linha_titulo.addStretch()
        btn_add = QPushButton("+ Adicionar")
        btn_add.clicked.connect(self._on_adicionar_excecao)
        linha_titulo.addWidget(btn_add)
        layout.addLayout(linha_titulo)

        self._tabela = QTableWidget(0, 5)
        self._tabela.setHorizontalHeaderLabels(["Data", "Tipo", "Horas", "Obs.", ""])
        self._tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._tabela, stretch=1)

        linha_btns = QHBoxLayout()
        linha_btns.addStretch()
        btn_salvar = QPushButton("✓ Salvar")
        btn_salvar.setObjectName("btnConfirmar")
        btn_salvar.clicked.connect(self._on_salvar)
        btn_cancelar = QPushButton("✗ Cancelar")
        btn_cancelar.setObjectName("btnSecundario")
        btn_cancelar.clicked.connect(self.reject)
        linha_btns.addWidget(btn_salvar)
        linha_btns.addWidget(btn_cancelar)
        layout.addLayout(linha_btns)

    def _atualizar_preview_periodos(self):
        """Recalcula e exibe o preview de períodos; exige dia-âncora entre 1 e 28."""
        qd = self._inicio_periodo.date()
        if qd.day() > 28:
            self._lbl_preview_periodos.setText(
                "⚠️ Escolha um dia entre 1 e 28 (evita cair em meses sem esse dia)."
            )
            return
        inicio = date(qd.year(), qd.month(), qd.day())
        texto = _gerar_preview_periodos(inicio, self._spin_meses.value())
        self._lbl_preview_periodos.setText(f"Períodos gerados: {texto}")

    def _carregar_config(self):
        """Preenche os campos do form com a config de jornada atual."""
        cfg = self._svc.obter_config_jornada()
        self._spin_jornada.setValue(cfg.jornada_horas_dia)
        self._spin_meses.setValue(cfg.banco_horas_meses)
        self._inicio_periodo.setDate(QDate(*_ymd(cfg.banco_horas_ancora)))
        for i, chk in enumerate(self._checks_dias):
            chk.setChecked(i in cfg.dias_trabalho)
        self._atualizar_preview_periodos()

    def _carregar_excecoes(self):
        """Recarrega a lista de exceções do service e repopula a tabela (itens + botões de ação)."""
        self._excecoes = self._svc.listar_excecoes()
        self._tabela.setRowCount(0)
        self._tabela.setRowCount(len(self._excecoes))

        # 1ª passagem: apenas setItem
        for row, exc in enumerate(self._excecoes):
            data_txt = (
                exc.data.strftime("%d/%m") + " 🔁"
                if exc.recorrente
                else exc.data.strftime("%d/%m/%Y")
            )
            horas_txt = "inteiro" if exc.dia_inteiro else f"{exc.horas_abonadas:.1f}h"
            self._tabela.setItem(row, 0, QTableWidgetItem(data_txt))
            self._tabela.setItem(row, 1, QTableWidgetItem(_TIPOS_LABEL.get(exc.tipo, exc.tipo)))
            self._tabela.setItem(row, 2, QTableWidgetItem(horas_txt))
            self._tabela.setItem(row, 3, QTableWidgetItem(exc.observacao))

        # 2ª passagem: setCellWidget
        for row, exc in enumerate(self._excecoes):
            self._tabela.setCellWidget(row, 4, _BotoesExcecao(exc, self))

    def _on_adicionar_excecao(self):
        """Abre _ExcecaoDialog em branco; se confirmado, cria a exceção e recarrega a tabela."""
        dados = _ExcecaoDialog(parent=self).pedir()
        if not dados:
            return
        try:
            self._svc.criar_excecao(**dados)
        except Exception as e:
            mbox.showerror("Erro", str(e), parent=self)
            return
        self._carregar_excecoes()

    def _on_editar_excecao(self, exc: DiaExcecao):
        """Abre _ExcecaoDialog pré-preenchido com `exc`; se confirmado, atualiza e recarrega a tabela."""
        dados = _ExcecaoDialog(parent=self, excecao=exc).pedir()
        if not dados:
            return
        try:
            self._svc.atualizar_excecao(exc.id, **dados)
        except Exception as e:
            mbox.showerror("Erro", str(e), parent=self)
            return
        self._carregar_excecoes()

    def _on_deletar_excecao(self, exc: DiaExcecao):
        """Pede confirmação e, se aceito, remove `exc` e recarrega a tabela."""
        if not mbox.askyesno(
            "Confirmar", f"Remover a exceção de {exc.data.strftime('%d/%m')}?", parent=self
        ):
            return
        self._svc.deletar_excecao(exc.id)
        self._carregar_excecoes()

    def _on_salvar(self):
        """Valida dias de trabalho e dia-âncora, e salva a config de jornada."""
        dias = [i for i, chk in enumerate(self._checks_dias) if chk.isChecked()]
        if not dias:
            mbox.showerror("Erro", "Selecione ao menos um dia de trabalho.", parent=self)
            return

        qd = self._inicio_periodo.date()
        if qd.day() > 28:
            mbox.showerror(
                "Erro", "Escolha um dia entre 1 e 28 para o início do período.", parent=self
            )
            return

        self._svc.salvar_config_jornada(
            jornada_horas_dia=self._spin_jornada.value(),
            banco_horas_meses=self._spin_meses.value(),
            banco_horas_ancora=date(qd.year(), qd.month(), qd.day()),
            dias_trabalho=dias,
        )
        self.accept()


# ── Sub-diálogo: Adicionar/Editar Exceção ─────────────────────────────────────


class _ExcecaoDialog(QDialog):
    """Formulário modal para criar/editar uma exceção; pedir() bloqueia e retorna o dict de dados ou None."""

    def __init__(self, parent: QWidget | None = None, excecao: DiaExcecao | None = None):
        """Monta o formulário; se `excecao` for passada, pré-preenche os campos (modo edição)."""
        super().__init__(parent)
        self.setWindowTitle("Exceção" if excecao is None else "Editar Exceção")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._resultado: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._combo_tipo = QComboBox()
        for valor, label in _TIPOS_LABEL.items():
            self._combo_tipo.addItem(label, valor)
        self._combo_tipo.currentIndexChanged.connect(self._on_tipo_changed)
        form.addRow("Tipo:", self._combo_tipo)

        self._chk_recorrente = QCheckBox("Repete todo ano (feriado fixo)")
        form.addRow("", self._chk_recorrente)

        self._data = QDateEdit(QDate.currentDate())
        self._data.setCalendarPopup(True)
        self._data.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Data:", self._data)

        self._chk_dia_inteiro = QCheckBox("Dia inteiro abonado")
        self._chk_dia_inteiro.setChecked(True)
        self._chk_dia_inteiro.toggled.connect(
            lambda marcado: self._spin_horas.setEnabled(not marcado)
        )
        form.addRow("", self._chk_dia_inteiro)

        self._spin_horas = QDoubleSpinBox()
        self._spin_horas.setRange(0.5, 24.0)
        self._spin_horas.setSingleStep(0.5)
        self._spin_horas.setEnabled(False)
        form.addRow("Horas abonadas:", self._spin_horas)

        self._obs = QLineEdit()
        form.addRow("Observação:", self._obs)
        layout.addLayout(form)

        self._on_tipo_changed()

        if excecao is not None:
            self._preencher(excecao)

        row = QHBoxLayout()
        row.addStretch()
        btn_ok = QPushButton("✓ Confirmar")
        btn_ok.clicked.connect(self._on_confirmar)
        btn_cancel = QPushButton("✗ Cancelar")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

    def _on_tipo_changed(self):
        """
        Só ATESTADO permite dia parcial e não-recorrente: para os demais tipos
        (Feriado/Dayoff), força e trava tanto "dia inteiro" quanto "recorrente" em True.
        """
        permite_parcial = self._combo_tipo.currentData() == DiaExcecao.ATESTADO

        self._chk_dia_inteiro.setEnabled(permite_parcial)
        if not permite_parcial:
            self._chk_dia_inteiro.setChecked(True)

        self._chk_recorrente.setEnabled(permite_parcial)
        if not permite_parcial:
            self._chk_recorrente.setChecked(True)

    def _preencher(self, exc: DiaExcecao):
        """Preenche o formulário com os dados de `exc` (modo edição)."""
        idx = self._combo_tipo.findData(exc.tipo)
        if idx >= 0:
            self._combo_tipo.setCurrentIndex(idx)
        self._chk_recorrente.setChecked(exc.recorrente)
        self._data.setDate(QDate(*_ymd(exc.data)))
        self._chk_dia_inteiro.setChecked(exc.dia_inteiro)
        if not exc.dia_inteiro:
            self._spin_horas.setValue(exc.horas_abonadas)
        self._obs.setText(exc.observacao)

    def _on_confirmar(self):
        """Valida a data (ano fixo 2000 se recorrente) e monta self._resultado antes de fechar."""
        qd = self._data.date()
        recorrente = self._chk_recorrente.isChecked()
        ano = 2000 if recorrente else qd.year()
        try:
            data_val = date(ano, qd.month(), qd.day())
        except ValueError as e:
            mbox.showerror("Erro", f"Data inválida: {e}", parent=self)
            return

        self._resultado = {
            "tipo": self._combo_tipo.currentData(),
            "recorrente": recorrente,
            "data": data_val,
            "horas_abonadas": None
            if self._chk_dia_inteiro.isChecked()
            else self._spin_horas.value(),
            "observacao": self._obs.text().strip(),
        }
        self.accept()

    def pedir(self) -> dict | None:
        """Executa o diálogo modal e retorna o dict de dados confirmado, ou None se cancelado."""
        self.exec()
        return self._resultado
