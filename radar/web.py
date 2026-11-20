"""零依赖本地 HTTP API 与静态管理台。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .deepseek import public_deepseek_status, save_deepseek_config, test_deepseek_connection
from .rules import load_rule_snapshot
from .service import ValidationError

PERMISSIONS = {
    "admin": {"view", "add", "edit", "delete", "export", "collect", "manage"},
    "analyst": {"view", "add", "edit", "export", "collect"},
    "viewer": {"view"},
    "ingester": {"view", "add", "collect"},
}


def make_handler(root, service):
    static_root = (Path(root) / "static").resolve()
    update_rules_path = (Path(root) / "config" / "update_rules.json").resolve()
    connector_path = (Path(root) / "config" / "source_connectors.json").resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "OpportunityRadar/" + __version__

        def log_message(self, fmt, *args):
            print(f"[HTTP] {self.address_string()} {fmt % args}")

        @property
        def role(self):
            configured = os.environ.get("RADAR_API_KEY", "")
            supplied = self.headers.get("X-API-Key", "")
            if configured and supplied and hmac.compare_digest(configured, supplied):
                return "ingester"
            value = self.headers.get("X-Role", "admin").lower()
            return value if value in PERMISSIONS else "viewer"

        def require(self, permission):
            if permission not in PERMISSIONS[self.role]:
                self.send_json({"error": "forbidden", "message": f"角色 {self.role} 无 {permission} 权限"}, 403)
                return False
            return True

        def send_json(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_text(self, text, content_type, filename=None):
            data = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            length = int(self.headers.get("Content-Length", 0))
            if length > 5_000_000:
                raise ValidationError("请求体超过 5 MB")
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            parsed = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            try:
                if parsed.path == "/api/health":
                    return self.send_json({"status": "ok", "version": __version__, "database": str(service.repo.path)})
                if parsed.path.startswith("/api/") and not self.require("view"):
                    return
                if parsed.path == "/api/meta":
                    return self.send_json({"version": __version__, "role": self.role, "permissions": sorted(PERMISSIONS[self.role]), "evidence_types": ["official","third_party_estimate","model_inference","demo"], "stages":["lead","screen","evidence_7d","test_30d","scale_validation","approved","rejected"]})
                if parsed.path == "/api/dashboard":
                    return self.send_json(service.repo.dashboard())
                if parsed.path == "/api/intelligence-dashboard":
                    return self.send_json(service.intelligence_dashboard())
                if parsed.path == "/api/update-rules":
                    return self.send_json(load_rule_snapshot(update_rules_path, service.repo))
                if parsed.path == "/api/source-connectors":
                    return self.send_json(json.loads(connector_path.read_text(encoding="utf-8")))
                if parsed.path == "/api/sources":
                    return self.send_json(service.repo.sources())
                if parsed.path == "/api/company-profile":
                    return self.send_json(service.repo.get_company_profile())
                if parsed.path in {"/api/signals", "/api/v1/intelligence"}:
                    return self.send_json(service.repo.list_signals(query.get("sector", ""), query.get("evidence_type", ""), query.get("q", ""),query.get("source_type", ""),query.get("freshness", "")))
                if parsed.path in {"/api/ingestion-status", "/api/v1/ingestion/status"}:
                    return self.send_json({"version":__version__,"api_key_enabled":bool(os.environ.get("RADAR_API_KEY")),"deepseek":public_deepseek_status(root),"sources":service.repo.sources()})
                if parsed.path == "/api/deepseek/status":
                    return self.send_json(public_deepseek_status(root))
                if parsed.path == "/api/opportunities":
                    return self.send_json(service.repo.list_opportunities(query.get("sector", ""),query.get("pool", ""),query.get("status", ""),query.get("q", ""),query.get("region", ""),query.get("genre", ""),query.get("asset", ""),query.get("stage", ""),query.get("decision", ""),query.get("min_fit", "")))
                if parsed.path.startswith("/api/opportunities/"):
                    object_id = int(parsed.path.rsplit("/", 1)[1])
                    item = service.repo.get_opportunity(object_id)
                    return self.send_json(item if item else {"error": "not_found"}, 200 if item else 404)
                if parsed.path == "/api/audit":
                    if not self.require("manage"): return
                    return self.send_json(service.repo.audit_logs())
                if parsed.path in {"/api/export.csv", "/api/export.md"}:
                    if not self.require("export"): return
                    rows = service.repo.list_opportunities(query.get("sector", ""),query.get("pool", ""),query.get("status", ""),query.get("q", ""),query.get("region", ""),query.get("genre", ""),query.get("asset", ""),query.get("stage", ""),query.get("decision", ""),query.get("min_fit", ""))
                    if parsed.path.endswith("csv"):
                        return self.send_text(service.export_csv(rows), "text/csv; charset=utf-8", f"game-market-opportunities-v{__version__}.csv")
                    return self.send_text(service.export_markdown(rows), "text/markdown; charset=utf-8", f"game-market-opportunities-v{__version__}.md")
                if parsed.path.startswith("/api/"):
                    return self.send_json({"error": "not_found"}, 404)
                return self.send_static(parsed.path)
            except (ValueError, ValidationError) as exc:
                self.send_json({"error": "bad_request", "message": str(exc)}, 400)
            except Exception as exc:
                self.send_json({"error": "server_error", "message": str(exc)}, 500)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/collect":
                    if not self.require("collect"): return
                    result = service.collect(self.body().get("source_key"))
                    return self.send_json(result, 201)
                if parsed.path == "/api/import":
                    if not self.require("manage"): return
                    return self.send_json(service.import_signals(self.body(),self.role),201)
                if parsed.path in {"/api/intelligence", "/api/v1/intelligence", "/api/v1/intelligence/batch"}:
                    if not self.require("add"): return
                    payload=self.body()
                    force_type="api_ingest" if self.role=="ingester" else None
                    return self.send_json(service.submit_intelligence(payload,self.role,force_type),201)
                if parsed.path == "/api/deepseek/config":
                    if not self.require("manage"): return
                    return self.send_json(save_deepseek_config(root,self.body()))
                if parsed.path == "/api/deepseek/test":
                    if not self.require("manage"): return
                    return self.send_json(test_deepseek_connection(root))
                if parsed.path.startswith("/api/opportunities/") and parsed.path.endswith("/evidence"):
                    if not self.require("edit"): return
                    object_id=int(parsed.path.strip("/").split("/")[2])
                    return self.send_json(service.link_evidence(object_id,self.body(),self.role),201)
                if parsed.path == "/api/opportunities":
                    if not self.require("add"): return
                    return self.send_json(service.create_opportunity(self.body(), self.role), 201)
                self.send_json({"error": "not_found"}, 404)
            except (ValueError, ValidationError) as exc:
                self.send_json({"error": "bad_request", "message": str(exc)}, 400)
            except Exception as exc:
                self.send_json({"error": "server_error", "message": str(exc)}, 500)

        def do_PUT(self):
            try:
                if not self.require("edit"): return
                if urlparse(self.path).path == "/api/company-profile":
                    if not self.require("manage"): return
                    return self.send_json(service.update_profile(self.body(), self.role))
                if not self.path.startswith("/api/opportunities/"):
                    return self.send_json({"error": "not_found"}, 404)
                object_id = int(urlparse(self.path).path.rsplit("/", 1)[1])
                return self.send_json(service.update_opportunity(object_id, self.body(), self.role))
            except KeyError:
                self.send_json({"error": "not_found"}, 404)
            except (ValueError, ValidationError) as exc:
                self.send_json({"error": "bad_request", "message": str(exc)}, 400)
            except Exception as exc:
                self.send_json({"error": "server_error", "message": str(exc)}, 500)

        def do_DELETE(self):
            try:
                if not self.require("delete"): return
                path = urlparse(self.path).path
                if not path.startswith("/api/opportunities/"):
                    return self.send_json({"error": "not_found"}, 404)
                object_id = int(path.rsplit("/", 1)[1])
                if not service.repo.delete_opportunity(object_id, self.role):
                    return self.send_json({"error": "not_found"}, 404)
                self.send_json({"deleted": object_id})
            except ValueError as exc:
                self.send_json({"error": "bad_request", "message": str(exc)}, 400)

        def send_static(self, request_path):
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            candidate = (static_root / relative).resolve()
            if static_root not in candidate.parents and candidate != static_root:
                return self.send_json({"error": "forbidden"}, 403)
            if not candidate.is_file():
                candidate = static_root / "index.html"
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(root, service, host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), make_handler(root, service))
    print(f"AI × 游戏机会市场雷达 v{__version__} 已启动：http://{host}:{port}")
    server.serve_forever()
