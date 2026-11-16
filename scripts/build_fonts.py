"""Ferramenta de desenvolvimento (não roda no build): gera assets/fonts/*.woff2 enxutos para o painel.

Subconjunto latino (cobre o português) das variáveis Inter, Space Grotesk e JetBrains Mono, em WOFF2, para
o painel offline embutir as fontes do Nevora sem passar de ~250 KB. Requer: pip install fonttools brotli.
Os .ttf completos (usados pela janela Tk) ficam em assets/fonts/ e são licenciados sob a SIL OFL 1.1.
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
UNICODES = "U+0000-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2013-2014,U+2018-201E,U+2022,U+2026,U+20AC,U+2122,U+2191,U+2193,U+2212"


def build(name: str) -> None:
    src = FONTS / f"{name}.ttf"
    font = TTFont(src)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.unicodes = subset.parse_unicodes(UNICODES)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=opts.unicodes)
    sub.subset(font)
    out = FONTS / f"{name}.woff2"
    font.flavor = "woff2"
    font.save(out)
    print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build("Inter")
    build("SpaceGrotesk")
    build("JetBrainsMono")
