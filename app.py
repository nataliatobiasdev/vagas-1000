"""vagas1000 — janela principal: botão de atualização + barra de status estilo player.

Uso: app.bat (abre sem console) ou python app.py. Instalado: vagas1000.exe.
O status vem de out/status.json, gravado pelo runner a cada empresa.
Visual: design system Nevora, no acabamento macio do CAM (cantos arredondados anti-aliasados, sombras
suaves, ícones e pílulas, pintados com Pillow em scraper/gfx.py; tokens em scraper/theme.py).
"""
from __future__ import annotations

import ctypes
import json
import os
import sqlite3
import subprocess
import sys
import time
import tkinter as tk
import threading
import tkinter.font as tkfont
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from scraper import gfx, paths
from scraper.theme import (ACCENT, ACCENT_FG, BG, BORDER, DANGER, FIELD, FG, FONT_BODY, FONT_BODY_SB,
                           FONT_HEAD, FONT_MONO, MUTED, MUTED_2, PANEL, SUBTLE, TEAL, tint)
from scraper.version import __version__

APP_NAME = "vagas1000"
ROOT = paths.HOME
BUNDLE = paths.BUNDLE
OUT = paths.OUT
STATUS = OUT / "status.json"
DB = paths.DATA / "vagas.db"
LI_DIR = ROOT / "linkedin-jobs"                       # só existe no modo código-fonte
LI_PY = LI_DIR / ".venv" / "Scripts" / "python.exe"
LI_STATUS = LI_DIR / "out" / "status.json"
LI_REPORT = LI_DIR / "out" / "linkedin-report.md"
LI_LAST = LI_DIR / "out" / "last-run.json"
LI_CDP = "http://127.0.0.1:9222/json/version"
HAS_LINKEDIN = LI_PY.exists() and not paths.FROZEN

TEXT = FG
ERR = DANGER


def load_fonts() -> None:
    """Registra Inter, Space Grotesk e JetBrains Mono só para este processo (Windows)."""
    try:
        for f in (BUNDLE / "assets" / "fonts").glob("*.ttf"):
            ctypes.windll.gdi32.AddFontResourceExW(str(f), 0x10, 0)     # FR_PRIVATE
    except Exception:
        pass                                  # sem as fontes o Tk usa a fonte substituta


def _parse(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


class CText:
    """Texto do canvas com a mesma interface `.config(text=, fg=)` dos Labels: o resto do app não muda."""

    def __init__(self, canvas: tk.Canvas, text: str = "", fg: str = FG):
        self.canvas, self.text, self.fg, self.item = canvas, text, fg, None

    def config(self, **kw):
        if "text" in kw:
            self.text = kw["text"]
        if "fg" in kw:
            self.fg = kw["fg"]
        if self.item is not None:
            self.canvas.itemconfigure(self.item, text=self.text, fill=self.fg)

    configure = config


class CBtn:
    """Botão arredondado (raio 10, borda de 1 px, brilho interno e sombra suave) desenhado sobre a cena."""

    VARIANTS = {
        "primary": dict(fill=ACCENT, grad=("#B7AAFF", ACCENT), border="#CFC7FF", fg=ACCENT_FG, shadow=0.45,
                        hover_grad=("#C6BCFF", "#A99AFF"), icon=ACCENT_FG),
        "secondary": dict(fill=PANEL, grad=None, border=BORDER, fg=FG, shadow=0.25, hover_fill=SUBTLE,
                          hover_border=tint(MUTED, 0.4, BORDER), icon=FG),
        "teal": dict(fill=PANEL, grad=None, border=tint(TEAL, 0.45, PANEL), fg=TEAL, shadow=0.25,
                     hover_fill=SUBTLE, hover_border=tint(TEAL, 0.75, PANEL), icon=TEAL),
    }

    def __init__(self, app, key: str, text: str, command, variant="secondary", icon: str | None = None,
                 big: bool = False):
        self.app, self.key, self.text, self.command = app, key, text, command
        self.variant, self.icon, self.big = variant, icon, big
        self.enabled, self.hover = True, False
        self.images: dict[str, tk.PhotoImage] = {}
        self.img_item = self.txt_item = None
        self.box = (0, 0, 0, 0)

    # --- API compatível com tk.Button.config(state=, text=)
    def config(self, **kw):
        relayout = False
        if "text" in kw and kw["text"] != self.text:
            self.text, relayout = kw["text"], True
        if "state" in kw:
            self.enabled = kw["state"] != "disabled"
            if not self.enabled:
                self.hover = False
        if relayout:
            self.app.schedule_layout(0)
        else:
            self.paint()

    configure = config

    def font(self):
        return FONT_BODY_SB(12 if self.big else 10)

    def width(self, u) -> int:
        icon_w = u(18) + u(8) if self.icon else 0
        return u(36 if self.big else 28) + icon_w + self.app.measure(self.font(), self.text)

    def build(self, scene, x: int, y: int, w: int, h: int, u):
        """Guarda a geometria e gera o estado normal; hover e desativado saem sob demanda (mais rápido)."""
        self.scene, self.box, self.u = scene, (x, y, w, h), u
        self.images = {}
        self.image("normal")
        return u(10)

    def image(self, state: str):
        if state in self.images:
            return self.images[state]
        x, y, w, h = self.box
        u, v = self.u, self.VARIANTS[self.variant]
        pad = u(10)
        fill, border, grad = v["fill"], v["border"], v["grad"]
        if state == "hover":
            fill, border = v.get("hover_fill", fill), v.get("hover_border", border)
            grad = v.get("hover_grad", grad)
        if state == "disabled":
            if self.variant == "primary":
                fill, grad, border = tint(ACCENT, 0.3, PANEL), None, tint(ACCENT, 0.3, PANEL)
            else:
                fill = PANEL
        sprite = gfx.surface(w, h, u(10), fill, border, highlight=0.35 if self.variant == "primary" else 0.07,
                             gradient=grad, shadow=(u(8), u(2), v["shadow"]) if state != "disabled" else None, pad=pad)
        if self.icon:
            icon_color = MUTED_2 if state == "disabled" else v["icon"]
            if state == "disabled" and self.variant == "primary":
                icon_color = tint(ACCENT_FG, 0.55, PANEL)
            sprite.alpha_composite(gfx.icon(self.icon, u(18), icon_color),
                                   (pad + u(16 if self.big else 14), pad + (h - u(18)) // 2))
        self.images[state] = tk.PhotoImage(data=gfx.to_photo_data(gfx.over(self.scene, sprite, x - pad, y - pad)))
        return self.images[state]

    def paint(self):
        if self.img_item is None:
            return
        v = self.VARIANTS[self.variant]
        state = "disabled" if not self.enabled else ("hover" if self.hover else "normal")
        fg = v["fg"] if self.enabled else (tint(ACCENT_FG, 0.55, PANEL) if self.variant == "primary" else MUTED_2)
        self.app.canvas.itemconfigure(self.img_item, image=self.image(state))
        self.app.canvas.itemconfigure(self.txt_item, fill=fg)


class Vagas1000App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc = None
        self.log_file = None
        self.finished = False
        self.run_started = None
        self._last_results = 0
        self._last_errors = 0
        self.was_external = False
        self.li_proc = None
        self.li_log = None
        self.li_finished = False
        self.mode = None             # "update" | "linkedin"
        self._frac = 0.0
        self._cover_letter = "—"
        self._layout_job = None
        self._size = (0, 0)
        self._fonts: dict = {}
        self.scale = root.winfo_fpixels("1i") / 96                # escala do Windows (100% = 1,0)
        root.title(APP_NAME)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(int(1040 * self.scale), sw - 60), min(int(680 * self.scale), sh - 90)
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 3)
        root.geometry(f"{w}x{h}+{x}+{y}")                          # centralizada, sem cair para fora da tela
        root.minsize(min(int(980 * self.scale), w), min(int(620 * self.scale), h))
        root.configure(bg=BG)
        try:
            ico = BUNDLE / "assets" / "icon.ico"
            if ico.exists():
                root.iconbitmap(default=str(ico))
        except Exception:
            pass
        self._build()
        self._load_stats()
        self._restore_log()
        root.after(400, self._poll)

    # ------------------------------------------------------------------ medidas
    def u(self, v: float) -> int:
        return max(1, round(v * self.scale)) if v else 0

    def measure(self, font, text: str) -> int:
        key = tuple(font)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(root=self.root, family=font[0], size=font[1])
        return self._fonts[key].measure(text)

    # ------------------------------------------------------------------ UI
    def _build(self):
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        c = self.canvas
        self.sub = CText(c, "base local", MUTED)
        self.now = CText(c, "Pronto", FG)
        self.detail = CText(c, "clique em Atualizar base", MUTED)
        self.time = CText(c, "", MUTED)
        self.cards = {k: CText(c, "—", ACCENT if k == "eligible" else FG) for k in ("open", "eligible", "companies")}
        self.badge = self._Badge(self)
        self.btn_run = CBtn(self, "run", "Atualizar base", self.start_run, "primary", "refresh", big=True)
        self.btn_li = CBtn(self, "li", "Buscar no LinkedIn", self.start_linkedin, "teal", "linkedin")
        self.buttons = [self.btn_run]
        if HAS_LINKEDIN:                       # o app instalado não inclui o módulo do LinkedIn
            self.buttons.append(self.btn_li)
        self.buttons.append(CBtn(self, "dash", "Abrir painel", self.open_dashboard, icon="layout"))
        if HAS_LINKEDIN:
            self.buttons.append(CBtn(self, "lir", "Relatório LinkedIn", self.open_linkedin_report, icon="briefcase"))
        self.buttons.append(CBtn(self, "pres", "Abrir presenciais", self.open_presenciais, icon="pin"))
        self.buttons.append(CBtn(self, "dir", "Abrir pasta", self.open_folder, icon="folder"))
        self.buttons.append(CBtn(self, "imp", "Importar vagas", self.import_jobs, icon="upload"))
        self.log = tk.Text(c, bg=FIELD, fg=MUTED, bd=0, wrap="none", font=FONT_MONO(9), state="disabled",
                           padx=4, pady=2, insertbackground=ACCENT, selectbackground=tint(ACCENT, 0.3, FIELD),
                           highlightthickness=0, cursor="arrow")
        self._photos: list = []
        c.bind("<Configure>", lambda e: self.schedule_layout(60))

    class _Badge:
        """Pílula semântica (sucesso/erro/neutra): o tom vem do `fg` que o app pede."""

        def __init__(self, app):
            self.app, self.text, self.fg = app, "", MUTED

        def config(self, **kw):
            self.text, self.fg = kw.get("text", self.text), kw.get("fg", self.fg)
            self.app._draw_badge()

        configure = config

    def schedule_layout(self, delay: int = 60):
        if self._layout_job:
            self.root.after_cancel(self._layout_job)
        self._layout_job = self.root.after(delay, self._layout)

    def _layout(self):
        """Pinta a cena (fundo atmosférico + cartões arredondados) e posiciona textos, botões e o log."""
        self._layout_job = None
        c, u = self.canvas, self.u
        W, H = c.winfo_width(), c.winfo_height()
        if W < 50 or H < 50:
            return
        self._size = (W, H)
        c.delete("all")
        self._photos = []
        scene = gfx.atmosphere(W, H)
        M = u(28)
        gap = u(14)

        # --- cabeçalho: marca em gradiente (como o "C" do CAM), título e versão
        tile = u(46)
        scene.alpha_composite(gfx.surface(tile, tile, u(13), ACCENT, None, gradient=(ACCENT, TEAL), diagonal=True,
                                          highlight=0.28, shadow=(u(10), u(3), 0.4), pad=u(10)),
                              (M - u(10), u(26) - u(10)))
        scene.alpha_composite(gfx.icon("search", u(26), ACCENT_FG, 2.0), (M + (tile - u(26)) // 2, u(26) + (tile - u(26)) // 2))
        tx = M + tile + u(14)
        ver_w = self.measure(FONT_MONO(9), f"v{__version__}") + u(22)
        pill = gfx.capsule(ver_w, u(24), SUBTLE)
        scene.alpha_composite(pill, (W - M - ver_w, u(36)))

        # --- cartões de números
        top = u(104)
        card_h = u(92)
        card_w = (W - 2 * M - 2 * gap) // 3
        specs = (("open", "vagas abertas", "briefcase", ACCENT), ("eligible", "elegíveis", "check", TEAL),
                 ("companies", "empresas", "building", ACCENT))
        for i, (key, label, ic, col) in enumerate(specs):
            x = M + i * (card_w + gap)
            scene.alpha_composite(gfx.surface(card_w, card_h, u(16), PANEL, BORDER, shadow=(u(18), u(6), 0.4), pad=u(22)),
                                  (x - u(22), top - u(22)))
            t = u(42)
            scene.alpha_composite(gfx.surface(t, t, u(12), tint(col, 0.14, PANEL), tint(col, 0.3, PANEL), highlight=0.05),
                                  (x + u(18), top + (card_h - t) // 2))
            scene.alpha_composite(gfx.icon(ic, u(20), col), (x + u(18) + (t - u(20)) // 2, top + (card_h - t) // 2 + (t - u(20)) // 2))

        # --- botões
        by = top + card_h + u(20)
        bh_small, bh_big = u(40), u(46)
        bx, row = M, 0
        for b in self.buttons:
            h = bh_big if b.big else bh_small
            w = b.width(u)
            if bx + w > W - M and bx > M:                  # não cabe na linha: desce (janela estreita ou muitos botões)
                bx, row = M, row + 1
            y = by + row * (bh_big + u(12)) + (bh_big - h) // 2
            b.build(scene, bx, y, w, h, u)
            bx += w + u(10)
        by_end = by + (row + 1) * bh_big + row * u(12)

        # --- área do log (campo arredondado) e card do player
        player_h = u(108)
        player_y = H - u(22) - player_h
        log_y = by_end + u(20)
        log_h = max(player_y - u(18) - log_y, u(60))
        scene.alpha_composite(gfx.surface(W - 2 * M, log_h, u(16), FIELD, BORDER, highlight=0.03),
                              (M, log_y))
        scene.alpha_composite(gfx.surface(W - 2 * M, player_h, u(18), PANEL, BORDER, shadow=(u(24), u(8), 0.5), pad=u(28)),
                              (M - u(28), player_y - u(28)))
        track_x, track_w = M + u(20), W - 2 * M - u(40)
        self._track = (track_x, player_y + player_h - u(22), track_w, u(6))
        scene.alpha_composite(gfx.capsule(track_w, u(6), SUBTLE), (track_x, self._track[1]))
        self.scene = scene
        self._geo = dict(M=M, W=W, H=H, player_y=player_y, player_h=player_h, top=top, card_w=card_w, card_h=card_h,
                         gap=gap, tile=tile, ver_w=ver_w)

        # --- fundo e elementos dinâmicos
        self.bg_photo = tk.PhotoImage(data=gfx.to_photo_data(scene))
        c.create_image(0, 0, image=self.bg_photo, anchor="nw")
        self.sub.item = c.create_text(tx, u(26) + u(36), text=self.sub.text, fill=self.sub.fg, anchor="nw",
                                      font=FONT_BODY(10))
        c.create_text(tx, u(24), text=APP_NAME, fill=FG, anchor="nw", font=FONT_HEAD(22))
        c.create_text(W - M - ver_w // 2, u(36) + u(12), text=f"v{__version__}", fill=MUTED, font=FONT_MONO(9))
        for i, (key, label, ic, col) in enumerate(specs):
            x = M + i * (card_w + gap)
            tx2 = x + u(18) + u(42) + u(16)
            c.create_text(tx2, top + u(22), text=label.upper(), fill=MUTED, anchor="nw", font=FONT_MONO(8))
            item = self.cards[key]
            item.item = c.create_text(tx2, top + u(38), text=item.text, fill=item.fg, anchor="nw", font=FONT_HEAD(26))
        for b in self.buttons:
            x, y, w, h = b.box
            pad = u(10)
            b.img_item = c.create_image(x - pad, y - pad, image=b.images["normal"], anchor="nw", tags=("btn", f"b_{b.key}"))
            icon_w = (u(18) + u(8)) if b.icon else 0
            left = x + (u(16 if b.big else 14) if b.icon else (w - self.measure(b.font(), b.text)) // 2)
            b.txt_item = c.create_text(left + icon_w, y + h // 2, text=b.text, anchor="w", font=b.font(),
                                       fill=b.VARIANTS[b.variant]["fg"], tags=("btn", f"b_{b.key}"))
            b.paint()
            for tag in (f"b_{b.key}",):
                c.tag_bind(tag, "<Enter>", lambda e, b=b: self._btn_hover(b, True))
                c.tag_bind(tag, "<Leave>", lambda e, b=b: self._btn_hover(b, False))
                c.tag_bind(tag, "<Button-1>", lambda e, b=b: b.enabled and b.command())
        pad_t = u(12)
        c.create_window(M + pad_t, log_y + pad_t, window=self.log, anchor="nw",
                        width=W - 2 * M - 2 * pad_t, height=log_h - 2 * pad_t)
        px = M + u(20)
        self.now.item = c.create_text(px + u(58) + u(16), player_y + u(18), text=self.now.text, fill=self.now.fg,
                                      anchor="nw", font=FONT_HEAD(14))
        self.detail.item = c.create_text(px + u(58) + u(16), player_y + u(46), text=self.detail.text, fill=self.detail.fg,
                                         anchor="nw", font=FONT_BODY(9))
        self.time.item = c.create_text(W - M - u(20), player_y + u(16), text=self.time.text, fill=self.time.fg,
                                       anchor="ne", font=FONT_MONO(11))
        self._draw_cover(self._cover_letter)
        self._draw_progress()
        self._draw_badge()

    def _btn_hover(self, b: CBtn, on: bool):
        b.hover = on and b.enabled
        self.canvas.configure(cursor="hand2" if (on and b.enabled) else "")
        b.paint()

    def _put(self, sprite, x, y, tag, anchor="nw"):
        """Compõe `sprite` sobre a cena e põe no canvas (tag para poder apagar depois)."""
        photo = tk.PhotoImage(data=gfx.to_photo_data(gfx.over(self.scene, sprite, x, y)))
        self._photos.append(photo)
        return self.canvas.create_image(x, y, image=photo, anchor="nw", tags=tag)

    def _draw_cover(self, letter: str):
        self._cover_letter = letter
        if not getattr(self, "scene", None):
            return
        c, u, g = self.canvas, self.u, self._geo
        c.delete("cover")
        size = u(58)
        x, y = g["M"] + u(20), g["player_y"] + u(16)
        tile = gfx.surface(size, size, u(15), ACCENT, None, gradient=(ACCENT, TEAL), diagonal=True, highlight=0.3)
        if letter in ("—", ""):
            tile.alpha_composite(gfx.icon("search", u(28), ACCENT_FG, 2.0), ((size - u(28)) // 2, (size - u(28)) // 2))
            self._put(tile, x, y, "cover")
        else:
            self._put(tile, x, y, "cover")
            c.create_text(x + size // 2, y + size // 2, text=letter[:1].upper(), fill=ACCENT_FG, font=FONT_HEAD(20),
                          tags="cover")

    def _draw_progress(self):
        if not getattr(self, "scene", None):
            return
        c = self.canvas
        c.delete("prog")
        x, y, w, h = self._track
        if self._frac > 0:
            fw = max(h, int(w * min(self._frac, 1.0)))
            self._put(gfx.capsule(fw, h, gradient=(ACCENT, TEAL)), x, y, "prog")

    def _draw_badge(self):
        if not getattr(self, "scene", None):
            return
        c, u, g = self.canvas, self.u, self._geo
        c.delete("badge")
        text, color = self.badge.text, self.badge.fg
        if not text:
            return
        w, h = self.measure(FONT_MONO(9), text) + u(24), u(24)
        x, y = g["W"] - g["M"] - u(20) - w, g["player_y"] + u(46)
        neutral = color == MUTED
        sprite = gfx.surface(w, h, h // 2, SUBTLE if neutral else tint(color, 0.16, PANEL),
                             None if neutral else tint(color, 0.38, PANEL), highlight=0)
        self._put(sprite, x, y, "badge")
        c.create_text(x + w // 2, y + h // 2, text=text, fill=color, font=FONT_MONO(9), tags="badge")

    # ------------------------------------------------------------------ dados
    def _load_stats(self):
        try:
            con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            open_jobs = con.execute("select count(*) from jobs where status='open'").fetchone()[0]
            eligible = con.execute("select count(*) from jobs where status='open' and verdict='ELIGIBLE'").fetchone()[0]
            companies = con.execute("select count(*) from companies where coalesce(adapter,'')<>'importado'").fetchone()[0]
            last = con.execute("select started_at,total,new_count from runs order by run_id desc limit 1").fetchone()
            con.close()
            self.cards["open"].config(text=f"{open_jobs:,}".replace(",", "."))
            self.cards["eligible"].config(text=f"{eligible:,}".replace(",", "."))
            self.cards["companies"].config(text=str(companies))
            if last and last[0]:
                dt = _parse(last[0])
                quando = dt.strftime("%d/%m %H:%M") if dt else last[0]
                self.sub.config(text=f"base local · última atualização {quando} · {open_jobs:,} vagas abertas".replace(",", "."))
        except Exception as e:
            self.sub.config(text=f"base local · banco indisponível ({type(e).__name__})")

    def _status(self):
        try:
            return json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ------------------------------------------------------------------ ações
    def start_run(self):
        if self.proc and self.proc.poll() is None:
            return
        self.mode = "update"
        self.btn_run.config(state="disabled", text="Atualizando…")
        self.btn_li.config(state="disabled")
        self.finished = False
        self._last_results = 0
        self._last_errors = 0
        self.run_started = time.time()
        logs = paths.LOGS
        logs.mkdir(parents=True, exist_ok=True)
        self.log_file = open(logs / "app-run.log", "a", encoding="utf-8")
        self.log_file.write(f"\n=== {datetime.now():%d/%m/%Y %H:%M:%S} atualização pelo app ===\n")
        self.log_file.flush()
        self._append_log("Atualização iniciada…")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [sys.executable] if paths.FROZEN else [sys.executable, str(Path(__file__).resolve())]
        self.proc = subprocess.Popen(cmd + ["--scrape", "--no-open"], cwd=str(ROOT),
                                     stdout=self.log_file, stderr=subprocess.STDOUT, creationflags=flags)

    # ------------------------------------------------------------- LinkedIn
    def start_linkedin(self):
        if (self.proc and self.proc.poll() is None) or (self.li_proc and self.li_proc.poll() is None):
            return
        if not LI_PY.exists():
            messagebox.showerror("LinkedIn", "Ambiente do linkedin-jobs não encontrado.\n"
                                             "Rode linkedin-jobs\\setup.bat primeiro.")
            return
        force = False
        try:
            prev = json.loads(LI_LAST.read_text(encoding="utf-8"))
            if prev.get("date") == datetime.now().strftime("%Y-%m-%d"):
                if not messagebox.askyesno(
                        "LinkedIn",
                        f"Já rodou hoje ({prev.get('found', 0)} vagas).\n"
                        "Rodar de novo aumenta o risco de bloqueio. Continuar?"):
                    return
                force = True
        except Exception:
            pass
        if not self._cdp_up():
            if not messagebox.askyesno(
                    "LinkedIn",
                    "O Chrome de depuração (porta 9222) não está aberto.\n"
                    "Abrir agora? (usa uma cópia do seu perfil, já logado — é o mesmo Chrome de antes)"):
                return
            self._launch_debug_chrome()
            if not self._cdp_up():
                messagebox.showerror("LinkedIn", "Não consegui abrir o Chrome de depuração.\n"
                                                 "Rode linkedin-jobs\\launch_chrome.py manualmente.")
                return
        self.mode = "linkedin"
        self.li_finished = False
        self.btn_run.config(state="disabled")
        self.btn_li.config(state="disabled", text="LinkedIn rodando…")
        self._append_log("LinkedIn: modo seguro — 2 páginas, últimas 24h, sem abrir detalhe.")
        logs = paths.LOGS
        logs.mkdir(parents=True, exist_ok=True)
        self.li_log = open(logs / "linkedin-app.log", "a", encoding="utf-8")
        args = [str(LI_PY), "linkedin_jobs.py", "--pages", "2", "--max-jobs", "50",
                "--details", "0", "--tpr", "r86400", "--top", "30"]
        if force:
            args.append("--force")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.li_proc = subprocess.Popen(args, cwd=str(LI_DIR), stdout=self.li_log,
                                            stderr=subprocess.STDOUT, creationflags=flags)
        except Exception as e:
            self.mode = None
            self.btn_run.config(state="normal")
            self.btn_li.config(state="normal", text="Buscar no LinkedIn")
            if self.li_log:
                self.li_log.close()
                self.li_log = None
            messagebox.showerror("LinkedIn", f"Não consegui iniciar: {e}")

    def _cdp_up(self) -> bool:
        try:
            with urllib.request.urlopen(LI_CDP, timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    def _launch_debug_chrome(self):
        try:
            subprocess.Popen([str(LI_PY), "launch_chrome.py"], cwd=str(LI_DIR),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for _ in range(30):
                time.sleep(1)
                if self._cdp_up():
                    return
        except Exception:
            pass

    def _li_status(self):
        try:
            return json.loads(LI_STATUS.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _poll_linkedin(self):
        st = self._li_status()
        alive = self.li_proc is not None and self.li_proc.poll() is None
        if alive:
            self._render_li_running(st)
        elif self.li_proc is not None:
            self._render_li_done(st, self.li_proc.poll())
        elif self.li_finished:
            pass
        else:
            self._render_li_idle(st)

    def _render_li_running(self, st):
        st = st or {}
        total = max(int(st.get("total_pages") or 1), 1)
        done = int(st.get("done_pages") or 0)
        self._frac = min(0.99, done / total + 0.02)
        self._draw_progress()
        self._draw_cover("in")
        busca = (st.get("search") or "LinkedIn")[:38]
        self.now.config(text=f"LinkedIn · {busca}", fg=TEXT)
        self.detail.config(text=f"página {st.get('page', 0)} de {st.get('pages', 2)} · "
                                f"{st.get('found', 0)} vagas · {self._elapsed(st)}")
        self.badge.config(text="modo seguro", fg=MUTED)
        self.time.config(text=self._elapsed(st))

    def _render_li_done(self, st, code):
        if self.li_finished:
            return
        self.li_finished = True
        if self.li_log:
            self.li_log.close()
            self.li_log = None
        self.btn_run.config(state="normal")
        self.btn_li.config(state="normal", text="Buscar no LinkedIn")
        st = st or {}
        if code == 0 and st.get("state") == "done":
            dur = self._duration(st)
            self._frac = 1.0
            self._draw_progress()
            self._draw_cover("in")
            self.now.config(text="LinkedIn concluído", fg=TEXT)
            self.detail.config(text=f"{st.get('found', 0)} vagas · relatório pronto · {dur}")
            self.badge.config(text="relatório", fg=MUTED)
            self.time.config(text=dur)
            self._append_log(f"LinkedIn: {st.get('found', 0)} vagas em {dur} (relatório salvo)")
            for t in (st.get("top") or [])[:5]:
                self._append_log(f"  {t.get('match_pct', 0):3}% {str(t.get('title'))[:52]} | {str(t.get('company'))[:26]}")
        elif code == 3 or st.get("state") == "blocked":
            self._draw_cover("!")
            self.now.config(text="LinkedIn: CAPTCHA/desafio — parei", fg=ERR)
            self.detail.config(text=(st.get("message") or "verifique no Chrome")[:110])
            self.badge.config(text="bloqueado", fg=ERR)
            self._append_log(f"LinkedIn parou: {st.get('message', '')}")
        elif code == 4:
            self.now.config(text="LinkedIn: já rodou hoje", fg=TEXT)
            self.detail.config(text=(st.get("message") or "use --force para repetir")[:110])
            self.badge.config(text="1x/dia", fg=MUTED)
            self._append_log("LinkedIn: já rodou hoje; não repeti.")
        else:
            self._draw_cover("!")
            self.now.config(text="LinkedIn falhou", fg=ERR)
            self.detail.config(text=(st.get("message") or f"código {code}")[:110])
            self.badge.config(text=f"código {code}", fg=ERR)
            self._append_log(f"LinkedIn falhou ({code}): {st.get('message', '')}")

    def _render_li_idle(self, st):
        self._draw_cover("in")
        self.now.config(text="LinkedIn", fg=TEXT)
        if st and st.get("state") == "done":
            self.detail.config(text=f"última busca: {st.get('found', 0)} vagas · {self._duration(st)}")
            self.badge.config(text="relatório", fg=MUTED)
        else:
            self.detail.config(text="modo seguro: 2 páginas · últimas 24h · 1x/dia")
            self.badge.config(text="", fg=MUTED)
        self.time.config(text="")

    def import_jobs(self):
        """Importa vagas de um arquivo (JSON, CSV, Markdown): a captura do LinkedIn, uma planilha..."""
        start = paths.HOME / "imports"
        path = filedialog.askopenfilename(
            title="Importar vagas", initialdir=str(start if start.exists() else paths.HOME),
            filetypes=[("Vagas (JSON, CSV, Markdown)", "*.json *.csv *.tsv *.md *.markdown"), ("Todos os arquivos", "*.*")])
        if not path:
            return
        self._append_log(f"Importando {Path(path).name}…")
        threading.Thread(target=self._do_import, args=(path,), daemon=True).start()

    def _do_import(self, path: str):
        from scraper import importer
        try:
            res = importer.run_import(path)
            msg = (f"Importadas {res['lidas']} vagas ({res['fonte']}): {res['novas']} novas, "
                   f"{res['atualizadas']} já existiam. Abra o painel para ver.")
        except Exception as e:
            msg = f"Não consegui importar: {e}"
        self.root.after(0, lambda: (self._append_log(msg), self._load_stats()))

    def open_linkedin_report(self):
        if LI_REPORT.exists():
            os.startfile(LI_REPORT)  # noqa: S606
        else:
            self._append_log("Relatório do LinkedIn ainda não existe — rode 'Buscar no LinkedIn'.")

    def open_dashboard(self):
        """Abre o painel numa janela do app (WebView2). Se não der, cai no navegador padrão."""
        p = OUT / "dashboard.html"
        if not p.exists():
            self._append_log("Painel ainda não existe — rode uma atualização.")
            return
        if getattr(self, "panel_proc", None) and self.panel_proc.poll() is None:
            self._append_log("O painel já está aberto (veja a janela “vagas1000 · Painel”).")
            return
        try:
            cmd = [sys.executable] if paths.FROZEN else [sys.executable, str(Path(__file__).resolve())]
            self.panel_proc = subprocess.Popen(cmd + ["--janela-painel"], cwd=str(ROOT),
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            self._append_log(f"Não consegui abrir a janela do painel ({type(e).__name__}); abrindo no navegador.")
            os.startfile(p)  # noqa: S606

    def open_presenciais(self):
        p = OUT / "presenciais.md"
        if p.exists():
            os.startfile(p)  # noqa: S606
        else:
            self._append_log("Relatório de presenciais ainda não existe.")

    def open_folder(self):
        os.startfile(paths.HOME)  # noqa: S606

    # ------------------------------------------------------------------ loop
    def _poll(self):
        if self.mode == "linkedin":
            self._poll_linkedin()
            self.root.after(500, self._poll)
            return
        st = self._status()
        alive = self.proc is not None and self.proc.poll() is None
        external = (not alive) and bool(st) and st.get("state") == "running" and self._fresh(st)
        if alive or external:
            self.was_external = external
            self._render_running(st)
        elif self.proc is not None:
            self._render_done(st, self.proc.poll())
        elif self.was_external and st and st.get("state") == "done" and not self.finished:
            self.was_external = False
            self._render_done(st, 0)
        elif self.finished:
            pass                      # mantém a tela de "Concluído" até a próxima execução
        else:
            self._render_idle(st)
        self.root.after(500, self._poll)

    def _fresh(self, st) -> bool:
        upd = _parse((st or {}).get("updated_at") or "")
        return bool(upd) and (datetime.now() - upd).total_seconds() < 60

    def _render_idle(self, st):
        self._frac = 1.0 if (st and st.get("state") == "done") else 0.0
        self._draw_progress()
        self._draw_cover("—")
        self.now.config(text="Pronto", fg=TEXT)
        if st and st.get("state") == "done":
            dur = self._duration(st)
            self.detail.config(text=f"última atualização: {st.get('total_jobs', 0)} vagas · "
                                    f"{st.get('eligible', 0)} elegíveis · {dur}")
            erros = len(st.get("errors") or [])
            self.badge.config(text=f"{erros} erro(s)" if erros else "sem erros", fg=ERR if erros else MUTED)
            self.time.config(text=dur)
        else:
            self.detail.config(text="clique em Atualizar base para buscar as vagas")
            self.badge.config(text="", fg=MUTED)
            self.time.config(text="")

    def _render_running(self, st):
        st = st or {}
        total = max(int(st.get("total") or 0), 1)
        done = int(st.get("done") or 0)
        frac = done / total
        if st.get("current") and not done:
            frac = 0.01
        self._frac = frac
        self._draw_progress()
        cur = (st.get("current") or {}).get("name")
        if cur:
            self.now.config(text=f"Extraindo: {cur}", fg=TEXT)
            self._draw_cover(cur)
        else:
            self.now.config(text="Atualizando base…", fg=TEXT)
        self.detail.config(text=f"{done} de {total} empresas · {self._elapsed(st)}")
        erros = st.get("errors") or []
        self.badge.config(text=f"{len(erros)} erro(s)" if erros else "tudo certo até aqui",
                          fg=ERR if erros else MUTED)
        self.time.config(text=self._elapsed(st))
        self._flush_results(st)

    def _render_done(self, st, code):
        if self.finished:
            return
        self.finished = True
        if self.log_file:
            self.log_file.close()
            self.log_file = None
        self.btn_run.config(state="normal", text="Atualizar base")
        self.btn_li.config(state="normal")
        self.proc = None
        st = st or {}
        self._frac = 1.0 if st.get("state") == "done" else 0.0
        self._draw_progress()
        if code == 0 and st.get("state") == "done":
            dur = self._duration(st)
            self._draw_cover("✓")
            self.now.config(text="Concluído", fg=TEXT)
            self.detail.config(text=f"{st.get('total_jobs', 0)} vagas · {st.get('eligible', 0)} elegíveis · {dur}")
            erros = st.get("errors") or []
            self.badge.config(text=f"{len(erros)} erro(s)" if erros else "sem erros", fg=ERR if erros else MUTED)
            self.time.config(text=dur)
            self._append_log(f"Concluído: {st.get('total_jobs', 0)} vagas, {st.get('eligible', 0)} elegíveis, "
                             f"{len(erros)} erro(s) em {dur}")
        else:
            self._draw_cover("!")
            self.now.config(text="A atualização falhou", fg=ERR)
            self.detail.config(text=(st.get("error") or "veja logs/scraper.log") [:110])
            self.badge.config(text=f"código {code}", fg=ERR)
            self._append_log(f"Falhou (código {code}): {st.get('error', '')}")
        self._load_stats()

    def _flush_results(self, st):
        results = st.get("results") or []
        for r in results[self._last_results:]:
            mark = "ok " if r.get("ok") else "ERRO"
            self._append_log(f"[{mark}] {r.get('name')}: {r.get('count', 0)} vagas em {r.get('seconds')}s")
        self._last_results = len(results)
        errors = st.get("errors") or []
        for e in errors[self._last_errors:]:
            self._append_log(f"      ERRO {e.get('name')}: {str(e.get('error'))[:120]}")
        self._last_errors = len(errors)

    # ------------------------------------------------------------------ helpers
    def _elapsed(self, st) -> str:
        start = _parse(st.get("started_at") or "")
        if not start:
            return ""
        secs = max(0, int((datetime.now() - start).total_seconds()))
        return f"{secs // 60}:{secs % 60:02d}"

    def _duration(self, st) -> str:
        a, b = _parse(st.get("started_at") or ""), _parse(st.get("finished_at") or "")
        if not a or not b:
            return "—"
        secs = max(0, int((b - a).total_seconds()))
        return f"{secs // 60}m{secs % 60:02d}s"

    def _append_log(self, line: str):
        self.log.config(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _restore_log(self):
        st = self._status()
        if not st:
            return
        results = st.get("results") or []
        if st.get("state") == "done":
            self._append_log(f"Última execução: {st.get('total_jobs', 0)} vagas, "
                             f"{st.get('eligible', 0)} elegíveis ({self._duration(st)})")
        for r in results[-6:]:
            mark = "ok " if r.get("ok") else "ERRO"
            self._append_log(f"[{mark}] {r.get('name')}: {r.get('count', 0)} vagas")
        self._last_results = len(results)
        self._last_errors = len(st.get("errors") or [])


def main():
    if "--scrape" in sys.argv:          # modo captura: o app instalado chama a si mesmo (sem Python separado)
        sys.argv.remove("--scrape")
        import main as cli
        cli.main(sys.argv[1:])
        return
    if "--janela-painel" in sys.argv:   # painel em janela própria (WebView2); --autoteste: abre, confere e fecha
        from scraper import panel_window
        raise SystemExit(panel_window.run(autotest="--autoteste" in sys.argv))
    load_fonts()
    paths.ensure_config()              # o perfil editável já existe antes da 1ª atualização
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)             # texto nítido e tamanhos reais em telas com escala
    except Exception:
        pass
    root = tk.Tk()
    Vagas1000App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
