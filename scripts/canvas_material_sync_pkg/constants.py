from __future__ import annotations

import re
from pathlib import Path

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
    "mon": "MON", "monday": "MON", "周一": "MON", "星期一": "MON", "一": "MON", "1": "MON",
    "tue": "TUE", "tues": "TUE", "tuesday": "TUE", "周二": "TUE", "星期二": "TUE", "二": "TUE", "2": "TUE",
    "wed": "WED", "wednesday": "WED", "周三": "WED", "星期三": "WED", "三": "WED", "3": "WED",
    "thu": "THU", "thur": "THU", "thurs": "THU", "thursday": "THU", "周四": "THU", "星期四": "THU", "四": "THU", "4": "THU",
    "fri": "FRI", "friday": "FRI", "周五": "FRI", "星期五": "FRI", "五": "FRI", "5": "FRI",
    "sat": "SAT", "saturday": "SAT", "周六": "SAT", "星期六": "SAT", "六": "SAT", "6": "SAT",
    "sun": "SUN", "sunday": "SUN", "周日": "SUN", "星期日": "SUN", "周天": "SUN", "星期天": "SUN", "日": "SUN", "天": "SUN", "7": "SUN", "0": "SUN",
}
