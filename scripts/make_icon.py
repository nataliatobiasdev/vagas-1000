"""Ferramenta de desenvolvimento (não roda no build): desenha o ícone do vagas1000.

Lupa em gradiente violeta -> teal sobre um quadrado arredondado Nevora (#151A2B). Gera
assets/icon.ico (16 a 256 px), assets/icon.png (1024 px) e docs/public/{logo,icon-256,favicon-32,favicon-64}.png.
Requer: pip install pillow. Falha se algum canto sair opaco (pegaria um recorte errado).
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S = 2048                                   # supersampling; reduzido no fim
VIOLET, TEAL, SURFACE, BORDER = (157, 140, 255), (66, 214, 205), (21, 26, 43), (60, 66, 92)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def diagonal_gradient(size, c1, c2, box):
    """Gradiente diagonal só dentro de `box` (x0, y0, x1, y1): o aro vai do violeta ao teal por inteiro."""
    x0, y0, x1, y1 = box
    g = Image.new("RGB", (size, size))
    px = g.load()
    span = (x1 - x0) + (y1 - y0)
    for y in range(size):
        for x in range(size):
            px[x, y] = lerp(c1, c2, min(1, max(0, ((x - x0) + (y - y0)) / span)))
    return g


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    m = int(S * 0.06)                                   # margem para a sombra
    box = (m, m, S - m, S - m)
    r = int(S * 0.22)
    # sombra suave em alfa real
    sh = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sh).rounded_rectangle((m, m + S * 0.02, S - m, S - m + S * 0.02), r, fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(S * 0.018))
    img.paste((0, 0, 0, 255), mask=sh)
    # corpo do ícone
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle(box, r, fill=SURFACE + (255,), outline=BORDER + (255,), width=int(S * 0.008))
    img = Image.alpha_composite(img, body)

    # lupa: aro em gradiente + cabo teal
    cx, cy, rad, w = int(S * 0.43), int(S * 0.42), int(S * 0.22), int(S * 0.062)
    ring = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(ring)
    rd.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=255, width=w)
    grad = diagonal_gradient(S, VIOLET, TEAL, (cx - rad, cy - rad, cx + rad, cy + rad)).convert("RGBA")
    grad.putalpha(ring)
    img = Image.alpha_composite(img, grad)
    handle = Image.new("L", (S, S), 0)
    hd = ImageDraw.Draw(handle)
    a = int(rad * 0.72)
    x1, y1 = cx + a, cy + a
    x2, y2 = int(S * 0.77), int(S * 0.76)
    hd.line((x1, y1, x2, y2), fill=255, width=int(w * 1.15))
    for x, y in ((x2, y2),):
        hd.ellipse((x - w * 0.575, y - w * 0.575, x + w * 0.575, y + w * 0.575), fill=255)
    teal = Image.new("RGBA", (S, S), TEAL + (255,))
    teal.putalpha(handle)
    img = Image.alpha_composite(img, teal)
    # brilho de "achado" dentro da lente (pequeno, discreto)
    sp = Image.new("L", (S, S), 0)
    sd = ImageDraw.Draw(sp)
    sx, sy, sr = cx - int(rad * 0.28), cy - int(rad * 0.28), int(S * 0.028)
    sd.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=150)
    img.paste((244, 246, 255, 255), mask=sp)
    return img


def main() -> None:
    big = draw()
    out = big.resize((1024, 1024), Image.LANCZOS)
    for corner in ((0, 0), (1023, 0), (0, 1023), (1023, 1023)):
        if out.getpixel(corner)[3] != 0:
            raise SystemExit(f"canto {corner} opaco: recorte errado")
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    out.save(assets / "icon.png")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    out.save(assets / "icon.ico", sizes=[(s, s) for s in sizes])
    pub = ROOT / "docs" / "public"
    pub.mkdir(parents=True, exist_ok=True)
    for name, s in (("logo.png", 512), ("icon-256.png", 256), ("favicon-64.png", 64), ("favicon-32.png", 32)):
        out.resize((s, s), Image.LANCZOS).save(pub / name)
    print("ok:", assets / "icon.ico")


if __name__ == "__main__":
    main()
