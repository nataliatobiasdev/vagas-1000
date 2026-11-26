"""O painel calcula o match sem reescrever banco, histórico ou avaliações originais."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper import dashboard, db
from scraper.models import Job


class MatchDashboardTests(unittest.TestCase):
    def test_projection_preserves_database_and_exposes_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / 'db.sqlite')
            job = Job('acme', 'Acme', 'gupy', 'Senior Salesforce Developer',
                      location='Brazil', job_id='1',
                      description=('Obrigatórios:\nExperiência obrigatória com Apex.\n'
                                   'Diferenciais:\nMarketing Cloud.\n' + 'Desenvolvimento e integração. ' * 20),
                      score=99, verdict='ELIGIBLE', reasons=['avaliação anterior'])
            db.save_run(conn, [job], {'acme': {'ok': True, 'count': 1}})
            before = tuple(conn.execute('select score, verdict, reasons from jobs').fetchone())
            profile = Path(__file__).resolve().parents[1] / 'config' / 'match_profile.json'
            with patch('scraper.dashboard.paths.config_file', return_value=profile):
                projection = dashboard.collect(conn)
            after = tuple(conn.execute('select score, verdict, reasons from jobs').fetchone())
            self.assertEqual(before, after)
            self.assertIn('match_category', projection['jobs'][0])
            reasons = projection['records'][0]['reasons']
            self.assertTrue(any('não é chance' in r for r in reasons))
            self.assertTrue(any('Apex' in r for r in reasons))
            conn.close()

    def test_cache_reuses_result_and_invalidates_changed_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / 'db.sqlite')
            job = Job('acme', 'Acme', 'gupy', 'Salesforce Developer', location='Brazil',
                      job_id='1', description='Apex LWC ' * 40)
            db.save_run(conn, [job], {'acme': {'ok': True, 'count': 1}})
            profile = Path(__file__).resolve().parents[1] / 'config' / 'match_profile.json'
            cache = {}
            with patch('scraper.dashboard.paths.config_file', return_value=profile):
                dashboard.collect(conn, cache)
                with patch('scraper.dashboard.assess', side_effect=AssertionError('cache não utilizado')):
                    dashboard.collect(conn, cache)
                conn.execute("update jobs set description='novo texto' where job_key='acme:1'")
                with patch('scraper.dashboard.assess', wraps=dashboard.assess) as matcher:
                    dashboard.collect(conn, cache)
                    matcher.assert_called_once()
            self.assertEqual(len(cache), 1)
            conn.close()
