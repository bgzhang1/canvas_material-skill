from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import INVALID_FILENAME


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_dt(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def sanitize_filename(name: str) -> str:
    return INVALID_FILENAME.sub("_", name).strip().rstrip(".") or "unnamed"


def strip_html(value: str) -> str:
    value = value or ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rule_overrides(path: Path) -> List[Dict[str, Any]]:
    data = load_json(path, {"overrides": []})
    overrides = data.get("overrides", []) if isinstance(data, dict) else []
    return [item for item in overrides if isinstance(item, dict)]


def detect_client_name() -> str:
    env = {k.lower(): v for k, v in os.environ.items()}
    if "codex_home" in env:
        return "codex"
    if any("opencode" in key for key in env):
        return "opencode"
    if any("openclaw" in key for key in env):
        return "openclaw"
    return "generic"


def detect_scheduler_backend() -> str:
    return "windows-task" if os.name == "nt" else "cron"
