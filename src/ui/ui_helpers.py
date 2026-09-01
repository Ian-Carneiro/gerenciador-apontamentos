# -*- coding: utf-8 -*-
"""Utilitários de UI - PySide6"""
from typing import Optional

from PySide6.QtWidgets import QWidget
from screeninfo import get_monitors


def centralizar_janela(widget: QWidget, largura: Optional[int] = None, altura: Optional[int] = None):
    """Centraliza widget (janela/diálogo) no monitor primário"""
    if largura is not None and altura is not None:
        widget.resize(largura, altura)

    largura = largura or widget.width()
    altura = altura or widget.height()

    try:
        monitors = get_monitors()
        monitor = next((m for m in monitors if getattr(m, "is_primary", True)), monitors[0])
        x = monitor.x + (monitor.width - largura) // 2
        y = monitor.y + (monitor.height - altura) // 2
        widget.move(x, y)
    except Exception:
        pass  # Qt já posiciona razoavelmente por padrão


def truncar_texto(texto: str, max_length: int = 50) -> str:
    """Trunca texto adicionando reticências"""
    if len(texto) <= max_length:
        return texto
    return texto[:max_length - 3] + "..."