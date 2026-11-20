from pathlib import Path
import unittest


class CeoDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.script = (root / "static" / "intelligence.js").read_text(encoding="utf-8")
        cls.styles = (root / "static" / "intelligence.css").read_text(encoding="utf-8")

    def test_first_view_is_decision_oriented(self):
        for text in ("30天内截止", "待决策事项", "老板本周要拍板", "业务影响", "建议决策", "负责人"):
            self.assertIn(text, self.script)

    def test_deadline_and_week_windows_are_computed(self):
        self.assertIn("currentWeekWindow", self.script)
        self.assertIn("decisionMeta", self.script)
        self.assertIn("metric_value", self.script)

    def test_decision_cards_have_distinct_urgency_styles(self):
        for css_class in (".ceo-decision-card", ".deadline-badge", ".decision-lines"):
            self.assertIn(css_class, self.styles)


if __name__ == "__main__":
    unittest.main()
