from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from .canvas_api import CanvasClient, choose_filename, collect_candidates
from .constants import (
    DEFAULT_CANVAS_URL,
    DEFAULT_CATEGORY_FOLDERS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SCHEDULE_TIME,
    DEFAULT_WEEKLY_DAYS,
    ENTRY_SCRIPT_PATH,
    RULES_PATH,
)
from .prompts import (
    normalize_hhmm,
    normalize_schedule_type,
    normalize_weekdays,
    prompt_bool,
    prompt_csv,
    prompt_hhmm,
    prompt_int,
    prompt_schedule_type,
    prompt_text,
    prompt_weekdays,
    resolve_schedule_settings,
)
from .state import (
    default_config_path,
    default_last_update_path,
    default_state_path,
    read_last_update_marker,
    update_memory,
    write_last_update_marker,
)
from .utils import (
    detect_client_name,
    detect_scheduler_backend,
    load_json,
    load_rule_overrides,
    now_utc,
    parse_dt,
    sanitize_filename,
    save_json,
)
from .materials import MaterialClassifier, OpenAIClassifier, ensure_pdf, extract_text_from_bytes


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    token_present = bool(os.environ.get("CANVAS_TOKEN"))
    base_url = os.environ.get("CANVAS_URL", DEFAULT_CANVAS_URL)
    client_name = args.client_name or detect_client_name()
    scheduler_backend = args.scheduler_backend or detect_scheduler_backend()
    output_root_default = str((Path.cwd() / "canvas_materials").resolve())
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else Path(prompt_text("资料输出目录", output_root_default)).expanduser().resolve()

    pdf_default = args.pdf_convert if args.pdf_convert is not None else True
    schedule_default = args.schedule_enabled if args.schedule_enabled is not None else True
    schedule_type_default = normalize_schedule_type(args.schedule_type) if args.schedule_type else "interval"
    interval_default = args.interval_minutes if args.interval_minutes is not None else DEFAULT_INTERVAL_MINUTES
    schedule_time_default = normalize_hhmm(args.schedule_time) if args.schedule_time else DEFAULT_SCHEDULE_TIME
    schedule_days_default = normalize_weekdays(args.schedule_days) if args.schedule_days else list(DEFAULT_WEEKLY_DAYS)
    categories_default = args.categories if args.categories else DEFAULT_CATEGORY_FOLDERS

    print("\n[setup] 首次安装前需要确认以下项目：")
    pdf_convert = prompt_bool("1. 是否开启 PDF 转换？", pdf_default)
    schedule_enabled = prompt_bool("2. 是否开启定时执行？", schedule_default)
    schedule_type = None
    interval_minutes = None
    schedule_time = None
    schedule_days: List[str] = []
    if schedule_enabled:
        schedule_type = prompt_schedule_type("3. 定时执行方式是？", schedule_type_default)
        if schedule_type == "interval":
            interval_minutes = prompt_int("4. 执行周期是多少（分钟）？", interval_default, 1)
        else:
            schedule_time = prompt_hhmm("5. 具体执行时间是什么（HH:MM）？", schedule_time_default)
            if schedule_type == "weekly":
                schedule_days = prompt_weekdays("6. 每周哪几天执行？", schedule_days_default)
    categories = prompt_csv("7. 资料要分成哪些文件夹分类（逗号分隔）？", categories_default)

    courses = args.course or []
    use_ai = args.use_ai if args.use_ai is not None else bool(os.environ.get("OPENAI_API_KEY"))
    if not token_present:
        print("提示：当前进程未检测到 CANVAS_TOKEN，后续运行前请先设置该环境变量。", file=sys.stderr)
    return {
        "canvas_url": base_url,
        "output_root": str(output_root),
        "state_file": str(default_state_path(output_root)),
        "last_update_file": str(default_last_update_path(output_root)),
        "rules_file": str(RULES_PATH),
        "pdf_convert": bool(pdf_convert),
        "keep_original_after_pdf": False,
        "schedule_enabled": bool(schedule_enabled),
        "schedule_type": schedule_type,
        "interval_minutes": int(interval_minutes) if interval_minutes is not None else None,
        "schedule_time": schedule_time,
        "schedule_days": schedule_days,
        "category_folders": categories,
        "courses": courses,
        "use_ai": bool(use_ai),
        "client_name": client_name,
        "scheduler_backend": scheduler_backend,
        "created_at": now_utc(),
    }


def load_config(path: Path) -> Dict[str, Any]:
    cfg = load_json(path, {})
    if not cfg:
        raise SystemExit(f"Config not found or invalid: {path}")
    return cfg


def install_windows_task(config_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    output_root = Path(config["output_root"])
    runner = output_root / "_canvas_material_sync_run.ps1"
    task_name = f"CanvasMaterialSync-{sanitize_filename(output_root.name)}"
    runner.write_text(f"python \"{ENTRY_SCRIPT_PATH}\" run --config \"{config_path}\"\n", encoding="utf-8")
    schedule = resolve_schedule_settings(config)
    cmd = [
        "schtasks", "/Create", "/F", "/TN", task_name,
        "/TR", f"powershell -NoProfile -ExecutionPolicy Bypass -File \"{runner}\"",
    ]
    if schedule["schedule_type"] == "interval":
        cmd.extend(["/SC", "MINUTE", "/MO", str(schedule["interval_minutes"])])
    elif schedule["schedule_type"] == "daily":
        cmd.extend(["/SC", "DAILY", "/ST", str(schedule["schedule_time"])])
    else:
        cmd.extend(["/SC", "WEEKLY", "/D", ",".join(schedule["schedule_days"]), "/ST", str(schedule["schedule_time"])])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "backend": "windows-task",
        "task_name": task_name,
        "runner": str(runner),
        "schedule_type": schedule["schedule_type"],
        "interval_minutes": schedule["interval_minutes"],
        "schedule_time": schedule["schedule_time"],
        "schedule_days": schedule["schedule_days"],
        "installed": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def install_cron_stub(config_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    output_root = Path(config["output_root"])
    runner = output_root / "_canvas_material_sync_run.sh"
    runner.write_text(f"python3 \"{ENTRY_SCRIPT_PATH}\" run --config \"{config_path}\"\n", encoding="utf-8")
    try:
        runner.chmod(0o755)
    except Exception:
        pass
    schedule = resolve_schedule_settings(config)
    if schedule["schedule_type"] == "interval":
        interval = int(schedule["interval_minutes"])
        if interval <= 59 and 60 % interval == 0:
            crontab_line = f"*/{interval} * * * * {runner}"
        elif interval % 60 == 0:
            crontab_line = f"0 */{interval // 60} * * * {runner}"
        else:
            crontab_line = f"* * * * * [ $(( ($(date +\\%s) / 60) % {interval} )) -eq 0 ] && {runner}"
    else:
        hour, minute = (schedule["schedule_time"] or DEFAULT_SCHEDULE_TIME).split(":")
        if schedule["schedule_type"] == "daily":
            crontab_line = f"{int(minute)} {int(hour)} * * * {runner}"
        else:
            crontab_line = f"{int(minute)} {int(hour)} * * {','.join(schedule['schedule_days'])} {runner}"
    return {
        "backend": "cron",
        "runner": str(runner),
        "schedule_type": schedule["schedule_type"],
        "interval_minutes": schedule["interval_minutes"],
        "schedule_time": schedule["schedule_time"],
        "schedule_days": schedule["schedule_days"],
        "installed": False,
        "manual_crontab_line": crontab_line,
    }


def install_scheduler(config_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("schedule_enabled", True):
        return {
            "backend": None,
            "installed": False,
            "enabled": False,
            "schedule_type": None,
            "note": "scheduled sync disabled by user",
        }
    backend = config.get("scheduler_backend") or detect_scheduler_backend()
    if backend == "windows-task" and os.name == "nt":
        return install_windows_task(config_path, config)
    return install_cron_stub(config_path, config)


def ensure_course_dirs(course_dir: Path, categories: List[str]) -> None:
    course_dir.mkdir(parents=True, exist_ok=True)
    for category in categories:
        (course_dir / category).mkdir(parents=True, exist_ok=True)


def run_sync(config: Dict[str, Any], *, mode: str, dry_run: bool = False, verbose: bool = False) -> int:
    token = os.environ.get("CANVAS_TOKEN")
    if not token:
        print("Error: CANVAS_TOKEN is required.", file=sys.stderr)
        return 1
    output_root = Path(config["output_root"]).expanduser().resolve()
    state_path = Path(config.get("state_file") or default_state_path(output_root)).expanduser().resolve()
    last_update_path = Path(config.get("last_update_file") or default_last_update_path(output_root)).expanduser().resolve()
    categories = config.get("category_folders") or DEFAULT_CATEGORY_FOLDERS
    state = load_json(state_path, {"first_full_sync_completed": False, "last_full_sync_at": None, "last_incremental_sync_at": None, "last_sync_at": None, "downloaded": {}, "courses": {}, "scheduler": None})
    baseline = None
    if mode == "incremental":
        baseline = (
            parse_dt(state.get("last_sync_at"))
            or parse_dt(read_last_update_marker(last_update_path))
            or parse_dt(state.get("last_incremental_sync_at"))
            or parse_dt(state.get("last_full_sync_at"))
        )
    client = CanvasClient(config.get("canvas_url") or os.environ.get("CANVAS_URL", DEFAULT_CANVAS_URL), token, verbose=verbose)
    courses = client.fetch_courses(config.get("courses") or None)
    ai = None
    if config.get("use_ai") and os.environ.get("OPENAI_API_KEY"):
        ai = OpenAIClassifier(os.environ["OPENAI_API_KEY"], os.environ.get("OPENAI_MODEL", "gpt-5-mini"))
    rules_file = Path(config.get("rules_file") or RULES_PATH)
    rules = load_rule_overrides(rules_file)
    classifier = MaterialClassifier(categories=categories, ai=ai, rules=rules)
    summary = {category: 0 for category in categories}
    summary.update({"ignore": 0, "errors": 0, "converted_to_pdf": 0})
    for course in courses:
        cid = str(course["id"])
        cname = course.get("name") or course.get("course_code") or cid
        course_dir = output_root / sanitize_filename(cname)
        ensure_course_dirs(course_dir, categories)
        candidates = collect_candidates(client, course, baseline, verbose=verbose)
        if verbose:
            print(f"[info] {cname}: {len(candidates)} candidate file actions")
        for cand in candidates:
            try:
                data, headers, final_url = client.download_binary(cand.file_url)
                filename = choose_filename(headers, final_url, sanitize_filename(cand.source_title))
                key = f"{cand.course_id}:{filename}:{cand.file_url}"
                extracted = extract_text_from_bytes(data, filename, headers.get("Content-Type", ""))
                category, reason = classifier.classify(course_name=cname, filename=filename, source_type=cand.source_type, source_title=cand.source_title, context_text=cand.context_text, extracted_text=extracted)
                prev = state.setdefault("downloaded", {}).get(key)
                if prev and prev.get("source_updated_at") == cand.source_updated_at and prev.get("category") == category:
                    if verbose:
                        print(f"[skip] {cname} :: {filename} :: unchanged")
                    continue
                state["downloaded"][key] = {
                    "category": category,
                    "reason": reason,
                    "source_updated_at": cand.source_updated_at,
                    "source_type": cand.source_type,
                    "source_title": cand.source_title,
                    "final_url": final_url,
                    "content_type": headers.get("Content-Type", ""),
                    "filename": filename,
                    "course_name": cname,
                    "saved_at": now_utc(),
                }
                if category == "ignore":
                    summary["ignore"] += 1
                    if verbose:
                        print(f"[ignore] {cname} :: {filename} :: {reason}")
                    continue
                dest = course_dir / category / filename
                if dry_run:
                    print(f"[dry-run] {cname} -> {category} :: {filename} :: {reason}")
                else:
                    dest.write_bytes(data)
                    print(f"[saved] {cname} -> {category} :: {filename} :: {reason}")
                    if config.get("pdf_convert"):
                        pdf_path, conv_reason = ensure_pdf(dest, keep_original=config.get("keep_original_after_pdf", False))
                        if pdf_path is not None and pdf_path != dest:
                            summary["converted_to_pdf"] += 1
                            print(f"[pdf] {cname} -> {pdf_path.name} :: {conv_reason}")
                        elif pdf_path is None and verbose:
                            print(f"[pdf-skip] {cname} :: {filename} :: {conv_reason}")
                summary[category] = summary.get(category, 0) + 1
            except Exception as exc:
                summary["errors"] += 1
                print(f"[error] {cname} :: {cand.source_title} :: {cand.file_url} :: {exc}", file=sys.stderr)
        state.setdefault("courses", {})[cid] = {"name": cname, "last_checked_at": now_utc()}
    synced_at = now_utc()
    if not dry_run:
        if mode == "full":
            state["first_full_sync_completed"] = True
            state["last_full_sync_at"] = synced_at
        else:
            state["last_incremental_sync_at"] = synced_at
        state["last_sync_at"] = synced_at
        save_json(state_path, state)
        write_last_update_marker(last_update_path, synced_at)
    print(json.dumps({
        "mode": mode,
        "output_root": str(output_root),
        "state_file": str(state_path),
        "last_update_file": str(last_update_path),
        "last_sync_at": synced_at if not dry_run else state.get("last_sync_at"),
        "summary": summary,
    }, ensure_ascii=False, indent=2))
    return 0 if summary["errors"] == 0 else 1


def finalize_after_run(config_path: Path, config: Dict[str, Any]) -> None:
    state = load_json(Path(config["state_file"]), {})
    update_memory(config_path, config, state)
