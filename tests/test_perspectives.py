from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PerspectiveExperienceTests(unittest.TestCase):
    def test_perspective_assets_are_loaded(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/perspectives.css"', html)
        self.assertIn('src="/perspectives.js"', html)

    def test_all_analysis_lenses_are_present(self):
        js = (ROOT / "static" / "perspectives.js").read_text(encoding="utf-8")
        for lens in ("overview", "market", "industry", "product", "channel", "business", "competition", "capability", "risk"):
            self.assertIn(f"{lens}:", js)
        self.assertIn("state.lens", js)
        self.assertIn("localStorage.setItem('radar-lens'", js)

    def test_role_is_not_used_to_choose_perspective(self):
        js = (ROOT / "static" / "perspectives.js").read_text(encoding="utf-8")
        self.assertNotIn("state.role", js)

    def test_evidence_boundary_is_explicit(self):
        js = (ROOT / "static" / "perspectives.js").read_text(encoding="utf-8")
        self.assertIn("证据分级 · 决策需复核", js)
        self.assertIn("带“演示数据”的旧项目仅用于展示流程", js)
        self.assertIn("不构成业绩承诺", js)


if __name__ == "__main__":
    unittest.main()
