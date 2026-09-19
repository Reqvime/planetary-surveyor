from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = PROJECT_ROOT / "autoload" / "autoload_installer.py"


def _load_installer():
    spec = importlib.util.spec_from_file_location("pds_test_autoload_installer", INSTALLER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutoloadInstallerTests(unittest.TestCase):
    def _fixture(self, root: Path):
        installer = _load_installer()
        bundle = root / "PlanetaryDiscoveryScanner"
        binaries = root / "Binaries"
        loader = bundle / "app" / "loader"
        loader.mkdir(parents=True)
        binaries.mkdir()
        (binaries / "NMS.exe").write_bytes(b"test executable")
        (loader / "PlanetaryDiscoveryScanner.mods").write_bytes(
            b"native " + installer.SCANNER_MARKER
        )
        (loader / "PlanetaryDiscoveryScanner.ini").write_text(
            "[Scanner]\nMode=All\n", encoding="utf-8"
        )
        (loader / "version.dll").write_bytes(b"proxy " + installer.VERSION_MARKER)

        installer.BUNDLE = bundle
        installer.GAME_ROOT = root
        installer.BINARIES = binaries
        installer.GAME_EXE = binaries / "NMS.exe"
        installer.LOADER_SOURCE = loader
        installer.SCANNER_SOURCE = loader / "PlanetaryDiscoveryScanner.mods"
        installer.SETTINGS_SOURCE = loader / "PlanetaryDiscoveryScanner.ini"
        installer.VERSION_SOURCE = loader / "version.dll"
        installer.SCANNER_TARGET = binaries / "PlanetaryDiscoveryScanner.mods"
        installer.SETTINGS_TARGET = binaries / "PlanetaryDiscoveryScanner.ini"
        installer.VERSION_TARGET = binaries / "version.dll"
        installer.STATE_PATH = bundle / "app" / "autoload-state.json"
        installer.LOG_PATH = bundle / "logs" / "installer.log"
        installer._game_running = lambda: False
        installer._message = lambda message, error=False: None
        return installer

    def test_installs_and_removes_owned_version_loader(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = self._fixture(Path(temporary))
            installer.install()
            state = json.loads(installer.STATE_PATH.read_text(encoding="utf-8"))
            self.assertEqual(state["version_loader"], "installed")
            self.assertTrue(installer.VERSION_TARGET.is_file())
            self.assertTrue(installer.SCANNER_TARGET.is_file())
            self.assertTrue(installer.SETTINGS_TARGET.is_file())

            installer.uninstall()
            self.assertFalse(installer.VERSION_TARGET.exists())
            self.assertFalse(installer.SCANNER_TARGET.exists())
            # Keep user settings so a reinstall preserves custom choices.
            self.assertTrue(installer.SETTINGS_TARGET.is_file())

    def test_preserves_compatible_third_party_loader(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = self._fixture(Path(temporary))
            original = b"third-party loader supports *.mods"
            installer.VERSION_TARGET.write_bytes(original)

            installer.install()
            state = json.loads(installer.STATE_PATH.read_text(encoding="utf-8"))
            self.assertEqual(state["version_loader"], "existing")
            self.assertEqual(installer.VERSION_TARGET.read_bytes(), original)

            installer.uninstall()
            self.assertEqual(installer.VERSION_TARGET.read_bytes(), original)
            self.assertFalse(installer.SCANNER_TARGET.exists())

    def test_preserves_existing_user_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = self._fixture(Path(temporary))
            existing = "[Scanner]\nMode=FaunaOnly\nSubmitDelayMs=750\n"
            installer.SETTINGS_TARGET.write_text(existing, encoding="utf-8")

            installer.install()

            self.assertEqual(
                installer.SETTINGS_TARGET.read_text(encoding="utf-8"), existing
            )

    def test_rejects_incompatible_third_party_loader_before_copying(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = self._fixture(Path(temporary))
            installer.VERSION_TARGET.write_bytes(b"unrelated proxy")

            with self.assertRaisesRegex(RuntimeError, "does not advertise"):
                installer.install()
            self.assertFalse(installer.SCANNER_TARGET.exists())

    def test_rejects_unowned_scanner_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = self._fixture(Path(temporary))
            installer.VERSION_TARGET.write_bytes(b"compatible *.mods loader")
            installer.SCANNER_TARGET.write_bytes(b"not our module")

            with self.assertRaisesRegex(RuntimeError, "not owned"):
                installer.install()


if __name__ == "__main__":
    unittest.main()
