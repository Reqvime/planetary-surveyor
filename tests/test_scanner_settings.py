from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.scanner_settings import ScannerSettings, _infer_game_root, load_settings


class ScannerSettingsTests(unittest.TestCase):
    def test_infers_game_root_for_autoload_bundle(self) -> None:
        module = Path(
            "C:/Games/NMS/PlanetaryDiscoveryScanner/app/mod/scanner_settings.py"
        )
        self.assertEqual(_infer_game_root(module), Path("C:/Games/NMS"))

    def test_infers_game_root_for_source_and_nms_py_layouts(self) -> None:
        source = Path("C:/Games/NMS/NMSDiscoveryLab/src/scanner_settings.py")
        drop_in = Path("C:/Games/NMS/GAMEDATA/MODS/scanner_settings.py")
        self.assertEqual(_infer_game_root(source), Path("C:/Games/NMS"))
        self.assertEqual(_infer_game_root(drop_in), Path("C:/Games/NMS"))

    def test_missing_file_is_created_with_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "PlanetaryDiscoveryScanner.ini"

            settings = load_settings(path)

            self.assertEqual(settings, ScannerSettings())
            self.assertTrue(path.is_file())
            self.assertIn("[Scanner]", path.read_text(encoding="utf-8"))

    def test_reads_fauna_mode_and_user_controls(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.ini"
            path.write_text(
                "[Scanner]\n"
                "Mode=FaunaOnly\n"
                "SubmitDelayMs=750\n"
                "SoundFeedback=yes\n"
                "EnableHotkey=no\n"
                "ScanKey=F10\n",
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings.scan_mode, "fauna")
            self.assertEqual(settings.submit_delay_ms, 750)
            self.assertEqual(settings.submit_interval_seconds, 0.75)
            self.assertTrue(settings.sound_feedback)
            self.assertFalse(settings.enable_hotkey)
            self.assertEqual(settings.scan_key, "f10")

    def test_invalid_values_fall_back_and_delay_is_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.ini"
            path.write_text(
                "[Scanner]\n"
                "Mode=unknown\n"
                "SubmitDelayMs=9000\n"
                "SoundFeedback=perhaps\n"
                "EnableHotkey=maybe\n"
                "ScanKey=Space\n",
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings.scan_mode, "fauna")
            self.assertEqual(settings.submit_delay_ms, 1500)
            self.assertTrue(settings.sound_feedback)
            self.assertTrue(settings.enable_hotkey)
            self.assertEqual(settings.scan_key, "f10")

    def test_too_small_delay_is_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.ini"
            path.write_text(
                "[Scanner]\nSubmitDelayMs=1\n",
                encoding="utf-8",
            )

            self.assertEqual(load_settings(path).submit_delay_ms, 250)


if __name__ == "__main__":
    unittest.main()
