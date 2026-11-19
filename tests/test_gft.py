import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scraper.collectors import collect_gft, collect_gft_rss
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

    @patch('scraper.collectors._get_text')
    def test_official_feed_reads_description_and_stable_id(self, get):
        get.return_value = '''<rss><channel><item><title>Salesforce Sênior (Barueri, BR)</title><link>https://jobs.gft.com/job/example/123/?utm_source=rss</link><description>&lt;p&gt;Apex e LWC&lt;/p&gt;</description><pubDate>Thu, 19 Nov 2026 02:00:00 GMT</pubDate></item></channel></rss>'''
        jobs = collect_gft_rss(None, {'company_id':'gft_rss','name':'GFT feed','board_url':'https://jobs.gft.com/feed'})
        self.assertEqual(jobs[0].job_id, '123')
        self.assertEqual(jobs[0].url, 'https://jobs.gft.com/job/example/123/')
        self.assertIn('Apex', jobs[0].description)
        self.assertEqual(jobs[0].location, 'Barueri, BR')

    def test_partial_feed_never_closes_missing_vacancies(self):
        from scraper import db
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / 'db.sqlite')
            config = [{'company_id':'gft_rss','name':'GFT feed','adapter':'gft_rss','board_url':'https://jobs.gft.com/feed','partial_feed':True}]
            job1 = Job('gft_rss','GFT','gft_rss','Salesforce',job_id='1')
            job2 = Job('gft_rss','GFT','gft_rss','Developer',job_id='2')
            db.save_run(conn, [job1], {'gft_rss':{'ok':True,'count':1}}, config)
            db.save_run(conn, [job2], {'gft_rss':{'ok':True,'count':1}}, config)
            self.assertEqual(conn.execute("select status from jobs where job_key='gft_rss:1'").fetchone()[0], 'open')
            conn.close()

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

    def test_feed_migrates_from_170_once(self):
        from scraper import paths
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, home = base / 'bundle', base / 'home'
            (bundle / 'config').mkdir(parents=True)
            (home / 'config').mkdir(parents=True)
            feed = {'company_id':'gft_rss','name':'GFT feed','partial_feed':True}
            (bundle / 'config' / 'companies.json').write_text(json.dumps({'companies':[feed]}), encoding='utf8')
            dest = home / 'config' / 'companies.json'
            dest.write_text(json.dumps({'companies':[{'company_id':'gft','name':'Personalizado'}], '_migrations':['fontes_salesforce_20261119']}), encoding='utf8')
            with patch.object(paths, 'BUNDLE', bundle), patch.object(paths, 'CONFIG', home / 'config'):
                paths.ensure_config()
                paths.ensure_config()
                result = json.loads(dest.read_text(encoding='utf8'))
                self.assertEqual([c['company_id'] for c in result['companies']], ['gft', 'gft_rss'])
                self.assertEqual(result['companies'][0]['name'], 'Personalizado')
                self.assertTrue((home / 'config' / 'companies.pre-gft-feed-20261119.json').exists())


if __name__ == '__main__':
    unittest.main()
