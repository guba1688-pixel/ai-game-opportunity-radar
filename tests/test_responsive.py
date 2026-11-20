from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResponsiveLayoutTests(unittest.TestCase):
    def test_responsive_stylesheet_is_loaded(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/responsive.css"', html)

    def test_desktop_viewport_contract_is_present(self):
        css = (ROOT / "static" / "responsive.css").read_text(encoding="utf-8")
        for breakpoint in ("1359px", "1360px", "1599px", "1600px", "1840px", "2200px"):
            self.assertIn(breakpoint, css)
        self.assertIn("max-width: none", css)
        self.assertIn("overflow-x: hidden", css)

    def test_large_desktop_uses_three_card_columns(self):
        css = (ROOT / "static" / "responsive.css").read_text(encoding="utf-8")
        large_rule = css.split("@media (min-width: 1840px)", 1)[1]
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", large_rule)

    def test_hidden_permission_controls_cannot_be_overridden(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "permissions.css").read_text(encoding="utf-8")
        self.assertIn('href="/permissions.css"', html)
        self.assertIn("display: none !important", css)


if __name__ == "__main__":
    unittest.main()
