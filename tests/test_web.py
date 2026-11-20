import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from http.server import ThreadingHTTPServer
from radar.db import Repository
from radar.service import OpportunityService
from radar.web import make_handler
from test_service import payload


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        service = OpportunityService(Repository(Path(cls.temp.name) / "web.db"))
        service.bootstrap()
        root = Path(__file__).resolve().parents[1]
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root, service))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=3); cls.temp.cleanup()

    def get_json(self, path, role="admin"):
        with urlopen(Request(self.base + path, headers={"X-Role": role}), timeout=3) as response:
            return response.status, json.load(response)

    def test_health_and_filters(self):
        status, health = self.get_json("/api/health")
        self.assertEqual(200, status); self.assertEqual("ok", health["status"])
        _, rows = self.get_json("/api/opportunities?sector=ai")
        self.assertTrue(rows); self.assertTrue(all(row["sector"] == "ai" for row in rows))

    def test_update_rules_expose_runtime_truth(self):
        status, rules = self.get_json("/api/update-rules", "viewer")
        self.assertEqual(200, status)
        self.assertEqual("1.0.0", rules["rules_version"])
        self.assertEqual(5, len(rules["schedules"]))
        self.assertEqual(8, len(rules["content_dimensions"]))
        self.assertEqual(0, rules["runtime"]["live_sources"])
        self.assertFalse(rules["runtime"]["semantic_dedup_active"])
        self.assertFalse(rules["runtime"]["ceiling_model_active"])

    def test_viewer_cannot_collect(self):
        request = Request(self.base + "/api/collect", data=b"{}", method="POST", headers={"X-Role":"viewer","Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(403, caught.exception.code)

    def test_import_requires_manage_permission_and_persists_source(self):
        body={"format":"json","source_name":"接口测试","source_ref":"api-sample.json","observed_at":"2026-09-03","content":'[{"title":"接口导入","summary":"可追溯摘要"}]'}
        data=json.dumps(body,ensure_ascii=False).encode("utf-8")
        request=Request(self.base+"/api/import",data=data,method="POST",headers={"X-Role":"viewer","Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request,timeout=3)
        self.assertEqual(403,caught.exception.code)
        request=Request(self.base+"/api/import",data=data,method="POST",headers={"X-Role":"admin","Content-Type":"application/json"})
        with urlopen(request,timeout=3) as response:
            result=json.load(response)
        self.assertEqual(1,result["inserted"])
        _,sources=self.get_json("/api/sources","viewer")
        self.assertTrue(any(row["source_type"]=="manual_import" for row in sources))

    def test_static_page_and_export(self):
        with urlopen(self.base + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
        self.assertIn("AI × 游戏机会市场雷达", html)
        self.assertIn("综合面板", html)
        self.assertIn("手动提交资讯", html)
        self.assertIn("/api/v1/intelligence", html)
        self.assertIn('class="ghost compact-api" data-jump="automation"', html)
        self.assertIn('id="game-radar-points"', html)
        self.assertIn('id="home-focus"', html)
        self.assertIn('id="home-game-signals"', html)
        self.assertIn('id="home-ai-signals"', html)
        self.assertIn('id="home-risks"', html)
        self.assertIn('id="deepseek-form"', html)
        self.assertIn('/api.deepseek.com', html)
        with urlopen(Request(self.base + "/api/export.csv", headers={"X-Role":"analyst"}), timeout=3) as response:
            csv_text = response.read().decode("utf-8-sig")
        self.assertIn("validation_action", csv_text.splitlines()[0])

    def test_manual_intelligence_api_deduplicates_and_updates_dashboard(self):
        body={"title":"游戏资讯接口探针","summary":"同一条资讯重复写入时只能新增一次","source_name":"人工测试","source_url":"https://example.com/news/1","observed_at":"2026-11-19","sector":"game","region":"全球","evidence_type":"third_party_estimate","confidence_grade":"B"}
        data=json.dumps(body,ensure_ascii=False).encode("utf-8")
        for expected in (1,0):
            request=Request(self.base+"/api/intelligence",data=data,method="POST",headers={"X-Role":"analyst","Content-Type":"application/json"})
            with urlopen(request,timeout=3) as response:
                result=json.load(response)
            self.assertEqual(expected,result["inserted"])
        _,dashboard=self.get_json("/api/intelligence-dashboard","viewer")
        self.assertGreaterEqual(dashboard["signals_total"],1)
        self.assertGreaterEqual(dashboard["manual_count"],1)
        _,rows=self.get_json("/api/v1/intelligence?sector=game","viewer")
        self.assertTrue(any(row["title"]=="游戏资讯接口探针" for row in rows))

    def test_intelligence_rejects_unsafe_source_url(self):
        body={"title":"不安全链接","summary":"拒绝非网页来源协议","source_name":"人工测试","source_url":"javascript:alert(1)","observed_at":"2026-11-19"}
        request=Request(self.base+"/api/intelligence",data=json.dumps(body,ensure_ascii=False).encode("utf-8"),method="POST",headers={"X-Role":"analyst","Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request,timeout=3)
        self.assertEqual(400,caught.exception.code)

    def test_http_crud_and_audit(self):
        data = json.dumps(payload("HTTP CRUD 探针"), ensure_ascii=False).encode("utf-8")
        request = Request(self.base + "/api/opportunities", data=data, method="POST", headers={"X-Role":"analyst","Content-Type":"application/json"})
        with urlopen(request, timeout=3) as response:
            created = json.load(response)
        update = payload("HTTP CRUD 探针已更新"); update["budget_30d"] = 180000; update["budget_scale"] = 300000
        request = Request(self.base + f"/api/opportunities/{created['id']}", data=json.dumps(update,ensure_ascii=False).encode("utf-8"), method="PUT", headers={"X-Role":"analyst","Content-Type":"application/json"})
        with urlopen(request, timeout=3) as response:
            changed = json.load(response)
        self.assertEqual("medium", changed["asset_level"])
        request = Request(self.base + f"/api/opportunities/{created['id']}", method="DELETE", headers={"X-Role":"admin"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(created["id"], json.load(response)["deleted"])
        _, audit = self.get_json("/api/audit", "admin")
        actions = [row["action"] for row in audit[:3]]
        self.assertEqual(["delete","update","create"], actions)


if __name__ == "__main__":
    unittest.main()
