import tempfile
from pathlib import Path
import unittest

from radar.db import Repository
from radar.scoring import DIMENSIONS
from radar.service import OpportunityService, ValidationError
from radar.adapters.base import Signal


def payload(title="测试机会"):
    return {"title":title,"sector":"ai_game","status":"candidate","pain":"明确痛点","target_users":"目标团队","product_solution":"可测试方案","market_evidence":["演示证据"],"competitors":["竞品 A"],"pricing":"订阅","acquisition":"定向试点","mvp":"最小闭环","team_size":2,"budget_cny":50000,"cycle_weeks":4,"risks":["样本不足"],"validation_action":"访谈五名用户","is_demo":True,"score_rationale":"测试","scores":{key:3 for key in DIMENSIONS}}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "radar.db"
        self.repo = Repository(self.db_path)
        self.service = OpportunityService(self.repo)
        self.service.bootstrap()

    def tearDown(self):
        self.temp.cleanup()

    def test_bootstrap_marks_demo_and_deduplicates(self):
        signals = self.repo.list_signals()
        self.assertEqual(4, len(signals))
        self.assertTrue(all(row["is_demo"] == 1 and row["evidence_type"] == "demo" for row in signals))
        result = self.service.collect()
        self.assertEqual(0, result["inserted"])
        self.assertEqual(4, result["received"])

    def test_v2_business_seed_and_classification(self):
        rows = self.repo.list_opportunities()
        business = [row for row in rows if row["opportunity_type"] == "business"]
        self.assertGreaterEqual(len(business), 12)
        self.assertTrue(all(row["is_demo"] for row in rows))
        self.assertTrue(all(len(row["stage_gates"]) == 7 for row in rows))
        radar = next(row for row in rows if row["seed_key"] == "internal-radar")
        npc = next(row for row in rows if row["seed_key"] == "observe-ai-npc")
        self.assertEqual("internal_tool", radar["opportunity_type"])
        self.assertEqual("observation", npc["opportunity_type"])
        self.assertEqual("hold", npc["decision_status"])
        self.assertFalse(any(row["title"] == "AI NPC 垂直原型验证服务" and row["opportunity_type"] == "business" for row in rows))

    def test_bootstrap_is_idempotent_and_does_not_overwrite(self):
        item = next(row for row in self.repo.list_opportunities() if row["seed_key"] == "regional-agency")
        changed = dict(item); changed["owner"] = "用户自定义负责人"
        self.service.update_opportunity(item["id"], changed, "analyst")
        audit_before = len(self.repo.audit_logs(1000))
        self.service.bootstrap()
        audit_after = len(self.repo.audit_logs(1000))
        self.assertEqual(audit_before, audit_after)
        self.assertEqual("用户自定义负责人", self.repo.get_opportunity(item["id"])["owner"])

    def test_company_profile_persists(self):
        profile = self.repo.get_company_profile(); profile["company_name"] = "测试发行公司"
        updated = self.service.update_profile(profile, "admin")
        self.assertEqual("测试发行公司", updated["company_name"])
        self.assertEqual("测试发行公司", Repository(self.db_path).get_company_profile()["company_name"])

    def test_v2_filters(self):
        rows = self.repo.list_opportunities(region="东南亚", asset="heavy", decision="recommend_now")
        self.assertTrue(rows)
        self.assertTrue(all("东南亚" in row["regions"] and row["asset_level"] == "heavy" for row in rows))
        rows = self.repo.list_opportunities(genre="休闲", stage="test_30d", min_fit="70")
        self.assertTrue(rows)
        self.assertTrue(all("休闲" in row["genres"] and row["validation_stage"] == "test_30d" and row["total_score"] >= 70 for row in rows))

    def test_crud_persists_and_audits(self):
        before = self.repo.dashboard()["total"]
        created = self.service.create_opportunity(payload(), "analyst")
        self.assertEqual(before + 1, self.repo.dashboard()["total"])
        updated_payload = payload("已修改机会")
        updated_payload["budget_cny"] = 250000
        updated = self.service.update_opportunity(created["id"], updated_payload, "analyst")
        self.assertEqual("L3", updated["investment_level"])
        self.assertEqual("heavy", updated["asset_pool"])
        self.assertTrue(self.repo.delete_opportunity(created["id"], "admin"))
        self.assertEqual(before, self.repo.dashboard()["total"])
        actions = [row["action"] for row in self.repo.audit_logs()[:3]]
        self.assertEqual(["delete", "update", "create"], actions)

    def test_required_fields(self):
        data = payload(); data["pain"] = ""
        with self.assertRaises(ValidationError):
            self.service.create_opportunity(data)

    def test_exports_keep_demo_and_evidence(self):
        rows = self.repo.list_opportunities()
        self.assertIn("is_demo", self.service.export_csv(rows).splitlines()[0])
        markdown = self.service.export_markdown(rows)
        self.assertIn("演示数据", markdown)
        self.assertIn("市场证据", markdown)

    def test_signal_rejects_unsafe_source_url(self):
        signal = Signal("x", "x", "ai", "x", "javascript:alert(1)", "x", "x", "x", "x", "x", "demo", "E", True)
        with self.assertRaises(ValueError):
            signal.normalized()


if __name__ == "__main__":
    unittest.main()
