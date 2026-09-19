from __future__ import annotations

import os
import sys

ROOT_TEXT = os.environ.get("PDS_ROOT", "")
if not os.path.isfile(os.path.join(ROOT_TEXT, "runtime", "python313.dll")):
    for _entry in sys.path:
        if os.path.basename(_entry).lower() == "python313.zip":
            _runtime_dir = os.path.dirname(_entry)
            ROOT_TEXT = os.path.dirname(_runtime_dir)
            break
LOG_DIR_TEXT = os.path.join(ROOT_TEXT, "logs")
BOOTSTRAP_LOG_TEXT = os.path.join(LOG_DIR_TEXT, "autoload-bootstrap-python.log")


def _early_log(message: str) -> None:
    os.makedirs(LOG_DIR_TEXT, exist_ok=True)
    with open(BOOTSTRAP_LOG_TEXT, "a", encoding="utf-8") as stream:
        stream.write(message + "\n")


_early_log(f"Python {sys.version.split()[0]} | root={ROOT_TEXT!r}")

try:
    import hashlib
    import time
    import traceback
    from pathlib import Path
except BaseException as exc:
    _early_log(f"Import error: {type(exc).__name__}: {exc}")
    raise


ROOT = Path(ROOT_TEXT).resolve()
LOG_DIR = ROOT / "logs"
BOOTSTRAP_LOG = LOG_DIR / "autoload-bootstrap-python.log"


def _log(message: str) -> None:
    _early_log(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}")


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _smoke_test() -> None:
    import cyminhook
    import nmspy
    import pymem
    import pymhf

    versions = (
        f"Python {sys.version.split()[0]}",
        f"pyMHF {getattr(pymhf, '__version__', '?')}",
        f"NMS.py {getattr(nmspy, '__version__', '?')}",
        f"pymem {getattr(pymem, '__version__', 'ok')}",
        f"cyminhook {getattr(cyminhook, '__version__', 'ok')}",
    )
    _log("Smoke test | " + " | ".join(versions))


def _start_pymhf() -> None:
    import nmspy
    import pymem
    import pymhf.core._internal as internal
    from pymhf.core._types import LoadTypeEnum

    exe_path = Path(sys.executable).resolve()
    if exe_path.name.lower() != "nms.exe":
        raise RuntimeError(f"Wrong host: {exe_path}")

    mod_dir = ROOT / "app" / "mod"
    nmspy_dir = Path(nmspy.__file__).resolve().parent
    cache_dir = ROOT / ".cache"
    mod_save_dir = ROOT / "MOD_SAVES"
    cache_dir.mkdir(exist_ok=True)
    mod_save_dir.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    process = pymem.Pymem(os.getpid())
    main_module = process.process_base
    if not main_module:
        raise RuntimeError("NMS module not found")

    config = {
        "exe": "NMS.exe",
        "internal_mod_dir": "{CURR_DIR}/_internal_mods",
        "mod_dir": str(mod_dir),
        "start_exe": False,
        "start_paused": False,
        "interactive_console": False,
        "logging": {
            "shown": False,
            "log_level": "info",
            "log_dir": str(LOG_DIR),
        },
        "gui": {"shown": False},
    }

    internal.MODULE_PATH = str(nmspy_dir)
    internal.BASE_ADDRESS = int(main_module.lpBaseOfDll)
    internal.SIZE_OF_IMAGE = int(main_module.SizeOfImage)
    internal.CWD = str(Path(__file__).resolve().parent)
    internal.PID = os.getpid()
    internal.HANDLE = process.process_handle
    internal.BINARY_HASH = _sha1(exe_path)
    internal.CONFIG = config
    internal.EXE_NAME = "NMS.exe"
    internal.BINARY_PATH = str(exe_path)
    internal.LOAD_TYPE = LoadTypeEnum.LIBRARY.value
    internal.MOD_SAVE_DIR = str(mod_save_dir)
    internal.INCLUDED_ASSEMBLIES = {}
    internal.CACHE_DIR = str(cache_dir)
    internal._SENTINEL_PTR = 0

    injected_path = Path(sys.modules["pymhf"].__file__).resolve().parent / "injected.py"
    _log(f"pyMHF | pid={internal.PID} | base=0x{internal.BASE_ADDRESS:X} | mods={mod_dir}")
    namespace = {
        "__builtins__": __builtins__,
        "__file__": str(injected_path),
        "__name__": "__main__",
        "__package__": None,
    }
    code = compile(injected_path.read_bytes(), str(injected_path), "exec")
    exec(code, namespace, namespace)


def main() -> None:
    os.environ["PYTEST_VERSION"] = "1"
    site_packages = ROOT / "runtime" / "Lib" / "site-packages"
    mod_dir = ROOT / "app" / "mod"
    for path in (str(site_packages), str(mod_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)

    if os.environ.get("PDS_BOOTSTRAP_SMOKE"):
        _smoke_test()
        return
    _start_pymhf()


try:
    main()
except BaseException:
    _log("Fatal\n" + traceback.format_exc())
    raise
