import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UpdateRuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((ROOT / "config" / "update_rules.json").read_text(encoding="utf-8"))

    def test_required_cadences_exist(self):
        identifiers = {item["id"] for item in self.rules["schedules"]}
        self.assertEqual({"fast_signals", "daily_digest", "opportunity_rescore", "weekly_review", "ceiling_refresh"}, identifiers)

    def test_four_layer_dedup_is_defined(self):
        self.assertEqual({"exact", "event_cluster", "opportunity_merge", "contradiction"}, set(self.rules["deduplication"]))
        self.assertIn("0.86", self.rules["deduplication"]["event_cluster"]["rule"])
        self.assertIn("0.82", self.rules["deduplication"]["opportunity_merge"]["rule"])

    def test_ceiling_model_requires_scenarios_and_confidence_gate(self):
        model = self.rules["ceiling_model"]
        self.assertEqual(["保守", "基准", "乐观"], model["scenarios"])
        self.assertIn("贡献现金", model["formula"])
        self.assertTrue(model["confidence_gate"])


if __name__ == "__main__":
    unittest.main()
