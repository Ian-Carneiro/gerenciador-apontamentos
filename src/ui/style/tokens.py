"""
tokens.py — Paleta de cores e constantes visuais do tema.
Baseado no color scheme Mariana (Sublime HQ).

Use estas constantes em qualquer setStyleSheet() dinâmico
(mudanças de estado em runtime). Estilos estáticos vão no theme.qss.

Paleta:
  BG_BASE       #2f3840   fundo da janela        (blue3)
  BG_ALT        #242b31   linhas alt / header    (blue3 escurecido)
  BG_SURFACE    #364149   painéis / inputs       (entre blue3 e blue2)
  BG_ELEVATED   #586573   hover / seleção        (blue2)
  BG_ACTIVE     #4a5663   item ativo             (blue2 escurecido)

  ACCENT        #f8ad57   primário / caret       (orange)
  ACCENT_DIM    #d4903a   hover do acento        (orange escurecido)
  ACCENT_TEXT   #fac660   texto em acento        (orange3 / yellow)

  CYAN          #5fb3b3   headers / accent alt   (blue5 / cyan)
  BLUE          #5b98d6   accent azul-vibrante
  GREEN         #99c694   positivo               (green)
  DANGER        #ec5f66   perigo / erro          (red)
  DANGER_DIM    #c94d54   hover danger

  TEXT_PRIMARY  #d7dde8   texto principal        (white3)
  TEXT_SECONDARY #a6acb9  texto secundário       (blue6)
  TEXT_MUTED    #637281   texto desabilitado     (border / blue4)
  TEXT_BRIGHT   #e8eaf0   texto de período/horário (quase = TEXT_PRIMARY)
  TEXT_DIM      #8b90a0   texto de preview inativo
  TEXT_SUBTLE   #555a6e   label auxiliar ("atual:")
  TEXT_ON_ACCENT #ffffff  texto sobre botão de destaque (alto contraste)

  BORDER        #4a5360   bordas sutis
  BORDER_FOCUS  #5fb3b3   borda foco             (= CYAN)

  BG_INSET      #1a1d27   fundo de frame de preview (mais escuro que BG_ALT)
  BG_ROW_ALT    #1e2235   linha ímpar da tabela de histórico
  BG_TOTAL      #131620   linha de total/rodapé de tabela

  GREEN_BRIGHT  #7ec99a   duração/resultado válido (mais vivo que GREEN)
  GREEN_MUTED   #4d7c5f   acento verde escuro (tabela de histórico)
  GREEN_ACTION  #4caf50   botão de ação primária ("Salvar") — fora da
                          paleta Mariana, mantido como já estava em uso
  RED_MUTED     #c0392b   alerta/negativo em tabela (mais escuro que DANGER)

  FONT_MONO     "JetBrains Mono", "Cascadia Code", "Consolas", monospace
  FONT_SIZE     15
  FONT_SIZE_SM  13
"""

# ── Backgrounds ───────────────────────────────────────────────────────────────
BG_BASE = "#2f3840"  # blue3 — fundo da janela
BG_ALT = "#242b31"  # blue3 escurecido — header / linhas alt
BG_SURFACE = "#364149"  # entre blue3 e blue2 — painéis / cards
BG_ELEVATED = "#586573"  # blue2 — inputs / hover
BG_ACTIVE = "#4a5663"  # blue2 escurecido — item ativo / selecionado
BG_POPUP = "#2a333b"  # popup / dropdown
BG_INSET = "#1a1d27"  # fundo de frame de preview (mais escuro que BG_ALT)
BG_ROW_ALT = "#1e2235"  # linha ímpar da tabela de histórico
BG_TOTAL = "#131620"  # linha de total/rodapé de tabela

# ── Accent (laranja Mariana) ───────────────────────────────────────────────────
ACCENT = "#f8ad57"  # orange — botão primário / caret
ACCENT_DIM = "#d4903a"  # orange escurecido — hover
ACCENT_BG = "#4a3a20"  # fundo de badge com acento
ACCENT_TEXT = "#fac660"  # orange3 — texto em contexto acento

# ── Cores semânticas ──────────────────────────────────────────────────────────
CYAN = "#5fb3b3"  # blue5 — headers / accent alt / foco
BLUE = "#5b98d6"  # blue-vibrant
GREEN = "#99c694"  # green — positivo
GREEN_BRIGHT = "#7ec99a"  # duração/resultado válido — mais vivo que GREEN
GREEN_MUTED = "#4d7c5f"  # acento verde escuro — tabela de histórico
GREEN_ACTION = "#4caf50"  # botão de ação primária ("Salvar") — fora da paleta Mariana
DANGER = "#ec5f66"  # red — erro / parar
DANGER_DIM = "#c94d54"  # red escurecido — hover danger
RED_MUTED = "#c0392b"  # alerta/negativo em tabela — mais escuro que DANGER

# ── Texto ─────────────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#d7dde8"  # white3
TEXT_SECONDARY = "#a6acb9"  # blue6
TEXT_MUTED = "#637281"  # blue4
TEXT_BRIGHT = "#e8eaf0"  # texto de período/horário — quase idêntico a TEXT_PRIMARY
TEXT_DIM = "#8b90a0"  # texto de preview inativo — entre TEXT_SECONDARY e TEXT_MUTED
TEXT_SUBTLE = "#555a6e"  # label auxiliar ("atual:")
TEXT_ON_ACCENT = "#ffffff"  # texto sobre botão de destaque (alto contraste)

# ── Bordas ────────────────────────────────────────────────────────────────────
BORDER = "#4a5360"
BORDER_FOCUS = "#5fb3b3"  # = CYAN

# ── Tipografia ────────────────────────────────────────────────────────────────
FONT_MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", monospace'
FONT_SIZE = 15
FONT_SIZE_SM = 13
