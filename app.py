from pathlib import Path
import argparse
import json

from radar.db import Repository
from radar.service import OpportunityService
from radar.web import serve


def main():
    parser = argparse.ArgumentParser(description="AI × 游戏机会雷达 MVP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--db", default="data/opportunity_radar.db")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = root / db_path
    service = OpportunityService(Repository(db_path))
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    source_config = {}
    if config_path.is_file():
        source_config = json.loads(config_path.read_text(encoding="utf-8")).get("sources", {})
    service.bootstrap(source_config)
    serve(root, service, args.host, args.port)


if __name__ == "__main__":
    main()
