"""Persistent JSON storage for Railway deployments and safe data migration.

Set BOT_DATA_DIR to the Railway Volume mount path (for example /data). On first
startup, existing users.json and progress.json files are merged/copied once so
existing users, sources, welcome text, and settings are retained.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path


_MIGRATION_MARKER = ".resala_storage_migrated_v1"


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[STORAGE] Could not read {path}: {exc}")
        return None


def _atomic_json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=4)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _merge_data(existing, incoming):
    """Merge records without discarding users, source IDs, or saved settings."""
    result = dict(existing or {})
    incoming = incoming or {}

    current_users = result.get("users")
    if not isinstance(current_users, dict):
        current_users = {}
    incoming_users = incoming.get("users")
    if isinstance(incoming_users, dict):
        merged_users = dict(current_users)
        for user_id, incoming_user in incoming_users.items():
            if not isinstance(incoming_user, dict):
                merged_users.setdefault(user_id, incoming_user)
                continue
            current_user = merged_users.get(user_id)
            if not isinstance(current_user, dict):
                merged_users[user_id] = dict(incoming_user)
                continue
            merged_user = dict(incoming_user)
            merged_user.update(current_user)  # Existing destination settings win.
            old_sources = incoming_user.get("sources")
            current_sources = current_user.get("sources")
            if isinstance(old_sources, dict) or isinstance(current_sources, dict):
                merged_sources = dict(old_sources or {})
                merged_sources.update(current_sources or {})
                merged_user["sources"] = merged_sources
            merged_users[user_id] = merged_user
        result["users"] = merged_users
    else:
        result.setdefault("users", current_users)

    # Do not replace an already configured welcome message or app with empty data.
    for key, value in incoming.items():
        if key == "users":
            continue
        if key not in result or result[key] in (None, ""):
            if value not in (None, ""):
                result[key] = value
    result.setdefault("welcome_msg", "مرحباً بك يا {name} 👋")
    result.setdefault("app_file", None)
    return result


def install(bot_module):
    """Install durable load/save functions into the existing bot module."""
    implementation_dir = Path(bot_module.__file__).resolve().parent
    repository_dir = implementation_dir.parent
    configured_dir = os.environ.get("BOT_DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    data_dir = Path(configured_dir).expanduser() if configured_dir else implementation_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    users_path = data_dir / "users.json"
    progress_path = data_dir / "progress.json"
    source_users = [repository_dir / "users.json", implementation_dir / "users.json"]
    source_progress = [repository_dir / "progress.json", implementation_dir / "progress.json"]
    marker = data_dir / _MIGRATION_MARKER

    def migrate_once():
        if marker.exists():
            return
        merged = _read_json(users_path) or {}
        # Merge repo and package copies once, preserving any records in both.
        for source_path in source_users:
            if source_path.resolve() == users_path.resolve() or not source_path.exists():
                continue
            source_data = _read_json(source_path)
            if source_data is not None:
                merged = _merge_data(merged, source_data)
        if merged:
            _atomic_json_write(users_path, merged)

        if not progress_path.exists():
            for source_path in source_progress:
                if source_path.resolve() == progress_path.resolve() or not source_path.exists():
                    continue
                try:
                    shutil.copy2(source_path, progress_path)
                    break
                except OSError as exc:
                    print(f"[STORAGE] Could not migrate {source_path}: {exc}")
        marker.write_text("done\n", encoding="utf-8")
        print(f"[STORAGE] One-time data migration finished into {data_dir}")

    migrate_once()
    bot_module.DB_FILE = str(users_path)
    bot_module.PROGRESS_FILE = str(progress_path)

    if not configured_dir and os.environ.get("RAILWAY_ENVIRONMENT"):
        print(
            "[STORAGE] WARNING: no Railway Volume path configured. Data is stored "
            "in the deployment filesystem and may be lost on redeploy. Set "
            "BOT_DATA_DIR to the mounted Volume path (for example /data)."
        )
    else:
        print(f"[STORAGE] Persistent data directory: {data_dir}")

    def load_data():
        data = _read_json(users_path)
        if data is None:
            return {"users": {}, "welcome_msg": "مرحباً بك يا {name} 👋", "app_file": None}
        if not isinstance(data.get("users"), dict):
            data["users"] = {}
        data.setdefault("welcome_msg", "مرحباً بك يا {name} 👋")
        data.setdefault("app_file", None)
        return data

    def save_data(data):
        if not isinstance(data, dict):
            raise TypeError("Bot data must be a dictionary")
        _atomic_json_write(users_path, data)

    bot_module.load_data = load_data
    bot_module.save_data = save_data
    return data_dir
