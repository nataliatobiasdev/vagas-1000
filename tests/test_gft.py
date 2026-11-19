import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scraper.collectors import collect_gft
from scraper.filtering import score_job
from scraper.models import Job


def page(number, total, rows, next_href=''):
    items = ''.join(f'<tr class="data-row"><td><a class="jobTitle-link" href="/job/x/{n}/">Salesforce {n}</a></td><td class="colLocation"><span class="jobLocation">São Paulo, BR</span></td><td><span class="jobShifttype">Remote</span></td></tr>' for n in rows)
    next_li = f'<li><a href="{next_href}">2</a></li>' if next_href else ''
    return f'<table>{items}</table><div class="pagination-bottom"><span class="paginationLabel">Resultados <b>{number}</b> de <b>{total}</b></span><ul><li><a class="current-page">1</a></li>{next_li}</ul></div>'


class GftTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'company_id':'gft','name':'GFT','board_url':'https://jobs.gft.com/go/brazil/4412501/', 'fetch_details':False}

    @patch('scraper.collectors._pause')
    @patch('scraper.collectors._get_text')
    def test_collects_all_pages_and_workplace(self, get, pause):
        get.side_effect = [page('1-1', 2, [1], '/page2'), page('2-2', 2, [2])]
        jobs = collect_gft(None, self.cfg)
        self.assertEqual([j.job_id for j in jobs], ['1','2'])
        self.assertEqual(jobs[0].workplace_type, 'remote')

    @patch('scraper.collectors._get_text')
    def test_incomplete_list_is_failure(self, get):
        get.return_value = page('1-1', 2, [1])
        with self.assertRaises(ValueError):
            collect_gft(None, self.cfg)

    def test_sales_cloud_is_not_sales_role(self):
        import json
        from pathlib import Path
        profile = json.loads((Path(__file__).parent.parent / 'config/profile.json').read_text(encoding='utf8'))
        job = Job('x','X','test','Desenvolvedor Salesforce Sales Cloud Sênior',location='Brasil')
        self.assertNotEqual(score_job(job, profile).verdict, 'BLOCKED')

    def test_existing_config_is_migrated_once_without_overwriting(self):
        from scraper import paths
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, home = base / 'bundle', base / 'home'
            (bundle / 'config').mkdir(parents=True)
            (home / 'config').mkdir(parents=True)
            (bundle / 'config' / 'companies.json').write_text(json.dumps({'companies':[{'company_id':'gft','name':'padrão'},{'company_id':'4mk','name':'4MK'}]}), encoding='utf8')
            dest = home / 'config' / 'companies.json'
            dest.write_text(json.dumps({'companies':[{'company_id':'gft','name':'personalizado'}]}), encoding='utf8')
            with patch.object(paths, 'BUNDLE', bundle), patch.object(paths, 'CONFIG', home / 'config'):
                paths.ensure_config()
                result = json.loads(dest.read_text(encoding='utf8'))
                self.assertEqual([c['name'] for c in result['companies']], ['personalizado','4MK'])
                result['companies'].pop()
                dest.write_text(json.dumps(result), encoding='utf8')
                paths.ensure_config()
                self.assertEqual(len(json.loads(dest.read_text(encoding='utf8'))['companies']), 1)


if __name__ == '__main__':
    unittest.main()
