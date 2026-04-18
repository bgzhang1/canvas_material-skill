from __future__ import annotations

import argparse
import json
from pathlib import Path

from .state import default_config_path
from .utils import load_json, save_json
from .sync_core import build_config, finalize_after_run, install_scheduler, load_config, run_sync


def cmd_setup(args: argparse.Namespace) -> int:
    config = build_config(args)
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    config_path = Path(args.config).expanduser().resolve() if args.config else default_config_path(output_root)
    save_json(config_path, config)
    print("\n[setup] 开始首次全量扫描下载...")
    rc = run_sync(config, mode="full", dry_run=False, verbose=args.verbose)
    scheduler_info = install_scheduler(config_path, config)
    config["scheduler"] = scheduler_info
    save_json(config_path, config)
    state = load_json(Path(config["state_file"]), {})
    finalize_after_run(config_path, config)
    print("\n[setup] 初始化完成。")
    print(json.dumps({
        "config_path": str(config_path),
        "output_root": config["output_root"],
        "scheduler": scheduler_info,
        "schedule_enabled": config.get("schedule_enabled", True),
        "first_full_sync_completed": state.get("first_full_sync_completed", False),
        "note": "如果当前客户端支持 app-native automation，也可以额外创建客户端内的定时运行；脚本本身默认优先配置跨环境可复用的系统计划任务。",
    }, ensure_ascii=False, indent=2))
    return rc


def cmd_run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    state = load_json(Path(config["state_file"]), {})
    mode = args.mode
    if mode == "auto":
        mode = "incremental" if state.get("first_full_sync_completed") else "full"
    rc = run_sync(config, mode=mode, dry_run=args.dry_run, verbose=args.verbose)
    finalize_after_run(config_path, config)
    return rc


def cmd_install_scheduler(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    info = install_scheduler(config_path, config)
    config["scheduler"] = info
    save_json(config_path, config)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info.get("enabled") is False or info.get("installed", False) or info.get("backend") == "cron" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canvas material sync with initial full download, remembered state, and scheduled incremental updates.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setup = sub.add_parser("setup", help="Ask configuration questions, run initial full sync, and optionally install scheduler")
    setup.add_argument("--config", help="Optional config path")
    setup.add_argument("--output-root", help="Destination root for organized downloads")
    setup.add_argument("--course", action="append", type=int, help="Limit to one or more course IDs")
    setup.add_argument("--interval-minutes", type=int, help="Incremental scan interval in minutes when schedule type is interval")
    setup.add_argument("--categories", nargs="+", help="Folder categories, e.g. lecture tutorial")
    setup.add_argument("--client-name", help="Override detected client name")
    setup.add_argument("--scheduler-backend", help="Override scheduler backend: windows-task/cron")
    setup.add_argument("--schedule", dest="schedule_enabled", action="store_true", help="Enable scheduled incremental sync")
    setup.add_argument("--no-schedule", dest="schedule_enabled", action="store_false", help="Disable scheduled incremental sync")
    setup.add_argument("--schedule-type", choices=["interval", "daily", "weekly"], help="Schedule style when scheduling is enabled")
    setup.add_argument("--schedule-time", help="Schedule time in HH:MM for daily/weekly scheduling")
    setup.add_argument("--schedule-days", nargs="+", help="Weekdays for weekly scheduling, e.g. mon wed")
    setup.add_argument("--pdf-convert", dest="pdf_convert", action="store_true", help="Enable PDF conversion")
    setup.add_argument("--no-pdf-convert", dest="pdf_convert", action="store_false", help="Disable PDF conversion")
    setup.add_argument("--use-ai", dest="use_ai", action="store_true", help="Enable AI classification if OPENAI_API_KEY is set")
    setup.add_argument("--no-use-ai", dest="use_ai", action="store_false", help="Disable AI classification")
    setup.add_argument("--verbose", action="store_true", help="Verbose logs")
    setup.set_defaults(pdf_convert=None, schedule_enabled=None, use_ai=None, func=cmd_setup)

    run = sub.add_parser("run", help="Run full or incremental sync from an existing config")
    run.add_argument("--config", required=True, help="Path to config JSON")
    run.add_argument("--mode", choices=["auto", "full", "incremental"], default="auto")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--verbose", action="store_true")
    run.set_defaults(func=cmd_run)

    install = sub.add_parser("install-scheduler", help="Install or refresh scheduler from an existing config")
    install.add_argument("--config", required=True, help="Path to config JSON")
    install.set_defaults(func=cmd_install_scheduler)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
