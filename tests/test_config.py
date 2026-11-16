import json
import unittest
from pathlib import Path

from scraper.collectors import COLLECTORS


class ConfigTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent.parent / "config" / "companies.json"
        self.companies = json.loads(path.read_text(encoding="utf-8"))["companies"]

    def test_companies_are_complete_and_use_known_adapter(self):
        ids = [c["company_id"] for c in self.companies]
        self.assertEqual(len(ids), len(set(ids)), "company_id duplicado")
        self.assertGreaterEqual(len(ids), 6)
        for c in self.companies:
            for field in ("company_id", "name", "adapter", "board_url", "fetch_details", "composite_score"):
                self.assertIn(field, c, f"{c.get('company_id')} sem {field}")
            self.assertIn(c["adapter"], COLLECTORS, f"adaptador desconhecido: {c['adapter']}")

    def test_greenhouse_api_has_board_token(self):
        for c in self.companies:
            if c["adapter"] == "greenhouse_api":
                self.assertTrue(c.get("board_token"), f"{c['company_id']} sem board_token")


if __name__ == "__main__":
    unittest.main()
