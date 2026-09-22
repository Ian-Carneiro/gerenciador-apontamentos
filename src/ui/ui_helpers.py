"""Utilitários de UI - PySide6"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget
from screeninfo import get_monitors


def centralizar_janela(widget: QWidget, largura: int | None = None, altura: int | None = None):
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
    return texto[: max_length - 3] + "..."


def campo_caption(texto: str) -> QLabel:
    """Cria um QLabel estilizado como legenda de campo (objectName 'labelFieldCaption')."""
    lbl = QLabel(texto)
    lbl.setObjectName("labelFieldCaption")
    return lbl


def linha_botoes_confirmar_cancelar(on_confirmar, on_cancelar) -> QHBoxLayout:
    """Monta uma linha centralizada com botões Confirmar/Cancelar (objectNames btnConfirmar/btnSecundario)."""
    row = QHBoxLayout()
    row.addStretch()

    btn_ok = QPushButton("✓ Confirmar")
    btn_ok.setObjectName("btnConfirmar")
    btn_ok.clicked.connect(on_confirmar)

    btn_cancel = QPushButton("✗ Cancelar")
    btn_cancel.setObjectName("btnSecundario")
    btn_cancel.clicked.connect(on_cancelar)

    row.addWidget(btn_ok)
    row.addWidget(btn_cancel)
    row.addStretch()
    return row


def icone_de_svg(svg: str) -> QIcon:
    """Cria um QIcon a partir de uma string SVG; levanta ValueError se o SVG for inválido."""
    pixmap = QPixmap()
    if not pixmap.loadFromData(svg.encode("utf-8"), "SVG"):
        raise ValueError("Não foi possível carregar o SVG do ícone.")
    return QIcon(pixmap)


def botao_com_icone(icon: QIcon, tooltip: str, object_name: str = "btnAcao") -> QPushButton:
    """Cria um botão de ação pequeno (32x28) com ícone e tooltip, sem foco de teclado por clique."""
    b = QPushButton()
    b.setObjectName(object_name)
    b.setIcon(icon)
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tooltip)
    b.setFixedSize(QSize(32, 28))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b
