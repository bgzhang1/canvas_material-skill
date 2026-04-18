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
    "mon": "MON", "monday": "MON", "??": "MON", "???": "MON", "???": "MON", "1": "MON",
    "tue": "TUE", "tues": "TUE", "tuesday": "TUE", "??": "TUE", "???": "TUE", "???": "TUE", "2": "TUE",
    "wed": "WED", "wednesday": "WED", "??": "WED", "???": "WED", "???": "WED", "3": "WED",
    "thu": "THU", "thur": "THU", "thurs": "THU", "thursday": "THU", "??": "THU", "???": "THU", "???": "THU", "4": "THU",
    "fri": "FRI", "friday": "FRI", "??": "FRI", "???": "FRI", "???": "FRI", "5": "FRI",
    "sat": "SAT", "saturday": "SAT", "??": "SAT", "???": "SAT", "???": "SAT", "6": "SAT",
    "sun": "SUN", "sunday": "SUN", "??": "SUN", "???": "SUN", "???": "SUN", "??": "SUN", "???": "SUN", "???": "SUN", "7": "SUN", "0": "SUN",
}
