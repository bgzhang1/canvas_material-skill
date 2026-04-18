from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .constants import DEFAULT_INTERVAL_MINUTES, DEFAULT_SCHEDULE_TIME, DEFAULT_WEEKLY_DAYS, WEEKDAY_ALIASES


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
        print("??? y ? n?")


def prompt_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = input(f"{prompt} [?? {default}] ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value >= minimum:
                return value
        except Exception:
            pass
        print(f"??????? {minimum} ????")


def prompt_csv(prompt: str, default: List[str]) -> List[str]:
    raw = input(f"{prompt} [?? {', '.join(default)}] ").strip()
    if not raw:
        return default
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or default


def prompt_text(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [?? {default}] ").strip()
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
        "??": "interval",
        "??": "interval",
        "???": "interval",
        "daily": "daily",
        "day": "daily",
        "??": "daily",
        "??": "daily",
        "weekly": "weekly",
        "week": "weekly",
        "??": "weekly",
        "???": "weekly",
    }
    return mapping.get(raw)


def prompt_schedule_type(prompt: str, default: str) -> str:
    labels = {
        "interval": "interval(?? N ??)",
        "daily": "daily(????)",
        "weekly": "weekly(????)",
    }
    while True:
        raw = input(f"{prompt} [?? {labels[default]}] ").strip()
        if not raw:
            return default
        value = normalize_schedule_type(raw)
        if value:
            return value
        print("??? interval/daily/weekly???? ??/??/???")


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
        raw = input(f"{prompt} [?? {default}] ").strip()
        if not raw:
            return default
        normalized = normalize_hhmm(raw)
        if normalized:
            return normalized
        print("?????????? 09:00 ? 18:30?")


def normalize_weekdays(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        tokens = [item.strip() for item in re.split(r"[,?/\s]+", values) if item.strip()]
    elif isinstance(values, list):
        tokens = []
        for item in values:
            if item is None:
                continue
            tokens.extend([part.strip() for part in re.split(r"[,?/\s]+", str(item)) if part.strip()])
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
        raw = input(f"{prompt} [?? {default_text}] ").strip()
        if not raw:
            return default
        days = normalize_weekdays(raw)
        if days:
            return days
        print("?????????? mon,wed ? ??,???")


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
