"""CSV、JSON 与本地 HTML 快照的可追溯信号导入。"""

from csv import DictReader
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
from urllib.parse import urlparse


SECTORS = {"ai", "game", "ai_game"}
EVIDENCE_TYPES = {"official", "third_party_estimate", "model_inference"}
GRADES = set("ABCDE")


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _date(value):
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text.replace("/", "-")):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"无法识别观察日期：{text}")


class SnapshotHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = ""
        self.buffer = []
        self.blocks = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if not self.skip and tag in {"title", "h1", "h2", "h3", "p", "li"}:
            self.tag = tag
            self.buffer = []

    def handle_data(self, data):
        if self.tag and not self.skip:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag == self.tag:
            text = " ".join("".join(self.buffer).split())
            if text:
                self.blocks.append((tag, text))
            self.tag = ""
            self.buffer = []


def _html_items(content):
    parser = SnapshotHTMLParser()
    parser.feed(content)
    document_title = next((text for tag, text in parser.blocks if tag in {"title", "h1"}), "本地 HTML 快照")
    headings = []
    current = None
    for tag, text in parser.blocks:
        if tag in {"h2", "h3"}:
            if current:
                headings.append(current)
            current = {"title": text, "parts": []}
        elif tag in {"p", "li"}:
            if current:
                current["parts"].append(text)
    if current:
        headings.append(current)
    items = [{"title": row["title"], "summary": "；".join(row["parts"])[:1600]} for row in headings if row["parts"]]
    if items:
        return items[:100]
    body = "；".join(text for tag, text in parser.blocks if tag in {"p", "li"})[:1600]
    return [{"title": document_title, "summary": body or "该 HTML 快照没有可提取的正文段落。"}]


def _raw_items(fmt, content):
    if fmt == "json":
        payload = json.loads(content)
        items = payload.get("items", []) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("JSON 顶层必须是数组，或包含 items 数组")
        return items
    if fmt == "csv":
        return list(DictReader(StringIO(content)))
    if fmt == "html":
        return _html_items(content)
    raise ValueError("仅支持 csv、json、html")


def parse_import(payload):
    fmt = str(payload.get("format", "")).lower().strip()
    content = str(payload.get("content", ""))
    source_name = str(payload.get("source_name", "")).strip()
    source_ref = str(payload.get("source_ref", "")).strip()
    if not source_name or not source_ref:
        raise ValueError("来源名称和原始文件名/引用必填")
    if not content.strip():
        raise ValueError("导入内容为空")
    default_observed = str(payload.get("observed_at", "")).strip()
    default_evidence = str(payload.get("evidence_type", "third_party_estimate")).strip()
    default_grade = str(payload.get("confidence_grade", "C")).upper().strip()
    source_type = str(payload.get("source_type", "manual_import")).strip()
    if source_type not in {"manual_import", "api_ingest"}:
        raise ValueError("source_type 仅支持 manual_import 或 api_ingest")
    if default_evidence not in EVIDENCE_TYPES or default_grade not in GRADES:
        raise ValueError("证据类型或置信等级无效")
    imported_at = utc_now()
    rows, errors = [], []
    for index, item in enumerate(_raw_items(fmt, content), start=1):
        if not isinstance(item, dict):
            errors.append({"row": index, "message": "记录不是对象"})
            continue
        try:
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", item.get("content", ""))).strip()
            if not title or not summary:
                raise ValueError("title 和 summary/content 必填")
            sector = str(item.get("sector", payload.get("sector", "ai_game"))).strip()
            evidence_type = str(item.get("evidence_type", default_evidence)).strip()
            grade = str(item.get("confidence_grade", default_grade)).upper().strip()
            if sector not in SECTORS or evidence_type not in EVIDENCE_TYPES or grade not in GRADES:
                raise ValueError("sector、evidence_type 或 confidence_grade 无效")
            observed_text = str(item.get("observed_at", item.get("observed_period", default_observed))).strip()
            observed = _date(observed_text)
            max_age = 90 if evidence_type == "third_party_estimate" else 30
            expires = observed + timedelta(days=max_age) if observed else None
            freshness = "unknown" if not observed else ("fresh" if expires >= imported_at else "stale")
            source_url = str(item.get("source_url", payload.get("source_url", ""))).strip()
            if source_url and urlparse(source_url).scheme not in {"http", "https"}:
                raise ValueError("source_url 仅支持 http/https")
            canonical = "|".join([title.lower(), source_ref.lower(), observed_text, str(item.get("metric_name", "资讯观察")).lower()])
            raw = {
                "import_format": fmt,
                "source_ref": source_ref,
                "record": item,
                "declared_estimate": bool(payload.get("is_estimate", evidence_type != "official")),
            }
            rows.append({
                "title": title,
                "summary": summary,
                "sector": sector,
                "source_name": source_name,
                "source_url": source_url,
                "collected_at": imported_at.isoformat(),
                "observed_period": observed_text or "未提供",
                "region": str(item.get("region", payload.get("region", "未标注"))).strip() or "未标注",
                "metric_name": str(item.get("metric_name", "资讯观察")).strip() or "资讯观察",
                "metric_value": str(item.get("metric_value", "见摘要")).strip() or "见摘要",
                "metric_unit": str(item.get("metric_unit", "原文口径")).strip() or "原文口径",
                "evidence_type": evidence_type,
                "confidence_grade": grade,
                "is_demo": 0,
                "dedupe_key": sha256(canonical.encode("utf-8")).hexdigest(),
                "raw_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                "source_type": source_type,
                "source_ref": source_ref,
                "updated_at": imported_at.isoformat(),
                "expires_at": expires.isoformat() if expires else "",
                "freshness_status": freshness,
                "is_estimate": int(bool(payload.get("is_estimate", evidence_type != "official"))),
            })
        except ValueError as exc:
            errors.append({"row": index, "message": str(exc)})
    return rows, errors
