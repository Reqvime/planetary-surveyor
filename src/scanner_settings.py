from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger("DiscoveryProbe.Settings")
OWNER = "Persistent user settings for Planetary Discovery Scanner"

_MIN_SUBMIT_DELAY_MS = 250
_MAX_SUBMIT_DELAY_MS = 1500
_VALID_SCAN_KEYS = frozenset(f"f{number}" for number in range(1, 13))
_DEFAULT_CONFIG_TEXT = (
    "[Scanner]\n"
    "Mode=FaunaOnly\n"
    "SubmitDelayMs=500\n"
    "SoundFeedback=true\n"
    "EnableHotkey=true\n"
    "ScanKey=F10\n"
)


@dataclass(frozen=True)
class ScannerSettings:
    scan_mode: str = "fauna"
    submit_delay_ms: int = 500
    sound_feedback: bool = True
    enable_hotkey: bool = True
    scan_key: str = "f10"

    @property
    def submit_interval_seconds(self) -> float:
        return self.submit_delay_ms / 1000.0


def settings_path() -> Path:
    override = os.environ.get("PDS_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()

    bundle_root = os.environ.get("PDS_ROOT")
    if bundle_root:
        return Path(bundle_root).resolve().parent / "Binaries" / "PlanetaryDiscoveryScanner.ini"

    return _infer_game_root(Path(__file__)) / "Binaries" / "PlanetaryDiscoveryScanner.ini"


def _infer_game_root(module_file: Path) -> Path:
    resolved = module_file.resolve()
    module_dir = resolved.parent
    if module_dir.name.casefold() == "mod" and module_dir.parent.name.casefold() == "app":
        return module_dir.parent.parent.parent
    return resolved.parents[2]


def _normalise_mode(value: str) -> str:
    mode = value.strip().lower().replace("_", " ").replace("-", " ")
    if mode in {"fauna", "faunaonly", "fauna only", "animals", "animals only"}:
        return "fauna"
    if mode in {"all", "full", "everything"}:
        return "all"
    raise ValueError("Mode must be All or FaunaOnly")


def _parse_bool(section: configparser.SectionProxy, name: str, default: bool) -> bool:
    try:
        return section.getboolean(name, fallback=default)
    except ValueError:
        logger.warning("Invalid %s value; using %s", name, default)
        return default


def _parse_delay(section: configparser.SectionProxy) -> int:
    raw = section.get("SubmitDelayMs", fallback="500").strip()
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid SubmitDelayMs=%r; using 500", raw)
        return 500
    clamped = max(_MIN_SUBMIT_DELAY_MS, min(_MAX_SUBMIT_DELAY_MS, value))
    if clamped != value:
        logger.warning(
            "SubmitDelayMs=%d is outside %d-%d; using %d",
            value,
            _MIN_SUBMIT_DELAY_MS,
            _MAX_SUBMIT_DELAY_MS,
            clamped,
        )
    return clamped


def _parse_scan_key(section: configparser.SectionProxy) -> str:
    raw = section.get("ScanKey", fallback="F10").strip().lower()
    if raw in _VALID_SCAN_KEYS:
        return raw
    logger.warning("Invalid ScanKey=%r; only F1-F12 are supported; using F10", raw)
    return "f10"


def _write_default_if_missing(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_DEFAULT_CONFIG_TEXT)
    except FileExistsError:
        pass


def load_settings(path: Path | None = None) -> ScannerSettings:
    config_path = path or settings_path()
    try:
        _write_default_if_missing(config_path)
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8-sig")
        section = parser["Scanner"] if parser.has_section("Scanner") else parser[parser.default_section]
        try:
            scan_mode = _normalise_mode(section.get("Mode", fallback="FaunaOnly"))
        except ValueError as exc:
            logger.warning("%s; using FaunaOnly", exc)
            scan_mode = "fauna"
        return ScannerSettings(
            scan_mode=scan_mode,
            submit_delay_ms=_parse_delay(section),
            sound_feedback=_parse_bool(section, "SoundFeedback", True),
            enable_hotkey=_parse_bool(section, "EnableHotkey", True),
            scan_key=_parse_scan_key(section),
        )
    except (OSError, configparser.Error):
        logger.exception("Unable to read %s; using built-in defaults", config_path)
        return ScannerSettings()


INITIAL_SETTINGS = load_settings()
