"""scripts/release_notes.py: as notas da Release saem do CHANGELOG em UTF-8, mesmo com a saída redirecionada no Windows."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.version import __version__  # noqa: E402


class ReleaseNotesTests(unittest.TestCase):
    def run_script(self, version: str, encoding: str):
        env = {**os.environ, "PYTHONIOENCODING": encoding}          # simula o stdout redirecionado do runner do Windows
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "release_notes.py"), version],
                              capture_output=True, env=env, cwd=ROOT)

    def test_current_version_notes_survive_a_cp1252_stdout(self):
        """O CHANGELOG usa "✕", "≥", "·" e acentos; o script não pode depender do cp1252 do console."""
        r = self.run_script(__version__, "cp1252")
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        text = r.stdout.decode("utf-8")                              # sempre UTF-8, qualquer que seja o console
        self.assertTrue(text.strip())
        self.assertNotIn("�", text)

    def test_unknown_version_fails_with_a_clear_message(self):
        r = self.run_script("0.0.0", "utf-8")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("0.0.0", r.stderr.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
