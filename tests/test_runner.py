import unittest

from scraper import runner


class FakeService:
    def __init__(self, owner):
        self.owner = owner

    def stop(self):
        self.owner.quit_called = True


class FakeDriver:
    """Sessão de mentira: só o que o runner usa (window_handles, quit e service.stop)."""

    def __init__(self, alive=True):
        self.alive = alive
        self.quit_called = False
        self.service = FakeService(self)

    @property
    def window_handles(self):
        if not self.alive:
            raise RuntimeError("no such window: target window already closed")
        return ["handle"]

    def quit(self):
        self.quit_called = True


class CollectOneTests(unittest.TestCase):
    def test_retries_once_with_new_driver_when_session_dies(self):
        dead, fresh = FakeDriver(alive=False), FakeDriver()
        seen = []

        def collector(driver, cfg):
            seen.append(driver)
            if driver is dead:
                raise RuntimeError("no such window")
            return ["vaga"]

        jobs, driver, err = runner.collect_one(collector, dead, {"company_id": "x"}, lambda: fresh)
        self.assertEqual(jobs, ["vaga"])
        self.assertIs(driver, fresh)
        self.assertIsNone(err)
        self.assertTrue(dead.quit_called)
        self.assertEqual(seen, [dead, fresh])       # tentou de novo, com driver novo

    def test_does_not_retry_when_error_is_not_a_dead_session(self):
        alive = FakeDriver()

        def collector(driver, cfg):
            raise ValueError("seletor quebrou")

        jobs, driver, err = runner.collect_one(collector, alive, {"company_id": "x"}, FakeDriver)
        self.assertIsNone(jobs)
        self.assertIs(driver, alive)
        self.assertIsInstance(err, ValueError)
        self.assertFalse(alive.quit_called)

    def test_does_not_retry_without_factory(self):
        dead = FakeDriver(alive=False)

        def collector(driver, cfg):
            raise RuntimeError("boom")

        jobs, driver, err = runner.collect_one(collector, dead, {"company_id": "x"})
        self.assertIsNone(jobs)
        self.assertIs(driver, dead)
        self.assertIsInstance(err, RuntimeError)

    def test_gives_up_after_one_retry(self):
        dead1, dead2 = FakeDriver(alive=False), FakeDriver(alive=False)

        def collector(driver, cfg):
            raise RuntimeError("boom")

        jobs, driver, err = runner.collect_one(collector, dead1, {"company_id": "x"}, lambda: dead2)
        self.assertIsNone(jobs)
        self.assertIs(driver, dead2)
        self.assertIsInstance(err, RuntimeError)
        self.assertTrue(dead1.quit_called)


if __name__ == "__main__":
    unittest.main()


class LazyChromeTests(unittest.TestCase):
    """O Chrome só deve abrir quando uma empresa realmente precisa dele."""

    def _run(self, adapters, factory):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        cfg = {"companies": [{"company_id": f"c{i}", "name": f"C{i}", "adapter": a, "board_url": "x"}
                             for i, a in enumerate(adapters)]}
        profile = json.loads((Path(__file__).resolve().parent.parent / "config" / "profile.json")
                             .read_text(encoding="utf-8"))
        calls = []

        def fake(driver, c):
            calls.append((c["adapter"], driver))
            return []

        fakes = {a: fake for a in set(adapters)}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(runner, "load_json", side_effect=lambda p: cfg if "companies" in str(p) else profile), \
                mock.patch.object(runner, "COLLECTORS", fakes), \
                mock.patch.object(runner.db, "connect", side_effect=AssertionError("não deveria gravar")), \
                mock.patch.object(runner.db, "save_run"):
            try:
                runner.run(None, out_dir=Path(tmp), driver_factory=factory)
            except AssertionError:
                pass
        return calls

    def test_api_only_run_never_opens_chrome(self):
        opened = []
        calls = self._run(["gupy", "greenhouse_api"], lambda: opened.append(1))
        self.assertEqual(opened, [])
        self.assertEqual(len(calls), 2)

    def test_browser_company_opens_chrome_once(self):
        opened = []

        def factory():
            opened.append(1)
            return FakeDriver()

        calls = self._run(["gupy", "stone_portal"], factory)
        self.assertEqual(len(opened), 1)
        self.assertIsNotNone(calls[1][1])

    def test_missing_chrome_fails_only_that_company(self):
        def factory():
            raise RuntimeError("sem chrome")

        calls = self._run(["gupy", "stone_portal"], factory)
        self.assertEqual([a for a, _ in calls], ["gupy"])      # a Stone falhou, a Gupy rodou


class AppPollRegressionTests(unittest.TestCase):
    def test_flush_results_with_errors_key_does_not_raise(self):
        # regressão: _flush_results referenciava `errors` sem defini-la (NameError a cada poll)
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        try:
            import tkinter as tk
            import app
            root = tk.Tk()
        except Exception as e:          # sem display/tk no ambiente
            self.skipTest(f"tkinter indisponível: {e}")
        root.withdraw()
        a = app.Vagas1000App(root)
        a._flush_results({"results": [{"name": "A", "ok": False, "count": 0, "seconds": 1}],
                          "errors": [{"name": "A", "error": "boom"}]})
        root.destroy()
