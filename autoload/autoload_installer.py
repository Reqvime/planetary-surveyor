"""GUI installer for the no-console Steam/Epic autoload package."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
GAME_ROOT = BUNDLE.parent
BINARIES = GAME_ROOT / "Binaries"
GAME_EXE = BINARIES / "NMS.exe"
LOADER_SOURCE = BUNDLE / "app" / "loader"
SCANNER_SOURCE = LOADER_SOURCE / "PlanetaryDiscoveryScanner.mods"
SETTINGS_SOURCE = LOADER_SOURCE / "PlanetaryDiscoveryScanner.ini"
VERSION_SOURCE = LOADER_SOURCE / "version.dll"
SCANNER_TARGET = BINARIES / "PlanetaryDiscoveryScanner.mods"
SETTINGS_TARGET = BINARIES / "PlanetaryDiscoveryScanner.ini"
VERSION_TARGET = BINARIES / "version.dll"
STATE_PATH = BUNDLE / "app" / "autoload-state.json"
LOG_PATH = BUNDLE / "logs" / "installer.log"
SCANNER_MARKER = b"PDS_AUTOLOAD_MODULE_V1"
VERSION_MARKER = b"PDS_VERSION_LOADER_V1"


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def _message(message: str, *, error: bool = False) -> None:
    if os.environ.get("PDS_INSTALLER_SILENT"):
        return
    flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
    ctypes.windll.user32.MessageBoxW(
        None,
        message,
        "Planetary Discovery Scanner",
        flags,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _contains(path: Path, marker: bytes) -> bool:
    return marker in path.read_bytes()


def _game_running() -> bool:
    import psutil

    return any(
        (process.info["name"] or "").lower() == "nms.exe"
        for process in psutil.process_iter(["name"])
    )


def _supports_mods(existing_version: Path) -> bool:
    data = existing_version.read_bytes()
    return VERSION_MARKER in data or b"*.mods" in data.lower()


def _atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_name(target.name + ".pds-new")
    shutil.copyfile(source, temporary)
    if _sha256(temporary) != _sha256(source):
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"copy verification failed: {target}")
    os.replace(temporary, target)


def install() -> None:
    if _game_running():
        raise RuntimeError("No Man's Sky is running. Close the game and run the installer again.")
    if not GAME_EXE.is_file():
        raise RuntimeError(
            "Place the PlanetaryDiscoveryScanner folder in the No Man's Sky folder, "
            "next to Binaries and GAMEDATA, then run this installer again."
        )
    for source in (SCANNER_SOURCE, SETTINGS_SOURCE, VERSION_SOURCE):
        if not source.is_file():
            raise RuntimeError(f"The release package is incomplete: {source.name} is missing.")

    if VERSION_TARGET.is_file() and not _supports_mods(VERSION_TARGET):
        raise RuntimeError(
            "Binaries\\version.dll belongs to another loader that does not advertise *.mods "
            "support. It was not replaced. Remove or reconfigure that loader first."
        )
    if SCANNER_TARGET.is_file() and not (
        _contains(SCANNER_TARGET, SCANNER_MARKER)
        or _sha256(SCANNER_TARGET) == _sha256(SCANNER_SOURCE)
    ):
        raise RuntimeError(
            "Binaries\\PlanetaryDiscoveryScanner.mods exists but is not owned by this package. "
            "It was not replaced."
        )

    version_mode = "existing"
    settings_created = not SETTINGS_TARGET.exists()
    if not VERSION_TARGET.exists():
        _atomic_copy(VERSION_SOURCE, VERSION_TARGET)
        version_mode = "installed"
    _atomic_copy(SCANNER_SOURCE, SCANNER_TARGET)
    if not SETTINGS_TARGET.exists():
        _atomic_copy(SETTINGS_SOURCE, SETTINGS_TARGET)

    state = {
        "version_loader": version_mode,
        "version_hash": _sha256(VERSION_TARGET),
        "scanner_hash": _sha256(SCANNER_TARGET),
        "settings_created": settings_created,
    }
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    _log(f"install ok version_loader={version_mode}")
    _message(
        "Installation complete.\n\n"
        "Start No Man's Sky normally from Steam or Epic Games. "
        "On a planet, wait a few seconds and press F10.\n\n"
        f"Version loader: {version_mode}."
    )


def uninstall() -> None:
    if _game_running():
        raise RuntimeError("No Man's Sky is running. Close the game and run the uninstaller again.")
    state: dict[str, str] = {}
    if STATE_PATH.is_file():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    removed: list[str] = []
    retained: list[str] = []
    if SCANNER_TARGET.is_file():
        if _contains(SCANNER_TARGET, SCANNER_MARKER):
            SCANNER_TARGET.unlink()
            removed.append(str(SCANNER_TARGET))
        else:
            retained.append(str(SCANNER_TARGET))

    if state.get("version_loader") == "installed" and VERSION_TARGET.is_file():
        if _contains(VERSION_TARGET, VERSION_MARKER):
            VERSION_TARGET.unlink()
            removed.append(str(VERSION_TARGET))
        else:
            retained.append(str(VERSION_TARGET))

    STATE_PATH.unlink(missing_ok=True)
    _log(f"uninstall removed={removed!r} retained={retained!r}")
    details = "\n".join(f"Removed: {item}" for item in removed) or "No native files were present."
    if retained:
        details += "\n\nLeft untouched because ownership could not be proven:\n" + "\n".join(retained)
    _message(details + "\n\nYou can now delete the PlanetaryDiscoveryScanner folder.")


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "install"
    try:
        if command == "install":
            install()
        elif command == "uninstall":
            uninstall()
        else:
            raise RuntimeError(f"Unknown installer command: {command}")
        return 0
    except BaseException as exc:
        _log("fatal error\n" + traceback.format_exc())
        _message(str(exc), error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
