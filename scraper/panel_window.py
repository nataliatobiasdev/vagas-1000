"""Janela do painel dentro do app: o dashboard abre numa janela do vagas1000 (WebView2), sem o Chrome.

Roda num processo à parte (`vagas1000.exe --janela-painel`), porque o WebView precisa do laço de eventos
principal e a janela principal (Tk) já usa o dele. Se o WebView2/pywebview não estiver disponível ou falhar,
cai no navegador padrão: o painel sempre abre.

A página é a mesma `out/dashboard.html`. A janela só acrescenta uma ponte (`pywebview.api`) para o que o arquivo
estático não carrega: o payload bruto de cada vaga, que fica no banco.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import webbrowser
from pathlib import Path

from . import db, paths

log = logging.getLogger("scraper")


class Api:
    """Ponte JS -> Python (window.pywebview.api.*)."""

    def get_raw(self, key: str):
        """Payload original que a fonte enviou para esta vaga (ou None)."""
        conn = db.connect()
        try:
            row = conn.execute("SELECT raw FROM jobs WHERE job_key=?", (key,)).fetchone()
        finally:
            conn.close()
        try:
            raw = json.loads(row["raw"]) if row and row["raw"] else None
        except ValueError:
            raw = None
        return raw or None


def dashboard_path() -> Path:
    """Garante que o painel existe (gera a partir do banco se ainda não foi gerado)."""
    out = paths.OUT / "dashboard.html"
    if not out.exists():
        from . import dashboard
        conn = db.connect()
        try:
            dashboard.build(conn, out)
        finally:
            conn.close()
    return out


def open_in_browser(path: Path) -> None:
    webbrowser.open(path.resolve().as_uri())


def run(autotest: bool = False) -> int:
    """Abre a janela do painel. Devolve o código de saída (autoteste: 0 = cards renderizados)."""
    path = dashboard_path()
    try:
        import webview
    except Exception as e:                       # pywebview/pythonnet ausentes
        log.warning("WebView indisponível (%s): abrindo no navegador", e)
        if autotest:
            return 2
        open_in_browser(path)
        return 0

    result = {"cards": -1, "error": ""}

    def probe(win):
        time.sleep(2.5)
        try:
            result["cards"] = int(win.evaluate_js("document.querySelectorAll('.card').length"))
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
        win.destroy()

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True             # "Baixar registro" salva o JSON da vaga
        win = webview.create_window("vagas1000 · Painel", url=path.resolve().as_uri(), js_api=Api(),
                                    width=1320, height=860, min_size=(900, 600), background_color="#0B0E19")
        storage = paths.HOME / ".webview"
        storage.mkdir(parents=True, exist_ok=True)
        webview.start(probe if autotest else None, win if autotest else None, private_mode=False,
                      storage_path=str(storage))
    except Exception as e:
        log.warning("não consegui abrir a janela do painel (%s): abrindo no navegador", e)
        if autotest:
            print(f"falha: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        open_in_browser(path)
        return 0
    if autotest:
        print(f"cards={result['cards']} {result['error']}".strip())
        return 0 if result["cards"] > 0 else 1
    return 0
