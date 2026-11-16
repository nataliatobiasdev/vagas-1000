"""Janela do Vagas Scraper: botão de atualização + barra de status estilo player.

Uso: app.bat (abre sem console) ou python app.py
O status vem de out/status.json, gravado pelo runner a cada empresa.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import tkinter as tk
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
STATUS = OUT / "status.json"
DB = ROOT / "data" / "vagas.db"
LI_DIR = ROOT / "linkedin-jobs"
LI_PY = LI_DIR / ".venv" / "Scripts" / "python.exe"
LI_STATUS = LI_DIR / "out" / "status.json"
LI_REPORT = LI_DIR / "out" / "linkedin-report.md"
LI_LAST = LI_DIR / "out" / "last-run.json"
LI_CDP = "http://127.0.0.1:9222/json/version"

BG = "#121212"
SURFACE = "#181818"
SURFACE2 = "#282828"
GREEN = "#1DB954"
GREEN_HI = "#1ED760"
BLUE = "#0A66C2"
TEXT = "#FFFFFF"
MUTED = "#B3B3B3"
ERR = "#F15E6C"

COMPANY = {"ciandt": "CI&T", "stone": "Stone", "zupinnovation": "Zup Innovation",
           "c6bank": "C6 Bank", "wellhub": "Wellhub", "vtex": "VTEX", "nubank": "Nubank",
           "quintoandar": "QuintoAndar", "jusbrasil": "Jusbrasil", "btgpactual": "BTG Pactual",
           "inter": "Banco Inter", "xpinc": "XP Inc.", "ebanx": "EBANX", "sezzle": "Sezzle",
           "clara": "Clara", "homeward": "Homeward", "engine": "Engine", "coderio": "Coderio",
           "luxurypresence": "Luxury Presence", "bluelightconsulting": "Bluelight",
           "infinity-constellation": "Infinity", "nortal": "Nortal", "inflect": "Inflect",
           "ilia": "ília", "sicredi": "Sicredi", "pagseguro": "PagSeguro", "porto": "Porto Bank",
           "stefanini": "Stefanini", "globalhitss": "Global Hitss", "softplan": "Softplan",
           "invillia": "Invillia", "valtech": "Valtech", "monks": "Monks", "bydbrasil": "BYD Brasil",
           "salesforce": "Salesforce", "rededor": "Rede D'Or", "assai": "Assaí", "renner": "Renner",
           "prio": "PRIO", "piracanjuba": "Piracanjuba", "bauducco": "Bauducco"}


def _parse(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


class VagasApp:
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
        root.title("Vagas Scraper")
        root.geometry("1040x640")
        root.minsize(960, 600)
        root.configure(bg=BG)
        self._build()
        self._load_stats()
        self._restore_log()
        root.after(400, self._poll)

    # ------------------------------------------------------------------ UI
    def _build(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=26, pady=(22, 4))
        tk.Label(head, text="Vagas Scraper", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        self.sub = tk.Label(head, text="base local", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.sub.pack(anchor="w", pady=(2, 0))

        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=26, pady=(16, 10))
        self.cards = {}
        specs = (("open", "vagas abertas"), ("eligible", "elegíveis"), ("companies", "empresas"))
        for i, (key, label) in enumerate(specs):
            card = tk.Frame(stats, bg=SURFACE)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            stats.grid_columnconfigure(i, weight=1)
            num = tk.Label(card, text="—", bg=SURFACE, fg=TEXT, anchor="w",
                           font=("Segoe UI Semibold", 24))
            num.pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(card, text=label, bg=SURFACE, fg=MUTED, anchor="w",
                     font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))
            self.cards[key] = num

        actions = tk.Frame(self.root, bg=BG)
        actions.pack(fill="x", padx=26, pady=(4, 10))
        self.btn_run = tk.Button(actions, text="▶  Atualizar base", command=self.start_run,
                                 bg=GREEN, fg="#000000", activebackground=GREEN_HI, activeforeground="#000000",
                                 font=("Segoe UI Semibold", 13), bd=0, padx=20, pady=10,
                                 cursor="hand2", disabledforeground="#0a3d1c")
        self.btn_run.pack(side="left")
        self.btn_li = tk.Button(actions, text="Buscar no LinkedIn", command=self.start_linkedin,
                                bg=BLUE, fg=TEXT, activebackground="#0A7BD6", activeforeground=TEXT,
                                font=("Segoe UI Semibold", 12), bd=0, padx=16, pady=10,
                                cursor="hand2", disabledforeground="#7aa9c9")
        self.btn_li.pack(side="left", padx=(10, 0))
        for label, cmd in (("Abrir painel", self.open_dashboard),
                           ("Relatório LinkedIn", self.open_linkedin_report),
                           ("Abrir presenciais", self.open_presenciais),
                           ("Abrir pasta", self.open_folder)):
            tk.Button(actions, text=label, command=cmd, bg=SURFACE2, fg=TEXT, bd=0, padx=14, pady=10,
                      font=("Segoe UI", 10), activebackground="#3a3a3a", activeforeground=TEXT,
                      cursor="hand2").pack(side="left", padx=(10, 0))

        self.log = tk.Text(self.root, bg=SURFACE, fg=MUTED, bd=0, height=8, wrap="none",
                           font=("Consolas", 9), state="disabled", padx=10, pady=8)
        self.log.pack(fill="both", expand=True, padx=26, pady=(0, 12))

        # ------------------------------------------------- barra estilo player
        self.bar = tk.Frame(self.root, bg=SURFACE, height=104)
        self.bar.pack(fill="x", side="bottom")
        self.bar.pack_propagate(False)
        self.progress = tk.Canvas(self.bar, bg=SURFACE, height=4, highlightthickness=0, bd=0)
        self.progress.pack(fill="x", side="top")
        self._frac = 0.0
        self.progress.bind("<Configure>", lambda e: self._draw_progress())

        body = tk.Frame(self.bar, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=18, pady=(10, 8))

        self.cover = tk.Canvas(body, width=58, height=58, bg=SURFACE, highlightthickness=0)
        self.cover.pack(side="left")
        self._draw_cover("—")

        mid = tk.Frame(body, bg=SURFACE)
        mid.pack(side="left", fill="both", expand=True, padx=(14, 10))
        self.now = tk.Label(mid, text="Pronto", bg=SURFACE, fg=TEXT, anchor="w",
                            font=("Segoe UI Semibold", 12))
        self.now.pack(anchor="w")
        self.detail = tk.Label(mid, text="clique em Atualizar base", bg=SURFACE, fg=MUTED, anchor="w",
                               font=("Segoe UI", 9))
        self.detail.pack(anchor="w", pady=(1, 0))

        right = tk.Frame(body, bg=SURFACE)
        right.pack(side="right")
        self.time = tk.Label(right, text="", bg=SURFACE, fg=MUTED, font=("Consolas", 10))
        self.time.pack(anchor="e")
        self.badge = tk.Label(right, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9))
        self.badge.pack(anchor="e", pady=(2, 0))

    def _draw_cover(self, letter: str):
        c = self.cover
        c.delete("all")
        c.create_rectangle(2, 2, 56, 56, fill=SURFACE2, outline="")
        c.create_text(29, 29, text=letter[:1].upper() or "V", fill=GREEN,
                      font=("Segoe UI Semibold", 22))

    def _draw_progress(self):
        c = self.progress
        c.delete("all")
        w = c.winfo_width()
        c.create_rectangle(0, 0, w, 4, fill=SURFACE2, outline="")
        if self._frac > 0:
            c.create_rectangle(0, 0, max(2, int(w * min(self._frac, 1.0))), 4, fill=GREEN, outline="")

    # ------------------------------------------------------------------ dados
    def _load_stats(self):
        try:
            con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            open_jobs = con.execute("select count(*) from jobs where status='open'").fetchone()[0]
            eligible = con.execute("select count(*) from jobs where status='open' and verdict='ELIGIBLE'").fetchone()[0]
            companies = con.execute("select count(*) from companies").fetchone()[0]
            last = con.execute("select started_at,total,new_count from runs order by run_id desc limit 1").fetchone()
            con.close()
            self.cards["open"].config(text=f"{open_jobs:,}".replace(",", "."))
            self.cards["eligible"].config(text=f"{eligible:,}".replace(",", "."))
            self.cards["companies"].config(text=str(companies))
            if last and last[0]:
                dt = _parse(last[0])
                quando = dt.strftime("%d/%m %H:%M") if dt else last[0]
                self.sub.config(text=f"base local · última execução {quando} · {last[1]} vagas")
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
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        self.log_file = open(logs / "app-run.log", "a", encoding="utf-8")
        self.log_file.write(f"\n=== {datetime.now():%d/%m/%Y %H:%M:%S} atualização pelo app ===\n")
        self.log_file.flush()
        self._append_log("Atualização iniciada…")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "main.py"), "--no-open"],
                                     cwd=str(ROOT), stdout=self.log_file,
                                     stderr=subprocess.STDOUT, creationflags=flags)

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
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
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

    def open_linkedin_report(self):
        if LI_REPORT.exists():
            os.startfile(LI_REPORT)  # noqa: S606
        else:
            self._append_log("Relatório do LinkedIn ainda não existe — rode 'Buscar no LinkedIn'.")

    def open_dashboard(self):
        p = OUT / "dashboard.html"
        if p.exists():
            os.startfile(p)  # noqa: S606
        else:
            self._append_log("Painel ainda não existe — rode uma atualização.")

    def open_presenciais(self):
        p = OUT / "presenciais.md"
        if p.exists():
            os.startfile(p)  # noqa: S606
        else:
            self._append_log("Relatório de presenciais ainda não existe.")

    def open_folder(self):
        os.startfile(ROOT)  # noqa: S606

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
        self.btn_run.config(state="normal", text="▶  Atualizar base")
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
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.25)
    except Exception:
        pass
    VagasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
