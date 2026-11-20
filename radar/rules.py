"""更新治理规则读取与真实运行状态快照。"""

import json
from pathlib import Path


def load_rule_snapshot(path, repository):
    rules_path = Path(path)
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    sources = repository.sources()
    live_sources = 0
    enabled_sources = 0
    for source in sources:
        if source.get("enabled"):
            enabled_sources += 1
        try:
            config = json.loads(source.get("config_json") or "{}")
        except json.JSONDecodeError:
            config = {}
        if source.get("enabled") and config.get("public_json_url"):
            live_sources += 1
    dashboard = repository.dashboard()
    signals_by_type = dashboard.get("signals_by_source_type", {})
    manual_count = signals_by_type.get("manual_import", 0)
    online_count = signals_by_type.get("live_online", 0)
    if online_count:
        notice = "已存在真实在线信号，但仍须逐来源完成健康率、去重和连续运行验收后才能用于自动机会升级。"
    elif manual_count:
        notice = "当前包含人工导入快照，不等于实时数据；须保留原始文件、观察日期和估算标记。"
    else:
        notice = "当前均为演示数据；接入真实来源并通过首次抽检前，不执行自动机会升级和确定性上限估算。"
    rules["runtime"] = {
        "execution_state": "定时规则待启用" if live_sources == 0 else "已具备定时启用条件",
        "actual_trigger": "服务启动 + 人工点击更新证据",
        "enabled_sources": enabled_sources,
        "live_sources": live_sources,
        "signal_count": dashboard.get("signals", 0),
        "demo_signal_count": signals_by_type.get("demo", 0),
        "manual_import_signal_count": manual_count,
        "live_online_signal_count": online_count,
        "opportunity_count": dashboard.get("total", 0),
        "demo_opportunity_count": dashboard.get("demo", 0),
        "semantic_dedup_active": False,
        "ceiling_model_active": False,
        "notice": notice
    }
    return rules
