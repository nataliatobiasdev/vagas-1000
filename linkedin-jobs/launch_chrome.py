#!/usr/bin/env python3
"""Abre um Chrome de depuração (porta 9222) reaproveitando a SUA sessão do Chrome.

Por que não abrir o Chrome normal com --remote-debugging-port? A partir do Chrome 136 isso é
bloqueado quando se usa a pasta de perfil padrão. Então este script copia só o essencial do perfil
(Local State + Preferences + cookies) para uma pasta separada e abre o Chrome com ela — os cookies
mantêm o LinkedIn logado, sem novo login e sem alterar configurações da conta.

Uso:
    python launch_chrome.py            # copia o perfil (1ª vez) e abre o Chrome de depuração
    python launch_chrome.py --refresh  # recopia os cookies (se a sessão tiver expirado)
    python launch_chrome.py --status   # mostra se a porta 9222 está no ar
    python launch_chrome.py --clean    # apaga a cópia do perfil (faça isso ao terminar)

A cópia fica em linkedin-jobs\.profile (cookies ficam lá — apague com --clean).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CDP_PORT = 9222
SRC_PROFILE = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
DST_PROFILE = HERE / ".profile"          # fica no projeto (ignorado pelo git), não no %TEMP%
START_URL = "https://www.linkedin.com/jobs/"

# o mínimo para o Chrome reconhecer o perfil e descriptografar os cookies do seu usuário
ESSENTIALS = [
    "Local State",
    "Default/Preferences",
    "Default/Secure Preferences",
    "Default/Network/Cookies",
    "Default/Network/Cookies-wal",
    "Default/Network/Cookies-shm",
]


def chrome_path() -> Path:
    cands = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in cands:
        if c.exists():
            return c
    raise SystemExit("Chrome não encontrado. Instale o Google Chrome ou rode instalar.bat.")


def port_up() -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def copy_profile(dst: Path, refresh: bool) -> None:
    blockers = []
    for rel in ESSENTIALS:
        src = SRC_PROFILE / rel
        if not src.exists():
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not refresh:
            continue
        try:
            shutil.copy2(src, out)
        except OSError as e:
            blockers.append(f"{rel}: {e}")
    missing = [r for r in ("Local State", "Default/Network/Cookies") if not (dst / r).exists()]
    if missing:
        print("AVISO: não copiei", ", ".join(missing))
        print("  Feche o Chrome e rode de novo, ou faça login uma vez na janela que abrir.")
    if blockers:
        print("AVISO ao copiar:", "; ".join(blockers))
    print(f"perfil de depuração: {dst}")


def launch(dst: Path, fresh: bool, copy: bool = True, no_sandbox: bool = False) -> None:
    dst = Path(dst).expanduser().resolve()
    if port_up():
        print(f"Já existe um Chrome de depuração no ar em :{CDP_PORT}.")
        return
    dst.mkdir(parents=True, exist_ok=True)
    if not copy:
        print("perfil vazio (--no-copy): você precisará entrar no LinkedIn uma vez nessa janela.")
    elif fresh or not (dst / "Local State").exists():
        copy_profile(dst, refresh=fresh)
    cmd = [
        str(chrome_path()),
        f"--user-data-dir={dst}",
        f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        START_URL,
    ]
    if no_sandbox:
        cmd.append("--no-sandbox")
    print("abrindo Chrome de depuração...")
    subprocess.Popen(cmd, close_fds=True)
    for _ in range(60):
        v = port_up()
        if v:
            print(f"OK: {v.get('Browser', 'Chrome')} ouvindo em http://127.0.0.1:{CDP_PORT}")
            print("Confira na janela que abriu se o LinkedIn está logado (se pedir login, entre UMA vez;")
            print("isso fica salvo nessa pasta de depuração).")
            print("\nAgora rode:  python linkedin_jobs.py")
            return
        time.sleep(0.5)
    raise SystemExit("A porta 9222 não abriu. Feche todo o Chrome e tente de novo; "
                     "se o Chrome fechar sozinho, rode com --no-sandbox.")


def status() -> None:
    v = port_up()
    if not v:
        print(f":{CDP_PORT} fechada — rode: python launch_chrome.py")
        return
    print(f"{v.get('Browser')} em :{CDP_PORT}")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2) as r:
            for t in json.loads(r.read().decode("utf-8")):
                if t.get("type") == "page":
                    print("  -", (t.get("title") or "")[:70], "|", (t.get("url") or "")[:80])
    except Exception:
        pass


def clean() -> None:
    if port_up():
        raise SystemExit("Feche a janela do Chrome de depuração antes de limpar (porta 9222 ativa).")
    if DST_PROFILE.exists():
        shutil.rmtree(DST_PROFILE, ignore_errors=True)
        print("removido:", DST_PROFILE)
    else:
        print("nada para remover:", DST_PROFILE)


def main() -> int:
    global DST_PROFILE
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="recopia os cookies do perfil padrão")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--profile-dir", default=str(DST_PROFILE), help="onde fica a cópia do perfil")
    ap.add_argument("--fresh", action="store_true", help="recria a pasta do zero")
    ap.add_argument("--no-copy", action="store_true", help="não copia cookies: perfil vazio (login manual)")
    ap.add_argument("--no-sandbox", action="store_true",
                    help="abre o Chrome com --no-sandbox (use só se ele fechar sozinho no seu ambiente)")
    args = ap.parse_args()

    DST_PROFILE = Path(args.profile_dir)
    if args.status:
        status()
    elif args.clean:
        clean()
    else:
        launch(DST_PROFILE, fresh=args.fresh, copy=not args.no_copy, no_sandbox=args.no_sandbox)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
