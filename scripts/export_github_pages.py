from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
PAGES = ROOT / "docs"
BASE_URL = "http://127.0.0.1:8765"

ENDPOINTS = {
    "meta": "/api/meta",
    "radar_dashboard": "/api/dashboard",
    "opportunities": "/api/opportunities",
    "signals": "/api/signals",
    "dashboard": "/api/intelligence-dashboard",
    "ingestion_status": "/api/ingestion-status",
    "company_profile": "/api/company-profile",
    "audit": "/api/audit",
    "sources": "/api/sources",
    "update_rules": "/api/update-rules",
}


def fetch_json(path: str):
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"X-Role": "admin", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def main() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    for source in STATIC.iterdir():
        if source.is_file():
            shutil.copy2(source, PAGES / source.name)

    index_path = PAGES / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace('href="/', 'href="./').replace('src="/', 'src="./')
    html = html.replace(
        '<script src="./app.js"></script>',
        '<script src="./pages-mode.js"></script><script src="./app.js"></script>',
    )
    index_path.write_text(html, encoding="utf-8")

    snapshot = {name: fetch_json(path) for name, path in ENDPOINTS.items()}
    (PAGES / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (PAGES / ".nojekyll").touch()
    print(f"GitHub Pages snapshot exported to {PAGES}")


if __name__ == "__main__":
    main()
