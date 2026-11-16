"""Criação do Chrome via Selenium 4 (o Selenium Manager baixa o chromedriver compatível sozinho)."""
from __future__ import annotations

from pathlib import Path

from . import paths


def make_driver(headless: bool = True, user_data_dir: str | None = None):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--lang=pt-BR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    # Perfil próprio dentro da pasta de dados: o chromedriver não depende do %TEMP% (que pode estar bloqueado
    # em terminais restritos: "cannot create temp dir for user data dir") e o seu Chrome pessoal fica intocado.
    profile = user_data_dir or str(paths.HOME / ".chrome-profile")
    Path(profile).mkdir(parents=True, exist_ok=True)
    opts.add_argument(f"--user-data-dir={profile}")
    # TEMP/TMP próprios para o chromedriver e o Chrome: sem isso, em terminais com %TEMP% bloqueado o Chrome
    # falha com "cannot create temp dir for ..." (visto em logs/scraper.log).
    import os
    from selenium.webdriver.chrome.service import Service
    tmp = paths.HOME / ".chrome-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TEMP": str(tmp), "TMP": str(tmp)}
    drv = webdriver.Chrome(options=opts, service=Service(env=env))   # Selenium Manager resolve o chromedriver
    drv.set_page_load_timeout(45)
    return drv


def session_alive(driver) -> bool:
    """A sessão do WebDriver ainda tem uma janela utilizável?

    Falso quando a janela controlada foi fechada (NoSuchWindowException) ou o Chrome morreu
    (InvalidSessionIdException / chrome not reachable). Nunca levanta: é só um teste.
    """
    try:
        return bool(driver.window_handles)
    except Exception:
        return False


def quit_driver(driver) -> None:
    """Encerra o Chrome sem travar quando a sessão já morreu.

    driver.quit() numa sessão morta repete requisições HTTP por ~12 s (e polui o log); nesse caso
    basta parar o chromedriver, que encerra o navegador que ele iniciou.
    """
    try:
        if session_alive(driver):
            driver.quit()
        else:
            driver.service.stop()
    except Exception:
        pass
