"""Desenho das superfícies do Nevora para a janela Tk: cantos arredondados anti-aliasados, sombras suaves,
brilho interno de 1 px, gradientes, pílulas e ícones no traço do Lucide.

O Tk só desenha retângulos serrilhados; para ter o acabamento "macio" do CAM (que roda num navegador)
as formas são pintadas com Pillow em 4x e reduzidas. Nada aqui depende de Tk ou de display, então tudo
é testável sem janela. O app compõe cada peça sobre a cena (fundo + cartões) e entrega ao Tk uma imagem
opaca, sem depender do suporte a transparência do Tk.
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from .theme import BG, TEAL, ACCENT, _hex, _rgb

SS = 4   # fator de supersampling


def rgba(color: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = _rgb(color)
    return r, g, b, round(255 * alpha)


def _rr_mask(size: tuple[int, int], box: tuple[float, float, float, float], radius: float) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, fill=255)
    return m


def _vgradient(w: int, h: int, top: str, bottom: str) -> Image.Image:
    col = Image.new("RGB", (1, h))
    t, b = _rgb(top), _rgb(bottom)
    col.putdata([tuple(round(t[i] + (b[i] - t[i]) * y / max(h - 1, 1)) for i in range(3)) for y in range(h)])
    return col.resize((w, h))


def _dgradient(w: int, h: int, c1: str, c2: str) -> Image.Image:
    """Gradiente diagonal (canto superior esquerdo -> inferior direito), como o `bg-gradient-to-br` do CAM."""
    g = Image.linear_gradient("L").rotate(0)               # 256x256, preto em cima -> branco embaixo
    g = g.resize((w, h))
    gx = Image.linear_gradient("L").rotate(90).resize((w, h))   # esquerda -> direita
    mix = ImageChops.add(g, gx, scale=2)
    return Image.composite(Image.new("RGB", (w, h), _rgb(c2)), Image.new("RGB", (w, h), _rgb(c1)), mix)


def surface(w: int, h: int, radius: int, fill: str, border: str | None = None, *, highlight: float = 0.07,
            shadow: tuple[int, int, float] | None = None, gradient: tuple[str, str] | None = None,
            diagonal: bool = False, pad: int = 0) -> Image.Image:
    """Veja `_cached_surface`. Devolve uma cópia: quem chama pode compor ícones em cima sem sujar o cache."""
    return _cached_surface(w, h, radius, fill, border, highlight, shadow, gradient, diagonal, pad).copy()


@lru_cache(maxsize=96)
def _cached_surface(w, h, radius, fill, border, highlight, shadow, gradient, diagonal, pad) -> Image.Image:
    """Superfície acetinada: preenchimento, borda de 1 px, brilho interno no topo e sombra suave opcional.

    `shadow` = (blur, deslocamento_y, opacidade). `pad` reserva margem em volta para a sombra caber na imagem
    (o chamador posiciona a imagem em x-pad, y-pad). Devolve RGBA com cantos realmente transparentes.
    Painéis grandes sem gradiente são montados em 9 partes (cantos de uma peça pequena + faixas esticadas),
    o que é idêntico a pintar tudo e dezenas de vezes mais rápido.
    """
    if gradient is None and w * h > 40000 and pad >= 0:
        c = radius + 6 + pad
        if w > 2 * (radius + 6) + 2 and h > 2 * (radius + 6) + 2:
            return _nine_slice(w, h, radius, fill, border, highlight, shadow, pad, c)
    return _surface(w, h, radius, fill, border, highlight, shadow, gradient, diagonal, pad)


def _nine_slice(w, h, radius, fill, border, highlight, shadow, pad, c):
    m = radius + 6
    small = _surface(2 * m + 2, 2 * m + 2, radius, fill, border, highlight, shadow, None, False, pad)
    TW, TH = w + 2 * pad, h + 2 * pad
    out = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    sw, sh = small.size
    out.paste(small.crop((0, 0, c, c)), (0, 0))
    out.paste(small.crop((sw - c, 0, sw, c)), (TW - c, 0))
    out.paste(small.crop((0, sh - c, c, sh)), (0, TH - c))
    out.paste(small.crop((sw - c, sh - c, sw, sh)), (TW - c, TH - c))
    out.paste(small.crop((c, 0, c + 1, c)).resize((TW - 2 * c, c)), (c, 0))
    out.paste(small.crop((c, sh - c, c + 1, sh)).resize((TW - 2 * c, c)), (c, TH - c))
    out.paste(small.crop((0, c, c, c + 1)).resize((c, TH - 2 * c)), (0, c))
    out.paste(small.crop((sw - c, c, sw, c + 1)).resize((c, TH - 2 * c)), (TW - c, c))
    out.paste(small.crop((c, c, c + 1, c + 1)).resize((TW - 2 * c, TH - 2 * c)), (c, c))
    return out


def _surface(w, h, radius, fill, border, highlight, shadow, gradient, diagonal, pad) -> Image.Image:
    TW, TH = w + 2 * pad, h + 2 * pad
    W, H = TW * SS, TH * SS
    ox = oy = pad * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    r = radius * SS
    box = (ox, oy, ox + w * SS - 1, oy + h * SS - 1)
    outer = _rr_mask((W, H), box, r)
    if border:
        img.paste(Image.new("RGBA", (W, H), rgba(border)), mask=outer)
        inset = SS
        inner = _rr_mask((W, H), (box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset), max(r - inset, 1))
    else:
        inner = outer
    if gradient:
        g = (_dgradient(W, H, *gradient) if diagonal else _vgradient(W, H, *gradient)).convert("RGBA")
        img.paste(g, mask=inner)
    else:
        img.paste(Image.new("RGBA", (W, H), rgba(fill)), mask=inner)
    if highlight:
        shifted = ImageChops.offset(inner, 0, SS)
        crescent = ImageChops.subtract(inner, shifted).point(lambda v: round(v * highlight))
        white = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        white.putalpha(crescent)
        img = Image.alpha_composite(img, white)
    img = img.resize((TW, TH), Image.LANCZOS)
    if shadow:                                   # a sombra é borrada de qualquer jeito: pinta em 1x, que é bem mais rápido
        blur, dy, alpha = shadow
        sh = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + dy, pad + w - 1, pad + h - 1 + dy), radius, fill=round(255 * alpha))
        sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
        layer = Image.new("RGBA", (TW, TH), (0, 0, 0, 255))
        layer.putalpha(sh)
        img = Image.alpha_composite(layer, img)
    return img


def capsule(w: int, h: int, fill: str | None = None, gradient: tuple[str, str] | None = None) -> Image.Image:
    """Cápsula totalmente arredondada (trilho e preenchimento da barra de progresso, pílulas)."""
    if gradient:
        return _capsule_gradient(w, h, gradient)
    return surface(w, h, h // 2, fill or "#000000", None, highlight=0)


def _capsule_gradient(w: int, h: int, gradient: tuple[str, str]) -> Image.Image:
    W, H = w * SS, h * SS
    g = Image.new("RGB", (W, H))
    a, b = _rgb(gradient[0]), _rgb(gradient[1])
    row = Image.new("RGB", (W, 1))
    row.putdata([tuple(round(a[i] + (b[i] - a[i]) * x / max(W - 1, 1)) for i in range(3)) for x in range(W)])
    g = row.resize((W, H))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste(g.convert("RGBA"), mask=_rr_mask((W, H), (0, 0, W - 1, H - 1), H // 2))
    return img.resize((w, h), Image.LANCZOS)


def atmosphere(w: int, h: int, base: str = BG) -> Image.Image:
    """Fundo do Nevora no tema escuro: duas luzes radiais muito sutis (violeta no canto, teal à direita)."""
    img = Image.new("RGBA", (w, h), rgba(base))

    def glow(cx: float, cy: float, radius: float, color: str, alpha: float) -> None:
        nonlocal img
        d = max(int(radius * 2), 2)
        # radial_gradient vai de 0 (centro) a 255 só nos cantos do quadrado; x√2 faz o círculo fechar em 255
        # (senão a luz acabava num corte reto no meio da borda). Queda quadrática = borda bem suave.
        g = Image.radial_gradient("L").resize((d, d))
        g = g.point(lambda v: round(alpha * 255 * (1 - min(v * 1.4142, 255) / 255) ** 2))
        mask = Image.new("L", (w, h), 0)
        mask.paste(g, (int(cx - radius), int(cy - radius)))
        layer = Image.new("RGBA", (w, h), rgba(color))
        layer.putalpha(mask)
        img = Image.alpha_composite(img, layer)

    glow(w * 0.15, -h * 0.05, max(w, h) * 0.75, ACCENT, 0.075)
    glow(w * 0.85, h * 0.35, max(w, h) * 0.55, TEAL, 0.04)
    # grão quase imperceptível (Nevora): também quebra as faixas que um degradê tão suave faz em 8 bits
    noise = Image.effect_noise((w, h), 1.6)
    rgb = img.convert("RGB")
    channels = [ImageChops.add(c, noise, 1, -128) for c in rgb.split()]
    return Image.merge("RGB", channels).convert("RGBA")


# --------------------------------------------------------------------------------------------- ícones
# Traço de 1,75 em grade 24x24 (como o Lucide). Cada ícone é uma lista de operações em coordenadas da grade.
ICONS = {
    "search": [("circle", 11, 11, 8), ("line", [(21, 21), (16.65, 16.65)])],
    "refresh": [("arc", 12, 12, 9, 180, 330), ("line", [(21, 3), (21, 8), (16, 8)]),
                ("arc", 12, 12, 9, 0, 150), ("line", [(3, 21), (3, 16), (8, 16)])],
    "briefcase": [("rrect", 2, 7, 22, 21, 2.5), ("line", [(16, 7), (16, 5.5), (14.5, 4), (9.5, 4), (8, 5.5), (8, 7)]),
                  ("line", [(2, 13), (22, 13)])],
    "check": [("circle", 12, 12, 9.5), ("line", [(8, 12.3), (11, 15.3), (16, 9.3)])],
    "building": [("rrect", 5, 3, 19, 21, 2), ("line", [(9, 8), (9.01, 8)]), ("line", [(15, 8), (15.01, 8)]),
                 ("line", [(9, 12), (9.01, 12)]), ("line", [(15, 12), (15.01, 12)]), ("line", [(10, 21), (10, 17), (14, 17), (14, 21)])],
    "layout": [("rrect", 3, 3, 10.5, 12, 1.8), ("rrect", 13.5, 3, 21, 8, 1.8),
               ("rrect", 13.5, 12, 21, 21, 1.8), ("rrect", 3, 16, 10.5, 21, 1.8)],
    "pin": [("arc", 12, 10, 8, 180, 360), ("line", [(20, 10), (20, 11), (12, 22)]), ("line", [(4, 10), (4, 11), (12, 22)]),
            ("circle", 12, 10, 3)],
    "folder": [("line", [(4, 20), (20, 20), (22, 18), (22, 8), (20, 6), (12.4, 6), (10.6, 4), (4, 3.2), (2, 5), (2, 18), (4, 20)])],
    "linkedin": [("rrect", 3, 3, 21, 21, 3.5), ("line", [(8, 11), (8, 17)]), ("line", [(8, 7.9), (8.01, 7.9)]),
                 ("line", [(12, 17), (12, 11)]), ("line", [(12, 13.5), (13.2, 11.5), (15.2, 11), (16.5, 12.2), (16.5, 17)])],
}


@lru_cache(maxsize=256)
def icon(name: str, size: int, color: str, stroke: float = 1.75) -> Image.Image:
    """Ícone `name` em `size` px, cor `color`, traço `stroke` (grade 24). RGBA com fundo transparente."""
    S = size * SS * 2
    k = S / 24
    mask = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(mask)
    wpx = max(int(stroke * k), 1)

    def pt(p):
        return p[0] * k, p[1] * k

    def dot(x, y):
        d.ellipse((x - wpx / 2, y - wpx / 2, x + wpx / 2, y + wpx / 2), fill=255)

    for op in ICONS[name]:
        kind = op[0]
        if kind == "circle":
            _, cx, cy, r = op
            d.ellipse(((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k), outline=255, width=wpx)
        elif kind == "arc":
            _, cx, cy, r, a0, a1 = op
            d.arc(((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k), a0, a1, fill=255, width=wpx)
        elif kind == "rrect":
            _, x0, y0, x1, y1, rr = op
            d.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), rr * k, outline=255, width=wpx)
        elif kind == "line":
            pts = [pt(p) for p in op[1]]
            d.line(pts, fill=255, width=wpx, joint="curve")
            for p in pts:
                dot(*p)
    img = Image.new("RGBA", (S, S), rgba(color))
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def to_photo_data(img: Image.Image) -> bytes:
    """PNG em base64, o formato que `tk.PhotoImage(data=...)` aceita (Tk 8.6 e 9)."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG", compress_level=1)
    return base64.b64encode(buf.getvalue())


def over(scene: Image.Image, sprite: Image.Image, x: int, y: int) -> Image.Image:
    """`sprite` (RGBA) composto sobre o trecho da `scene` onde ele ficará: resultado opaco, pronto para o Tk."""
    base = scene.crop((x, y, x + sprite.width, y + sprite.height)).convert("RGBA")
    return Image.alpha_composite(base, sprite)


def mix(a: str, b: str, t: float) -> str:
    ca, cb = _rgb(a), _rgb(b)
    return _hex(*(ca[i] + (cb[i] - ca[i]) * t for i in range(3)))
