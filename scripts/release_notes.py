"""Imprime a seção de uma versão do CHANGELOG.md (usado pelo release.yml como corpo da Release)."""
import re
import sys
from pathlib import Path

# Com a saída redirecionada (`> release-notes.md`) o Windows usa cp1252, que não tem "✕", "≥" etc.: sem isto o passo
# das notas da versão quebrava com UnicodeEncodeError e a Release não era publicada.
sys.stdout.reconfigure(encoding="utf-8")

version = sys.argv[1]
text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
m = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
if not m:
    sys.exit(f"CHANGELOG.md não tem a seção da versão {version}")
print(m.group(1).strip())
