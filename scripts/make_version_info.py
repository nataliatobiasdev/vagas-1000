"""Gera installer/version_info.txt (metadados do .exe: versão, empresa, nome) a partir de scraper/version.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ver = re.search(r'__version__ = "([^"]+)"', (ROOT / "scraper" / "version.py").read_text(encoding="utf-8")).group(1)
nums = [int(x) for x in ver.split(".")[:3]] + [0] * 4
t = (4 * "{}, ").format(*nums[:4]).rstrip(", ")
(ROOT / "installer" / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({t}), prodvers=({t}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'Natalia Tobias'),
      StringStruct('FileDescription', 'vagas1000'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'vagas1000'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Natalia Tobias'),
      StringStruct('OriginalFilename', 'vagas1000.exe'),
      StringStruct('ProductName', 'vagas1000'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
""", encoding="utf-8")
print("version_info.txt", ver)
