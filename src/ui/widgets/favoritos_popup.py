# -*- coding: utf-8 -*-
"""
FavoritosPopup — popup de seleção rápida de favoritos.

Exibe lista de pares (projeto, tarefa) mais usados recentemente.
Emite `favorito_escolhido(projeto, tarefa)` ao clicar num item.

Uso:
    popup = FavoritosPopup(parent, favoritos)
    popup.favorito_escolhido.connect(handler)
    popup.abrir_em(pos_global, largura_ref)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class FavoritosPopup(QFrame):
    favorito_escolhido = Signal(str, str)  # projeto, tarefa

    _LARGURA_MIN = 420

    def __init__(self, parent: QWidget, favoritos: list):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("favPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(2)

        if not favoritos:
            v.addWidget(QLabel("Nenhum favorito ainda"))

        for fav in favoritos:
            btn = QPushButton(f"{fav.projeto}\n{fav.tarefa}")
            btn.setObjectName("favItem")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setToolTip(f"{fav.horas_str} nos últimos 7 dias")
            btn.clicked.connect(
                lambda _, p=fav.projeto, t=fav.tarefa: self.favorito_escolhido.emit(p, t)
            )
            v.addWidget(btn)

    def abrir_abaixo_de(self, widget: QWidget):
        self.setFixedWidth(max(widget.width() + 60, self._LARGURA_MIN))
        self.move(widget.mapToGlobal(widget.rect().bottomLeft()))
        self.show()

    def abrir_em(self, pos_global, largura_ref: int = 0):
        """Posiciona o popup em um ponto global (ex: abaixo de uma QAction da MenuBar)."""
        self.setFixedWidth(max(largura_ref + 60, self._LARGURA_MIN))
        self.move(pos_global)
        self.show()