from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CANVAS_URL = "https://canvas.example.edu"
DEFAULT_INTERVAL_MINUTES = 60
DEFAULT_CATEGORY_FOLDERS = ["lecture", "tutorial"]
DEFAULT_SCHEDULE_TIME = "09:00"
DEFAULT_WEEKLY_DAYS = ["MON"]
FILE_LINK_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
INVALID_FILENAME = re.compile(r"[\\/:*?\"<>|]+")
LECTURE_RE = re.compile(r"(lecture|lectures|lec\b|slides?|topic\d*|chapter\d*|week\s*\d+|syllabus)", re.I)
TUTORIAL_RE = re.compile(r"(tutorial|tut\b|lab\b|exercise|exercises|practice|worksheet|problem\s*set|homework|assignment|question)", re.I)
IGNORE_RE = re.compile(r"(video|recording|meeting|zoom|archive|source\s*code|starter\s*code|demo\s*video)", re.I)
DOC_EXTS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".pps", ".ppsx", ".txt", ".md", ".html", ".htm", ".ipynb"}
IGNORE_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".zip", ".rar", ".7z", ".tar", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".exe"}
PACKAGE_ROOT = Path(__file__).resolve().parent
SCRIPTS_ROOT = PACKAGE_ROOT.parent
ENTRY_SCRIPT_PATH = SCRIPTS_ROOT / "canvas_material_sync.py"
SKILL_ROOT = SCRIPTS_ROOT.parent
MEMORY_PATH = SKILL_ROOT / "memory.json"
RULES_PATH = SKILL_ROOT / "rules.json"
WEEKDAY_ALIASES = {
    "mon": "MON", "monday": "MON", "周一": "MON", "星期一": "MON", "礼拜一": "MON", "1": "MON",
    "tue": "TUE", "tues": "TUE", "tuesday": "TUE", "周二": "TUE", "星期二": "TUE", "礼拜二": "TUE", "2": "TUE",
    "wed": "WED", "wednesday": "WED", "周三": "WED", "星期三": "WED", "礼拜三": "WED", "3": "WED",
    "thu": "THU", "thur": "THU", "thurs": "THU", "thursday": "THU", "周四": "THU", "星期四": "THU", "礼拜四": "THU", "4": "THU",
    "fri": "FRI", "friday": "FRI", "周五": "FRI", "星期五": "FRI", "礼拜五": "FRI", "5": "FRI",
    "sat": "SAT", "saturday": "SAT", "周六": "SAT", "星期六": "SAT", "礼拜六": "SAT", "6": "SAT",
    "sun": "SUN", "sunday": "SUN", "周日": "SUN", "星期日": "SUN", "礼拜日": "SUN", "周天": "SUN", "星期天": "SUN", "礼拜天": "SUN", "7": "SUN", "0": "SUN",
}


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


def prompt_bool(prompt: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def prompt_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = input(f"{prompt} [默认 {default}] ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value >= minimum:
                return value
        except Exception:
            pass
        print(f"请输入大于等于 {minimum} 的整数。")


def prompt_csv(prompt: str, default: List[str]) -> List[str]:
    raw = input(f"{prompt} [默认 {', '.join(default)}] ").strip()
    if not raw:
        return default
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or default


def prompt_text(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [默认 {default}] ").strip()
    return raw or default


def normalize_schedule_type(value: str) -> Optional[str]:
    if not value:
        return None
    raw = value.strip().lower()
    mapping = {
        "interval": "interval",
        "minutes": "interval",
        "minute": "interval",
        "minutely": "interval",
        "每隔": "interval",
        "分钟": "interval",
        "按分钟": "interval",
        "daily": "daily",
        "day": "daily",
        "每天": "daily",
        "每日": "daily",
        "weekly": "weekly",
        "week": "weekly",
        "每周": "weekly",
        "每星期": "weekly",
    }
    return mapping.get(raw)


def prompt_schedule_type(prompt: str, default: str) -> str:
    labels = {
        "interval": "interval(每隔 N 分钟)",
        "daily": "daily(每天定时)",
        "weekly": "weekly(每周定时)",
    }
    while True:
        raw = input(f"{prompt} [默认 {labels[default]}] ").strip()
        if not raw:
            return default
        value = normalize_schedule_type(raw)
        if value:
            return value
        print("请输入 interval/daily/weekly，或输入 分钟/每天/每周。")


def normalize_hhmm(value: str) -> Optional[str]:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def prompt_hhmm(prompt: str, default: str) -> str:
    while True:
        raw = input(f"{prompt} [默认 {default}] ").strip()
        if not raw:
            return default
        normalized = normalize_hhmm(raw)
        if normalized:
            return normalized
        print("请输入合法时间，例如 09:00 或 18:30。")


def normalize_weekdays(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        tokens = [item.strip() for item in re.split(r"[,，/\s]+", values) if item.strip()]
    elif isinstance(values, list):
        tokens = []
        for item in values:
            if item is None:
                continue
            tokens.extend([part.strip() for part in re.split(r"[,，/\s]+", str(item)) if part.strip()])
    else:
        tokens = [str(values).strip()]
    out: List[str] = []
    for token in tokens:
        day = WEEKDAY_ALIASES.get(token.strip().lower())
        if day and day not in out:
            out.append(day)
    return out


def prompt_weekdays(prompt: str, default: List[str]) -> List[str]:
    default_text = ", ".join(default)
    while True:
        raw = input(f"{prompt} [默认 {default_text}] ").strip()
        if not raw:
            return default
        days = normalize_weekdays(raw)
        if days:
            return days
        print("请输入合法星期，例如 mon,wed 或 周一,周三。")


def resolve_schedule_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    enabled = bool(config.get("schedule_enabled", True))
    schedule_type = normalize_schedule_type(str(config.get("schedule_type") or "interval")) or "interval"
    interval_minutes = config.get("interval_minutes")
    if schedule_type == "interval":
        try:
            interval_minutes = int(interval_minutes or DEFAULT_INTERVAL_MINUTES)
        except Exception:
            interval_minutes = DEFAULT_INTERVAL_MINUTES
        if interval_minutes < 1:
            interval_minutes = DEFAULT_INTERVAL_MINUTES
    else:
        interval_minutes = None
    schedule_time = normalize_hhmm(str(config.get("schedule_time") or DEFAULT_SCHEDULE_TIME)) if schedule_type in {"daily", "weekly"} else None
    if schedule_type in {"daily", "weekly"} and schedule_time is None:
        schedule_time = DEFAULT_SCHEDULE_TIME
    schedule_days = normalize_weekdays(config.get("schedule_days")) if schedule_type == "weekly" else []
    if schedule_type == "weekly" and not schedule_days:
        schedule_days = list(DEFAULT_WEEKLY_DAYS)
    return {
        "enabled": enabled,
        "schedule_type": schedule_type,
        "interval_minutes": interval_minutes,
        "schedule_time": schedule_time,
        "schedule_days": schedule_days,
    }


def category_mapping(categories: List[str]) -> Tuple[str, str]:
    lecture = None
    tutorial = None
    for category in categories:
        lowered = category.lower()
        if lecture is None and re.search(r"(lecture|slide|slides|topic|chapter|note)", lowered):
            lecture = category
        if tutorial is None and re.search(r"(tutorial|lab|exercise|practice|worksheet|homework|assignment|question)", lowered):
            tutorial = category
    if lecture is None:
        lecture = categories[0]
    if tutorial is None:
        tutorial = categories[1] if len(categories) > 1 else categories[0]
    return lecture, tutorial


def default_config_path(output_root: Path) -> Path:
    return output_root / "_canvas_material_sync_config.json"


def default_state_path(output_root: Path) -> Path:
    return output_root / "_canvas_material_sync_state.json"


def default_last_update_path(output_root: Path) -> Path:
    return output_root / "_canvas_material_sync_last_update.txt"


def read_last_update_marker(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return value or None


def write_last_update_marker(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + "\n", encoding="utf-8")


def load_memory() -> Dict[str, Any]:
    return load_json(MEMORY_PATH, {"profiles": [], "last_config_path": None, "first_full_sync_completed": False})


def update_memory(config_path: Path, config: Dict[str, Any], state: Dict[str, Any]) -> None:
    memory = load_memory()
    memory["last_config_path"] = str(config_path)
    memory["first_full_sync_completed"] = bool(state.get("first_full_sync_completed"))
    entry = {
        "config_path": str(config_path),
        "output_root": config.get("output_root"),
        "client_name": config.get("client_name"),
        "scheduler_backend": config.get("scheduler_backend"),
        "first_full_sync_completed": bool(state.get("first_full_sync_completed")),
        "last_full_sync_at": state.get("last_full_sync_at"),
        "last_incremental_sync_at": state.get("last_incremental_sync_at"),
        "updated_at": now_utc(),
    }
    profiles = [profile for profile in memory.get("profiles", []) if profile.get("config_path") != str(config_path)]
    profiles.append(entry)
    memory["profiles"] = profiles
    save_json(MEMORY_PATH, memory)
