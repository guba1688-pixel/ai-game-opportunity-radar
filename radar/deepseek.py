"""DeepSeek 服务端配置与连通性检测。密钥永不返回给浏览器。"""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
ALLOWED_MODELS = {"deepseek-flash", "deepseek-v4-pro"}


def _config_path(root):
    return Path(root) / "config" / "deepseek.json"


def _read_file(root):
    path = _config_path(root)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_deepseek_config(root):
    saved = _read_file(root)
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip() or str(saved.get("api_key", "")).strip()
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip() or str(saved.get("base_url", DEFAULT_BASE_URL)).strip()
    model = os.environ.get("DEEPSEEK_MODEL", "").strip() or str(saved.get("model", DEFAULT_MODEL)).strip()
    return {"api_key": api_key, "base_url": base_url or DEFAULT_BASE_URL, "model": model or DEFAULT_MODEL}


def public_deepseek_status(root):
    config = load_deepseek_config(root)
    key_source = "environment" if os.environ.get("DEEPSEEK_API_KEY", "").strip() else ("server_file" if config["api_key"] else "none")
    return {
        "configured": bool(config["api_key"]),
        "base_url": config["base_url"],
        "model": config["model"],
        "key_source": key_source,
    }


def save_deepseek_config(root, payload):
    current = load_deepseek_config(root)
    base_url = str(payload.get("base_url", current["base_url"])).strip().rstrip("/")
    model = str(payload.get("model", current["model"])).strip()
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != "api.deepseek.com":
        raise ValueError("DeepSeek 地址必须使用 https://api.deepseek.com")
    if model not in ALLOWED_MODELS:
        raise ValueError("模型仅支持 deepseek-flash 或 deepseek-v4-pro")
    api_key = str(payload.get("api_key", "")).strip()
    if not api_key:
        api_key = str(_read_file(root).get("api_key", "")).strip()
    if payload.get("clear_api_key"):
        api_key = ""
    if api_key and not api_key.startswith("sk-"):
        raise ValueError("DeepSeek API Key 格式应以 sk- 开头")
    path = _config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"api_key": api_key, "base_url": base_url, "model": model}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return public_deepseek_status(root)


def test_deepseek_connection(root, timeout=20):
    config = load_deepseek_config(root)
    if not config["api_key"]:
        raise ValueError("尚未配置 DeepSeek API Key")
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": "仅回复 OK"}],
        "thinking": {"type": "disabled"},
        "max_tokens": 4,
        "stream": False,
    }
    request = Request(
        config["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer " + config["api_key"], "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = ""
        raise ValueError(f"DeepSeek 返回 HTTP {exc.code}" + (f"：{detail}" if detail else "")) from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"无法连接 DeepSeek：{getattr(exc, 'reason', exc)}") from exc
    usage = result.get("usage") or {}
    return {
        "ok": True,
        "model": result.get("model", config["model"]),
        "reply": ((result.get("choices") or [{}])[0].get("message") or {}).get("content", ""),
        "total_tokens": usage.get("total_tokens", 0),
    }
