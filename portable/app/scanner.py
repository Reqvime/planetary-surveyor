from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
GAME_ROOT = BUNDLE.parent
GAME_EXE = GAME_ROOT / "Binaries" / "NMS.exe"
DEFAULT_MOD_DIR = GAME_ROOT / "GAMEDATA" / "MODS"
LOG_DIR = BUNDLE / "logs"
BACKUP_CONFIRMED = BUNDLE / "app" / ".backup-confirmed"
MAX_PATH_LENGTH = 259
MOD_FILES = {
    "discovery_probe.py": "NMSDiscoveryLab stage-",
    "planet_object_types.py": "Generated NMS 7.0 scannable object scene hashes",
    "scanner_settings.py": "Persistent user settings for Planetary Discovery Scanner",
}
CONFIG_MARKER = "# Created by Planetary Discovery Scanner"


def _fail(message: str) -> int:
    print(f"Error: {message}")
    return 1


def _config_path() -> Path:
    return Path(os.environ["APPDATA"]) / "pymhf" / "nmspy" / "pymhf.local.toml"


def _game_running() -> bool:
    import psutil

    return any(
        (process.info["name"] or "").lower() == "nms.exe"
        for process in psutil.process_iter(["name"])
    )


def _owned(path: Path, marker: str) -> bool:
    return marker in path.read_text(encoding="utf-8", errors="replace")


def _configured_mod_dir() -> Path | None:
    import tomlkit

    path = _config_path()
    if not path.is_file():
        return None
    local = tomlkit.parse(path.read_text(encoding="utf-8")).get("pymhf", {}).get(
        "local_config", {}
    )
    mod_dir = local.get("mod_dir")
    return Path(str(mod_dir)) if mod_dir else None


def _ensure_config() -> Path:
    import tomlkit

    configured = _configured_mod_dir()
    if configured is not None and configured.is_dir():
        return configured

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup = path.with_name(f"{path.name}.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copyfile(path, backup)
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        document = tomlkit.parse(f"{CONFIG_MARKER}\n")
    pymhf_config = document.setdefault("pymhf", tomlkit.table())
    local = pymhf_config.setdefault("local_config", tomlkit.table())
    logging_config = local.setdefault("logging", tomlkit.table())
    local["mod_dir"] = str(DEFAULT_MOD_DIR)
    local.setdefault("start_paused", True)
    logging_config.setdefault("log_dir", str(LOG_DIR))
    logging_config.setdefault("shown", False)
    path.write_text(tomlkit.dumps(document), encoding="utf-8")
    print(f"Config: {path}")
    return DEFAULT_MOD_DIR


def _confirm_backup_once(assume_yes: bool) -> bool:
    if assume_yes or BACKUP_CONFIRMED.is_file():
        return True
    print("This changes discoveries in your save.")
    answer = input("Save backed up? [y/N] ").strip().lower()
    if answer not in ("y", "yes", "д", "да"):
        return False
    BACKUP_CONFIRMED.write_text("confirmed\n", encoding="ascii")
    return True


def play(dry_run: bool, assume_yes: bool) -> int:
    print("Planetary Surveyor 1.1.0")
    if not GAME_EXE.is_file():
        return _fail("NMS.exe not found. Check the install folder.")
    if _game_running():
        return _fail("No Man's Sky is already running.")
    longest = max(len(str(path)) for path in (BUNDLE / "runtime").rglob("*"))
    if longest > MAX_PATH_LENGTH:
        return _fail(f"Game path is too long ({longest} characters).")
    if not _confirm_backup_once(assume_yes):
        return _fail("Cancelled. Back up the save first.")

    mod_dir = _ensure_config()
    mod_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    for name, marker in MOD_FILES.items():
        source = BUNDLE / "app" / "mod" / name
        target = mod_dir / name
        if target.is_file():
            if not _owned(target, marker):
                return _fail(f"{target} belongs to another mod and was not replaced.")
            if target.read_bytes() == source.read_bytes():
                continue
        shutil.copyfile(source, target)
        print(f"Installed {target}")

    print("On a planet, press F10 once and wait.")
    if dry_run:
        print("Dry run complete.")
        return 0
    print("Starting No Man's Sky...")
    from pymhf import run

    sys.argv = ["pymhf", "run", "nmspy"]
    run()
    return 0


def uninstall() -> int:
    if _game_running():
        return _fail("Close No Man's Sky first.")
    folders = {DEFAULT_MOD_DIR}
    configured = _configured_mod_dir()
    if configured is not None:
        folders.add(configured)
    for folder in folders:
        for name, marker in MOD_FILES.items():
            path = folder / name
            if not path.is_file():
                continue
            if _owned(path, marker):
                path.unlink()
                print(f"Removed {path}")
            else:
                print(f"Skipped {path}")
    config = _config_path()
    if config.is_file() and config.read_text(encoding="utf-8").startswith(CONFIG_MARKER):
        config.unlink()
        print(f"Removed {config}")
    print("Done.")
    return 0


def _documents() -> Path:
    override = os.environ.get("NMSDL_BACKUP_ROOT")
    if override:
        return Path(override)
    buffer = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
        return Path(buffer.value)
    return Path.home() / "Documents"


def _summary(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def backup() -> int:
    if _game_running():
        return _fail("Close No Man's Sky first.")
    source = Path(os.environ["APPDATA"]) / "HelloGames" / "NMS"
    if not source.is_dir():
        return _fail(f"Save folder not found: {source}")
    target = _documents() / "NMS-Save-Backups" / f"NMS-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copytree(source, target)
    if _summary(source) != _summary(target):
        return _fail(f"Backup verification failed: {target}")
    count, size = _summary(target)
    print(f"Backup: {target} ({count} files, {size} bytes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scanner")
    commands = parser.add_subparsers(dest="command", required=True)
    play_parser = commands.add_parser("play")
    play_parser.add_argument("--dry-run", action="store_true")
    play_parser.add_argument("--yes", action="store_true", help="skip backup prompt")
    commands.add_parser("uninstall")
    commands.add_parser("backup")
    args = parser.parse_args()
    if args.command == "play":
        return play(args.dry_run, args.yes)
    if args.command == "uninstall":
        return uninstall()
    return backup()


if __name__ == "__main__":
    sys.exit(main())
