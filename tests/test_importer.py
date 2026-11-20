import tempfile
from pathlib import Path
import unittest

from radar.db import Repository
from radar.importer import parse_import
from radar.service import OpportunityService


class ImporterTests(unittest.TestCase):
    def test_csv_import_is_traceable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Repository(Path(temp)/"radar.db")
            service=OpportunityService(repo)
            service.bootstrap()
            payload={"format":"csv","source_name":"测试报告","source_ref":"report-20260903.csv","sector":"ai_game","observed_at":"2026-09-03","evidence_type":"third_party_estimate","confidence_grade":"C","is_estimate":True,"content":"title,summary,region\n机会A,这是估算摘要,中国\n机会B,这是第二条摘要,全球\n"}
            first=service.import_signals(payload)
            second=service.import_signals(payload)
            self.assertEqual(2,first["inserted"])
            self.assertEqual(0,second["inserted"])
            self.assertEqual(2,second["duplicates"])
            self.assertTrue(Path(first["backup_path"]).is_file())
            imported=repo.list_signals(source_type="manual_import")
            self.assertEqual(2,len(imported))
            self.assertTrue(all(row["source_ref"]=="report-20260903.csv" and row["is_estimate"]==1 for row in imported))
            opportunity=repo.list_opportunities()[0]
            linked=service.link_evidence(opportunity["id"],{"signal_id":imported[0]["id"],"relation_type":"estimate","notes":"仅作估算证据"})
            self.assertEqual("linked",linked["evidence_trace_status"])
            self.assertEqual("estimate",linked["evidence_links"][0]["relation_type"])
            source=next(row for row in repo.sources() if row["source_type"]=="manual_import")
            self.assertEqual("no_change",source["health_status"])

    def test_json_reports_invalid_rows_without_hiding_valid_rows(self):
        rows,errors=parse_import({"format":"json","source_name":"JSON样例","source_ref":"sample.json","observed_at":"2026-09-03","content":'[{"title":"有效","summary":"摘要"},{"title":"缺摘要"}]'})
        self.assertEqual(1,len(rows))
        self.assertEqual(1,len(errors))
        self.assertEqual("manual_import",rows[0]["source_type"])

    def test_html_snapshot_preserves_file_and_date(self):
        rows,errors=parse_import({"format":"html","source_name":"HTML样例","source_ref":"AI市场机会分析报告-20260903.html","observed_at":"2026-09-03","content":"<html><title>报告</title><h2>市场机会</h2><p>该结论属于估算。</p></html>"})
        self.assertFalse(errors)
        self.assertEqual("市场机会",rows[0]["title"])
        self.assertEqual("2026-09-03",rows[0]["observed_period"])
        self.assertEqual("AI市场机会分析报告-20260903.html",rows[0]["source_ref"])


if __name__=="__main__":
    unittest.main()
