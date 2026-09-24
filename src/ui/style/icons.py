"""
icons.py — Ícones SVG (como strings) usados via QIcon nos botões de ação da UI.

Não confundir com assets/icons/: aqueles são arquivos carregados por caminho
no QSS (seta de combobox, checkmark), um mecanismo totalmente separado deste.

Uso:
    from src.ui.style.icons import SVG_EDITAR
    from src.ui.ui_helpers import icone_de_svg, botao_com_icone

    btn = botao_com_icone(icone_de_svg(SVG_EDITAR), "Editar")
"""

from src.ui.style.tokens import TEXT_BRIGHT

SVG_EDITAR = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="24" height="24"
     viewBox="0 0 24 24"
     fill="none"
     stroke="{TEXT_BRIGHT}"
     stroke-width="1.8"
     stroke-linecap="round"
     stroke-linejoin="round">
    <path d="M12 20h9"/>
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/>
</svg>
"""

SVG_RELOGIO = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="24" height="24"
     viewBox="0 0 24 24"
     fill="none"
     stroke="{TEXT_BRIGHT}"
     stroke-width="1.8"
     stroke-linecap="round"
     stroke-linejoin="round">
    <circle cx="12" cy="12" r="9"/>
    <polyline points="12 7 12 12 15 14"/>
</svg>
"""

SVG_DIVIDIR = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="24" height="24"
     viewBox="0 0 24 24"
     fill="none"
     stroke="{TEXT_BRIGHT}"
     stroke-width="1.8"
     stroke-linecap="round"
     stroke-linejoin="round">
    <circle cx="6" cy="6" r="2"/>
    <circle cx="18" cy="18" r="2"/>
    <path d="M8 8l8 8"/>
    <path d="M16 8l-4 4"/>
    <path d="M12 12l-4 4"/>
</svg>
"""

SVG_ADICIONAR = f"""
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="{TEXT_BRIGHT}"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/>
        <line x1="12" y1="8" x2="12" y2="16"/>
        <line x1="8" y1="12" x2="16" y2="12"/>
    </svg>
    """

SVG_LIXEIRA = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="24" height="24"
     viewBox="0 0 24 24"
     fill="none"
     stroke="{TEXT_BRIGHT}"
     stroke-width="1.8"
     stroke-linecap="round"
     stroke-linejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v5"/>
    <path d="M14 11v5"/>
    <path d="M9 6V4h6v2"/>
</svg>
"""
