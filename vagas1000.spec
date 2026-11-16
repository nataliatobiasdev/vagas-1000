# -*- mode: python ; coding: utf-8 -*-
# Empacota o vagas1000 em uma pasta autocontida (dist/vagas1000/vagas1000.exe), sem precisar de Python.
# Uso: pyinstaller vagas1000.spec --noconfirm   (o instalador NSIS é montado depois, em installer/)
from PyInstaller.utils.hooks import collect_all

selenium_datas, selenium_bins, selenium_hidden = collect_all("selenium")   # inclui o selenium-manager.exe

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=selenium_bins,
    datas=[
        ("config/*.json", "config"),                       # padrões copiados para %APPDATA%\vagas1000 na 1ª execução
        ("scraper/templates/dashboard.html", "scraper/templates"),
        ("assets/fonts/*", "assets/fonts"),
        ("assets/icon.ico", "assets"),
    ] + selenium_datas,
    hiddenimports=["main"] + selenium_hidden,             # `app.py --scrape` importa main.py em tempo de execução
    excludes=["pytest", "unittest.mock", "fontTools", "brotli"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vagas1000",
    console=False,                                         # janela Tk, sem console
    icon="assets/icon.ico",
    version="installer/version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, name="vagas1000")
