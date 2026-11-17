# -*- mode: python ; coding: utf-8 -*-
# Empacota o vagas1000 em uma pasta autocontida (dist/vagas1000/vagas1000.exe), sem precisar de Python.
# Uso: pyinstaller vagas1000.spec --noconfirm   (o instalador NSIS é montado depois, em installer/)
from PyInstaller.utils.hooks import collect_all

selenium_datas, selenium_bins, selenium_hidden = collect_all("selenium")   # inclui o selenium-manager.exe
# Painel em janela própria (WebView2): pywebview + pythonnet (clr_loader) trazem DLLs que o PyInstaller não acha sozinho
wv = [collect_all(m) for m in ("webview", "pythonnet", "clr_loader")]
wv_datas = [d for x in wv for d in x[0]]
wv_bins = [b for x in wv for b in x[1]]
wv_hidden = [h for x in wv for h in x[2]] + ["clr", "proxy_tools", "bottle"]

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=selenium_bins + wv_bins,
    datas=[
        ("config/*.json", "config"),                       # padrões copiados para %APPDATA%\vagas1000 na 1ª execução
        ("scraper/templates/dashboard.html", "scraper/templates"),
        ("assets/fonts/*", "assets/fonts"),
        ("assets/icon.ico", "assets"),
    ] + selenium_datas + wv_datas,
    hiddenimports=["main"] + selenium_hidden + wv_hidden,             # `app.py --scrape` importa main.py em tempo de execução
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
