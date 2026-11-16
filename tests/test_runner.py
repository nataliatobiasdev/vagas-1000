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
