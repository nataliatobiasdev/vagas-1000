import unittest

from scraper import gfx, theme as T


class GfxTests(unittest.TestCase):
    def test_surface_has_transparent_rounded_corners_and_solid_center(self):
        img = gfx.surface(120, 60, 16, T.PANEL, T.BORDER)
        self.assertEqual(img.size, (120, 60))
        self.assertEqual(img.getpixel((0, 0))[3], 0)               # canto realmente transparente
        self.assertEqual(img.getpixel((60, 30))[3], 255)           # miolo opaco

    def test_large_surface_nine_slice_matches_direct_paint(self):
        big = gfx.surface(400, 200, 16, T.PANEL, T.BORDER, shadow=(10, 3, 0.4), pad=12)
        direct = gfx._surface(400, 200, 16, T.PANEL, T.BORDER, 0.07, (10, 3, 0.4), None, False, 12)
        self.assertEqual(big.size, direct.size)
        for pt in ((0, 0), (40, 40), (200, 100), (390, 20), (200, 8), (12, 100)):
            a, b = big.getpixel(pt), direct.getpixel(pt)
            self.assertTrue(all(abs(x - y) <= 3 for x, y in zip(a, b)), (pt, a, b))

    def test_surface_cache_returns_independent_copies(self):
        a = gfx.surface(50, 30, 8, T.PANEL, T.BORDER)
        a.putpixel((25, 15), (255, 0, 0, 255))
        b = gfx.surface(50, 30, 8, T.PANEL, T.BORDER)
        self.assertNotEqual(b.getpixel((25, 15)), (255, 0, 0, 255))

    def test_every_icon_draws_something(self):
        for name in gfx.ICONS:
            ic = gfx.icon(name, 24, T.FG)
            self.assertEqual(ic.size, (24, 24))
            self.assertGreater(ic.getchannel("A").getbbox()[2], 0, name)

    def test_capsule_and_atmosphere(self):
        self.assertEqual(gfx.capsule(80, 8, T.SUBTLE).getpixel((0, 0))[3], 0)
        self.assertEqual(gfx.capsule(80, 8, gradient=(T.ACCENT, T.TEAL)).size, (80, 8))
        bg = gfx.atmosphere(300, 200)
        self.assertEqual(bg.size, (300, 200))
        self.assertEqual(bg.getpixel((150, 100))[3], 255)

    def test_over_composites_onto_scene(self):
        scene = gfx.atmosphere(100, 100)
        sprite = gfx.surface(20, 20, 6, T.ACCENT, None)
        out = gfx.over(scene, sprite, 10, 10)
        self.assertEqual(out.size, (20, 20))
        self.assertEqual(out.getpixel((10, 10))[3], 255)


if __name__ == "__main__":
    unittest.main()
