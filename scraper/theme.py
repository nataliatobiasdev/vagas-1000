"""Tokens do design system Nevora (tema escuro) para a janela Tk do vagas1000.

Fonte da verdade: arquivo Figma Make "Nevora Design System Showcase". Os mesmos valores estão em
scraper/templates/dashboard.html (variáveis CSS) e em docs/.vitepress/theme/custom.css.
Aqui não há nada de Tk: só cores, fontes e duas funções de cor, para poder testar sem display.
"""
from __future__ import annotations

# Neutros (≈85% da interface)
BG = "#0B0E19"          # Background
PANEL = "#151A2B"       # Surface: cards e painéis
SUBTLE = "#1C2238"      # Hover / fundo secundário
FIELD = "#0E121E"       # Inputs e área de log
BORDER = "#2C3142"      # rgba(255,255,255,.12) sobre Surface
FG = "#F4F6FF"          # Text Primary
MUTED = "#A6B1CB"       # Text Secondary
MUTED_2 = "#7D87A3"     # Texto desabilitado
# Marca (≈10% violeta, ≈5% teal)
ACCENT = "#9D8CFF"      # Primary Violet
ACCENT_FG = "#0B0E19"   # texto sobre o violeta
TEAL = "#42D6CD"        # Secondary Teal
# Semânticas
SUCCESS = "#45D6A0"
WARNING = "#F5C66B"
DANGER = "#FF718D"

# Raios (px): inputs/botões 8, cards 12, painéis 16, destaques 24
RADIUS = {"md": 8, "lg": 12, "xl": 16, "2xl": 24}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(v))) for v in (r, g, b)))


def tint(color: str, alpha: float, base: str = PANEL) -> str:
    """`color` com opacidade `alpha` sobre `base` (Tk não tem rgba)."""
    c, b = _rgb(color), _rgb(base)
    return _hex(*(b[i] + (c[i] - b[i]) * alpha for i in range(3)))


def gradient(a: str, b: str, steps: int) -> list[str]:
    """`steps` cores de `a` até `b` (usado na barra de progresso, o único gradiente da interface)."""
    ca, cb = _rgb(a), _rgb(b)
    n = max(steps - 1, 1)
    return [_hex(*(ca[i] + (cb[i] - ca[i]) * k / n for i in range(3))) for k in range(steps)]


# Fontes empacotadas em assets/fonts (carregadas por app.load_fonts); sem elas o Tk usa a substituta.
def FONT_BODY(size: int = 10):
    return ("Inter", size)


def FONT_BODY_SB(size: int = 10):
    return ("Inter SemiBold", size)


def FONT_HEAD(size: int = 14):
    return ("Space Grotesk Medium", size)


def FONT_MONO(size: int = 9):
    return ("JetBrains Mono", size)
