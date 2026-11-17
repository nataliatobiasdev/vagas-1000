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


CMD_FILE_NAME = "panel-cmd.json"
EMBED_FAILED = 3                     # código de saída de run_embedded quando não deu para embutir (o app abre o navegador)


def _trace(msg: str) -> None:
    """Diagnóstico do painel embutido: vai para o stderr (o autoteste do CI recolhe e publica)."""
    try:
        print(f"[painel] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def cmd_file() -> Path:
    return paths.OUT / CMD_FILE_NAME


def send_route(route: str) -> None:
    """Pede ao painel embutido que mostre `route` ('#/' = vagas, '#/linkedin' = aba do LinkedIn)."""
    f = cmd_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        n = json.loads(f.read_text(encoding="utf-8")).get("n", 0) + 1
    except (OSError, ValueError):
        n = 1
    f.write_text(json.dumps({"n": n, "route": route}), encoding="utf-8")


def embed_url(path: Path, route: str) -> str:
    """`#embed|<rota>` esconde as abas internas do painel: quem escolhe a aba é a janela principal.

    A marca vai no fragmento (#) e NÃO numa query (`?embed=1`): o WebView2 trata a query de uma URL `file://` como
    parte do nome do arquivo e mostra ERR_FILE_NOT_FOUND."""
    return path.resolve().as_uri() + "#embed|" + (route if route.startswith("#") else "#/")


def run_embedded(parent: int, route: str = "#/") -> int:
    """Painel como janela FILHA da janela principal (`parent` = HWND de um Frame do Tk), sem borda e do tamanho dele.

    O WebView2 precisa do laço de eventos do próprio processo, então ele continua num processo à parte; o Windows
    deixa uma janela de um processo ser filha de outra. A janela nasce fora da tela, vira filha (WS_CHILD +
    SetParent) e só então aparece no app, sem piscar. Em segundo plano, acompanha o tamanho do pai,
    obedece a `send_route` (arquivo `out/panel-cmd.json`) e se fecha quando a janela principal some.
    Devolve EMBED_FAILED se o WebView2 não estiver disponível ou a janela não puder ser embutida.
    """
    import ctypes
    from ctypes import wintypes

    try:
        import webview
    except Exception as e:
        log.warning("WebView indisponível (%s)", e)
        return EMBED_FAILED
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)         # mesma escala da janela principal (Tk)
    except Exception:
        pass
    u32 = ctypes.windll.user32
    u32.FindWindowW.restype = ctypes.c_void_p
    u32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_uint]
    u32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    u32.IsWindow.argtypes = [ctypes.c_void_p]
    GWL_STYLE, WS_CHILD, WS_VISIBLE = -16, 0x40000000, 0x10000000
    WS_POPUP, WS_CAPTION, WS_THICKFRAME = 0x80000000, 0x00C00000, 0x00040000
    SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010

    path = dashboard_path()
    title = f"vagas1000-painel-{ctypes.windll.kernel32.GetCurrentProcessId()}"
    try:                                         # o que já estava no arquivo é de uma sessão anterior: só vale o que vier depois
        n0 = int(json.loads(cmd_file().read_text(encoding="utf-8")).get("n", 0))
    except (OSError, ValueError):
        n0 = 0
    state = {"mtime": path.stat().st_mtime, "n": n0, "failed": True}

    def parent_size():
        r = wintypes.RECT()
        u32.GetClientRect(parent, ctypes.byref(r))
        return r.right - r.left, r.bottom - r.top

    def js(win, script, timeout=4.0):
        """`evaluate_js` com prazo. O pywebview espera o resultado num semáforo SEM limite: numa janela reparentada
        que não responde (ou se a tarefa do ExecuteScriptAsync falhar) a chamada nunca volta e o worker inteiro
        travava, deixando o processo vivo. Aqui a chamada roda numa thread descartável; sem resposta, devolve None."""
        import threading
        box = {}

        def call():
            try:
                box["v"] = win.evaluate_js(script)
            except Exception as e:                             # pragma: no cover - janela em fechamento
                box["e"] = e

        t = threading.Thread(target=call, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            _trace(f"evaluate_js sem resposta em {timeout:.0f}s")
            return None
        if "e" in box:
            raise box["e"]
        return box.get("v")

    def worker(win):
        try:
            _worker(win)
        except Exception:
            import traceback
            _trace("erro no worker:\n" + traceback.format_exc())
        finally:
            try:
                win.destroy()
            except Exception:
                pass
            # Destruir uma janela reparentada às vezes trava o desmonte do WebView2 e o processo ficaria órfão
            # depois que a janela principal some: se ele não terminar sozinho em poucos segundos, termina à força.
            import os
            import threading
            t = threading.Timer(2.5, os._exit, [EMBED_FAILED if state["failed"] else 0])
            t.daemon = True
            t.start()

    def _worker(win):
        hwnd = 0
        for _ in range(300):                                   # até ~30 s para o WebView2 criar a janela
            hwnd = u32.FindWindowW(None, title)
            if hwnd or not u32.IsWindow(parent):
                break
            time.sleep(0.1)
        _trace(f"janela do WebView2: hwnd={hwnd} pai_existe={bool(u32.IsWindow(parent))}")
        if not hwnd or not u32.IsWindow(parent):
            return
        style = u32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        u32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME)) | WS_CHILD | WS_VISIBLE)
        old = u32.SetParent(hwnd, parent)
        w, h = parent_size()
        u32.SetWindowPos(hwnd, None, 0, 0, max(w, 1), max(h, 1), SWP_NOZORDER | SWP_NOACTIVATE)
        _trace(f"SetParent: pai_anterior={old} pai_atual={u32.GetParent(hwnd)} tamanho={w}x{h}")
        state["failed"] = False
        info = None
        for _ in range(8):                                     # confere que a PÁGINA carregou (não um erro do WebView2)
            try:
                info = js(win, "[document.querySelectorAll('.card').length, document.documentElement.dataset.embed || '', "
                               "document.title].join('|')")
            except Exception:
                info = None
            if info and not str(info).startswith("0|"):
                break
            time.sleep(1)
        _trace(f"pagina: {info}")
        last = (w, h)
        while u32.IsWindow(parent):
            size = parent_size()
            if size != last and size[0] > 0 and size[1] > 0:
                u32.SetWindowPos(hwnd, None, 0, 0, size[0], size[1], SWP_NOZORDER | SWP_NOACTIVATE)
                last = size
            try:
                cmd = json.loads(cmd_file().read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cmd = None
            if cmd and cmd.get("n", 0) != state["n"]:
                state["n"] = cmd.get("n", 0)
                route = str(cmd.get("route") or "#/")
                _trace(f"comando: {route}")
                try:
                    m = dashboard_path().stat().st_mtime
                    if m != state["mtime"]:                    # o painel foi regenerado (nova atualização/importação)
                        state["mtime"] = m
                        win.load_url(embed_url(path, route))
                    else:
                        js(win, f"location.hash = {json.dumps(route)}")
                except Exception as e:                         # pragma: no cover - janela em fechamento
                    _trace(f"painel embutido: {e}")
            time.sleep(0.12)
        _trace("janela principal fechou: encerrando o painel")

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        win = webview.create_window(title, url=embed_url(path, route), js_api=Api(), width=900, height=600,
                                    x=-32000, y=-32000, frameless=True, easy_drag=False, background_color="#0B0E19")
        storage = paths.HOME / ".webview"
        storage.mkdir(parents=True, exist_ok=True)
        webview.start(worker, win, private_mode=False, storage_path=str(storage))
    except Exception as e:
        import traceback
        log.warning("não consegui embutir o painel (%s)", e)
        _trace("falha ao abrir o WebView:\n" + traceback.format_exc())
        return EMBED_FAILED
    return EMBED_FAILED if state["failed"] else 0


def run_embedded_autotest() -> int:
    """Autoteste do painel embutido (CI): abre uma janela Tk com um Frame, embute o painel nele e confere que a
    janela filha existe, está visível, tem o tamanho do Frame e mostra a página (várias cores, não só o fundo).
    Também troca para a aba do LinkedIn pelo arquivo de comandos. Devolve 0 se tudo certo."""
    import ctypes
    import subprocess
    import tkinter as tk
    from ctypes import wintypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    from PIL import ImageGrab
    u32 = ctypes.windll.user32
    u32.FindWindowExW.restype = ctypes.c_void_p
    u32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
    u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    u32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]

    root = tk.Tk()
    root.geometry("900x600+40+40")
    root.configure(bg="#0B0E19")
    host = tk.Frame(root, bg="#0B0E19")
    host.pack(fill="both", expand=True)
    root.update()
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve().parent.parent / "app.py")]
    child_log = paths.LOGS / "painel-embutido-filho.txt"
    child_log.parent.mkdir(parents=True, exist_ok=True)
    with open(child_log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd + ["--janela-painel", "--embutir", str(host.winfo_id()), "--rota", "#/"],
                                stdout=fh, stderr=subprocess.STDOUT)
    result = {"child": None, "colors": 0, "size": None, "visible": False, "exit": None}
    t0 = time.time()
    while time.time() - t0 < 60 and proc.poll() is None:
        root.update()
        time.sleep(0.1)
        child = u32.FindWindowExW(host.winfo_id(), None, None, None)
        if not child or not u32.IsWindowVisible(child):
            continue
        if time.time() - t0 < 6:                      # dá tempo para a página renderizar
            continue
        r = wintypes.RECT()
        u32.GetWindowRect(child, ctypes.byref(r))
        result.update(child=child, visible=True, size=(r.right - r.left, r.bottom - r.top))
        root.update()
        x, y = host.winfo_rootx(), host.winfo_rooty()
        shot = ImageGrab.grab(bbox=(x, y, x + host.winfo_width(), y + host.winfo_height()))
        result["colors"] = len(shot.convert("RGB").getcolors(maxcolors=1 << 20) or [0] * (1 << 20))
        break
    if result["child"] and proc.poll() is None:      # troca de aba pelo arquivo de comandos e confere que a janela segue viva
        send_route("#/linkedin")
        end = time.time() + 3
        while time.time() < end:
            root.update()
            time.sleep(0.1)
    alive = proc.poll() is None
    result["exit"] = proc.poll()
    w, h = host.winfo_width(), host.winfo_height()
    root.destroy()                                    # o painel percebe que o pai sumiu e fecha sozinho
    for _ in range(100):                              # até 10 s: o desmonte do WebView2 pode demorar um pouco
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    closed = proc.poll() is not None
    if not closed:
        proc.kill()
    # O WebView2 roda em processos filhos (msedgewebview2.exe). Matar só o pai os deixa órfãos, e no CI eles
    # seguram as saídas do passo e a esteira fica esperando até o time-out: derruba a árvore inteira.
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    size = result["size"] or (0, 0)
    import re
    try:
        log_text = child_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        log_text = ""
    m = re.search(r"pagina: (\d+)\|1\|", log_text)
    cards = int(m.group(1)) if m else 0                # cards > 0 e embed=1: é a página do painel, não uma tela de erro
    ok = bool(result["child"] and alive and closed and cards > 0
              and abs(size[0] - w) <= 4 and abs(size[1] - h) <= 4)
    try:
        tail = child_log.read_text(encoding="utf-8", errors="replace")[-1800:]
    except OSError:
        tail = ""
    print(f"filho:\n{tail}")
    print(f"embutido: janela={bool(result['child'])} visivel={result['visible']} tamanho={size} cores={result['colors']} "
          f"viva_apos_trocar_aba={alive} fechou_com_o_pai={closed} saida={result['exit']}")
    return 0 if ok else 1


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
