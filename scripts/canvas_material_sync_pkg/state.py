from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .constants import MEMORY_PATH
from .utils import load_json, now_utc, save_json


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
