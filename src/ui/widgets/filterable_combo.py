"""
FilterableComboBox — campo editável com dropdown via QFrame(Qt.Popup).

Não usa QComboBox nem QMenu — ambos capturam o teclado no Linux e
impedem digitar enquanto o dropdown está aberto.

Qt.Popup fecha ao clicar fora mas não rouba foco do QLineEdit,
permitindo continuar digitando enquanto o dropdown atualiza.

Dois níveis de filtragem:
  1. Pai→filho : _visiveis = subconjunto de _todos filtrado pelo pai
  2. Digitação : subconjunto de _visiveis que bate com o texto (sem acento)
"""

from __future__ import annotations

import unicodedata

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _norm(texto: str) -> str:
    """Remove acentos e converte para minúscula."""
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


# ── Dropdown popup ────────────────────────────────────────────────────────────


class _DropdownPopup(QFrame):
    """
    QFrame com flag Qt.Popup:
      - Aparece sobre outros widgets sem alterar a janela pai
      - Fecha automaticamente ao clicar fora
      - NÃO captura teclado — o QLineEdit continua recebendo digitação
    """

    item_selecionado = Signal(str)

    def __init__(self, parent: QWidget):
        super().__init__(
            parent,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("dropdown")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._parent_combo = parent

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # Scroll para listas longas
        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll)

        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(1)
        self._scroll.setWidget(self._container)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._largura_conteudo = 0  # maior largura de texto entre os itens

    def popular(self, itens: list[str]):
        """Reconstrói a lista de botões."""
        # Remove itens antigos
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not itens:
            lbl = QLabel("Nenhum resultado")
            lbl.setObjectName("dropVazio")
            self._vbox.addWidget(lbl)
        else:
            for valor in itens:
                btn = QPushButton(valor)
                btn.setObjectName("dropItem")
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # FocusPolicy NoFocus: clicar no botão não tira foco do lineEdit
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda _, v=valor: self.item_selecionado.emit(v))
                self._vbox.addWidget(btn)

        fm = self.fontMetrics()
        altura_item = fm.height() + 14  # 14 = padding vertical do QSS (7px topo + 7px base)
        n = min(len(itens), 8) if itens else 1
        espacamento = self._vbox.spacing() * max(n - 1, 0)
        altura_scroll = n * altura_item + espacamento + 8
        self._scroll.setFixedHeight(altura_scroll)
        margens = self.layout().contentsMargins()
        self.setFixedHeight(
            altura_scroll + margens.top() + margens.bottom() + 2
        )  # +2 = borda do QFrame (1px topo + 1px base)

        # Largura do item mais longo (+ padding horizontal do QSS + margens do popup)
        maior_texto = max((fm.horizontalAdvance(v) for v in itens), default=0)
        self._largura_conteudo = (
            maior_texto + 24 + 8 + 5
        )  # padding 12+12 + margens 4+4 + folga scrollbar

    def posicionar(self, largura: int):
        largura_final = max(largura, self._largura_conteudo, 200)
        tela = QApplication.primaryScreen().availableGeometry().width()
        largura_final = min(largura_final, int(tela * 0.6))
        self.setFixedWidth(largura_final)
        pos_global = self._parent_combo.mapToGlobal(self._parent_combo.rect().bottomLeft())
        self.move(pos_global)
        self.show()
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            dentro_popup = self.geometry().contains(pos)
            dentro_combo = self._parent_combo.rect().contains(self._parent_combo.mapFromGlobal(pos))
            if not dentro_popup and not dentro_combo:
                self.close()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)


# ── FilterableComboBox ────────────────────────────────────────────────────────


class FilterableComboBox(QWidget):
    """
    Campo editável com dropdown filtrado (QFrame Popup, sem QComboBox/QMenu).

    Signals:
        valor_selecionado(str): emitido ao confirmar seleção.
    """

    valor_selecionado = Signal(str)

    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self.setObjectName("fcbOuter")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(36)

        self._todos: list[str] = []
        self._visiveis: list[str] = []
        self._dados_por_pai: dict[str, list[str]] = {}
        self._combo_pai: FilterableComboBox | None = None
        self._popup: _DropdownPopup | None = None

        self._build_ui(placeholder)

        # Debounce: reconstrói dropdown 200ms após última tecla
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._mostrar_dropdown)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self, placeholder: str):
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._edit = QLineEdit()
        self._edit.setObjectName("fcbEdit")
        self._edit.setPlaceholderText(placeholder)
        self._edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._edit.textEdited.connect(self._ao_digitar)
        self._edit.installEventFilter(self)
        row.addWidget(self._edit, stretch=1)

        self._btn_clear = QPushButton("×")
        self._btn_clear.setObjectName("fcbClear")
        self._btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.setVisible(False)
        self._btn_clear.clicked.connect(self._ao_clicar_limpar)
        row.addWidget(self._btn_clear)

        self._btn = QPushButton("v")
        self._btn.setObjectName("fcbArrow")
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.clicked.connect(self._toggle_dropdown)
        row.addWidget(self._btn)

    # ── API pública ───────────────────────────────────────────────────────────

    def set_dados(self, itens: list[str]):
        self._todos = sorted(set(itens))
        self._visiveis = list(self._todos)

    def set_dados_por_pai(
        self,
        dados: list[dict],
        campo_proprio: str,
        campo_pai: str,
        combo_pai: FilterableComboBox,
    ):
        self._combo_pai = combo_pai
        self._dados_por_pai = {}
        todos = set()
        for d in dados:
            pv = d.get(campo_pai, "")
            tv = d.get(campo_proprio, "")
            self._dados_por_pai.setdefault(pv, []).append(tv)
            todos.add(tv)
        self._todos = sorted(todos)
        self._visiveis = list(self._todos)
        combo_pai.valor_selecionado.connect(self._ao_pai_mudar)
        self._atualizar_por_pai(combo_pai.valor_atual())

    def valor_atual(self) -> str:
        return self._edit.text().strip()

    def set_valor(self, valor: str):
        self._edit.blockSignals(True)
        self._edit.setText(valor)
        self._edit.blockSignals(False)
        self._btn_clear.setVisible(bool(valor.strip()))

    def limpar(self):
        self.set_valor("")
        self._fechar_dropdown()

    def atualizar_dados(self, dados_dicts: list[dict], campo: str):
        itens = sorted({d[campo] for d in dados_dicts if campo in d})
        self.set_dados(itens)

    def setFocus(self):
        self._edit.setFocus()

    def adicionar_valor(self, valor: str):
        if valor not in self._todos:
            self._todos.append(valor)
            self._todos.sort()
        if valor not in self._visiveis:
            self._visiveis.append(valor)
            self._visiveis.sort()

    def adicionar_par(self, pai: str, valor: str):
        if valor not in self._todos:
            self._todos.append(valor)
            self._todos.sort()
        lst = self._dados_por_pai.setdefault(pai, [])
        if valor not in lst:
            lst.append(valor)
            lst.sort()
        if self._combo_pai and self._combo_pai.valor_atual() == pai and valor not in self._visiveis:
            self._visiveis.append(valor)
            self._visiveis.sort()

    # ── Dropdown ──────────────────────────────────────────────────────────────

    def _toggle_dropdown(self):
        if self._popup and self._popup.isVisible():
            self._fechar_dropdown()
        else:
            self._mostrar_dropdown()

    def _mostrar_dropdown(self):
        texto = self._edit.text().strip()
        if texto:
            norm = _norm(texto)
            itens = [v for v in self._visiveis if norm in _norm(v)]
        else:
            itens = list(self._visiveis)

        if self._popup is None or not self._popup.isVisible():
            self._popup = _DropdownPopup(self)
            self._popup.item_selecionado.connect(self._ao_selecionar)

        self._popup.popular(itens)
        self._popup.posicionar(self.width())

    def _fechar_dropdown(self):
        if self._popup and self._popup.isVisible():
            self._popup.close()
        self._popup = None

    def _ao_selecionar(self, valor: str):
        self._fechar_dropdown()
        self.set_valor(valor)
        self.valor_selecionado.emit(valor)

    def _ao_clicar_limpar(self):
        self.set_valor("")
        self.valor_selecionado.emit("")
        self.setFocus()
        self._mostrar_dropdown()

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _ao_digitar(self, texto: str):
        self._btn_clear.setVisible(bool(texto.strip()))
        self._debounce.start()
        self.valor_selecionado.emit(texto.strip())

    def eventFilter(self, obj, event):
        """Fecha dropdown ao pressionar Escape; confirma com Enter/Tab."""
        from PySide6.QtCore import QEvent

        if obj is self._edit:
            if event.type() == QEvent.Type.MouseButtonPress and not (
                self._popup and self._popup.isVisible()
            ):
                self._mostrar_dropdown()
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape:
                    self._fechar_dropdown()
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab) and (
                    self._popup and self._popup.isVisible()
                ):
                    texto = self.valor_atual()
                    for v in self._visiveis:
                        if not texto or _norm(texto) in _norm(v):
                            self._ao_selecionar(v)
                            if key == Qt.Key.Key_Tab:
                                self.focusNextChild()
                            return True
        return super().eventFilter(obj, event)

    # ── Pai→filho ─────────────────────────────────────────────────────────────

    def _ao_pai_mudar(self, valor_pai: str):
        self._atualizar_por_pai(valor_pai)

    def _atualizar_por_pai(self, valor_pai: str):
        """Atualiza _visiveis sem tocar em _todos."""
        if valor_pai:
            self._visiveis = sorted(self._dados_por_pai.get(valor_pai, []))
            self.setEnabled(True)
        else:
            self._visiveis = []
            self.setEnabled(False)
        self.limpar()

    # ── Foco visual ───────────────────────────────────────────────────────────

    def focusInEvent(self, event):
        self.setProperty("focused", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setProperty("focused", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(event)
