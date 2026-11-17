import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from scraper.panel_window import Api, dashboard_path

class CamIntegrationTest(unittest.TestCase):
    def test_add_duplicate_and_full_payload(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'APPDATA': tmp}):
            path = Path(tmp) / 'CAM' / 'cam.db'
            path.parent.mkdir()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE vagas1000_inbox (job_key TEXT PRIMARY KEY, payload TEXT, added_at TEXT, application_id TEXT)')
            api = Api()
            api.get_raw = lambda key: {'original': 'conteúdo'}
            job = {'key': '123', 'title': 'Engenheira', 'company': 'Empresa'}
            self.assertEqual(api.cam_status('123')['status'], 'absent')
            self.assertEqual(api.add_to_cam('123', job, {'description': 'Detalhes'}), {'ok': True, 'already': False})
            self.assertEqual(api.cam_status('123')['status'], 'pending')
            self.assertEqual(api.add_to_cam('123', job, {}), {'ok': True, 'already': True})
            with closing(sqlite3.connect(path)) as db:
                rows = db.execute('SELECT payload FROM vagas1000_inbox').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0][0])['bruto']['original'], 'conteúdo')
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE vagas1000_inbox SET application_id='app1' WHERE job_key='123'")
            self.assertEqual(api.cam_status('123')['status'], 'applied')

    def test_missing_or_outdated_cam(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'APPDATA': tmp}):
            self.assertFalse(Api().add_to_cam('123', {'key': '123', 'title': 'Cargo', 'company': 'Empresa'}, {})['ok'])
            self.assertEqual(Api().cam_status('123')['status'], 'unavailable')

    def test_dashboard_is_not_rebuilt_on_every_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dashboard = out / 'dashboard.html'
            dashboard.write_text('<!-- cam-status-v2 -->', encoding='utf-8')
            with patch('scraper.panel_window.paths.OUT', out), patch('scraper.db.connect') as connect:
                self.assertEqual(dashboard_path(), dashboard)
                connect.assert_not_called()

if __name__ == '__main__':
    unittest.main()
