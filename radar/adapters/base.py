"""适配器协议及合规公开 JSON 读取器。"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

EVIDENCE_TYPES = {"official", "third_party_estimate", "model_inference", "demo"}
GRADES = set("ABCDE")


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Signal:
    title: str
    summary: str
    sector: str
    source_name: str
    source_url: str
    observed_period: str
    region: str
    metric_name: str
    metric_value: str
    metric_unit: str
    evidence_type: str
    confidence_grade: str
    is_demo: bool = False

    def normalized(self):
        if self.sector not in {"ai", "game", "ai_game"}:
            raise ValueError("sector 必须是 ai、game 或 ai_game")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError("未知证据类型")
        if self.confidence_grade not in GRADES:
            raise ValueError("置信等级必须是 A-E")
        if self.evidence_type == "demo" and not self.is_demo:
            raise ValueError("演示证据必须设置 is_demo")
        source = urlparse(self.source_url)
        if source.scheme not in {"http", "https"} or not source.netloc or source.username:
            raise ValueError("来源链接必须是无凭据的 HTTP(S) URL")
        row = asdict(self)
        row["collected_at"] = utc_now()
        canonical = "|".join([self.title.strip().lower(), self.source_url.strip().lower(), self.observed_period.strip(), self.metric_name.strip().lower()])
        row["dedupe_key"] = sha256(canonical.encode("utf-8")).hexdigest()
        row["raw_json"] = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
        row["is_demo"] = int(self.is_demo)
        return row


class PublicJsonMixin:
    """只允许无需认证的 HTTP(S) JSON；不处理登录、验证码或反爬。"""

    def read_public_json(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise ValueError("仅支持无凭据的公开 HTTP(S) URL")
        request = Request(url, headers={"User-Agent": "OpportunityRadar/0.1 (+local-research)"})
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"application/json", "text/json"}:
                raise ValueError("公开数据源必须返回 JSON")
            return json.load(response)
