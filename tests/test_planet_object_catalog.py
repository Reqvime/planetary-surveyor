from __future__ import annotations

import ctypes
import struct
import time
import unittest
from pathlib import Path
from unittest import mock

from src import discovery_probe
from src.discovery_probe import (
    DiscoveryProbe,
    _GAME_FUNCTION_SIGNATURES,
    _IS_DISCOVERY_KNOWN_APPLICATION_LOAD_OFFSET,
    _DiscoveryData,
    _GameAddresses,
    _GAME_LAYOUTS,
    _PLANET_DISCOVERY_DATA_OFFSET,
    _PLANET_STRIDE,
    _SOLAR_PLANETS_OFFSET,
    _SOLAR_PLANET_COUNT_OFFSET,
    _PLANET_OBJECT_SPAWN_ARRAY_OFFSETS,
    _PLANET_OBJECT_SPAWN_CAPACITY_OFFSET,
    _PLANET_OBJECT_SPAWN_FILENAME_OFFSET,
    _PLANET_OBJECT_SPAWN_SEED_OFFSET,
    _PLANET_OBJECT_SPAWN_SIZE_OFFSET,
    _PLANET_OBJECT_SPAWN_STRIDE,
    _PLANET_OBJECT_SPAWN_USE_SEED_OFFSET,
    _SceneCandidate,
    _SubmitBatch,
    _djb2_64,
    _find_unique_pattern,
    _game_window_is_foreground,
    _read_planet_object_catalog,
    _resolve_game_addresses,
    _select_game_layout,
)
from src.planet_object_types import FLORA_SCENE_HASHES, MINERAL_SCENE_HASHES

_BIOMES = "MODELS/PLANETS/BIOMES/"
SMALLPLANT = _BIOMES + "COMMON/PLANTS/SMALLPLANT.SCENE.MBIN"
MEDIUMROCK = _BIOMES + "COMMON/ROCKS/MEDIUM/MEDIUMROCK.SCENE.MBIN"
STEAMVENT = _BIOMES + "UNDERWATER/INTERACTIVE/STEAMVENT.SCENE.MBIN"
FISHFIENDROCK = _BIOMES + "UNDERWATER/INTERACTIVE/FISHFIENDROCK.SCENE.MBIN"
UNSCANNABLE = _BIOMES + "COMMON/BUILDINGS/DEBRIS/DEBRISLARGE_COMMON.SCENE.MBIN"
DESCRIPTOR = _BIOMES + "COMMON/PLANTS/SMALLPLANT.DESCRIPTOR.MBIN"
UNIVERSE_ADDRESS = 18072676793524483
GAME_EXE = Path(__file__).resolve().parents[2] / "Binaries" / "NMS.exe"
# IsDiscoveryKnown from NMS.exe 178994 with the rip displacement cut out.
IS_KNOWN_PREFIX = bytes.fromhex("4883EC28488B0D")
IS_KNOWN_SUFFIX = bytes.fromhex("4881C138E82C00E899F621FF4885C07410F68007020000087507B001")


def _make_planet(*arrays: tuple[list[tuple[str | None, int, int]], int | None]):
    """Build planet memory holding the three spawn arrays in the 178938 layout.

    Each array is (slots, capacity); a slot is (filename, seed, use_seed), where
    a filename of None stands for a string pointer into unreadable memory.
    Returns the planet address and the buffers that must stay alive.
    """
    keep: list[ctypes.Array] = []
    planet = ctypes.create_string_buffer(max(_PLANET_OBJECT_SPAWN_ARRAY_OFFSETS) + 8)
    keep.append(planet)
    for offset, (slots, capacity) in zip(_PLANET_OBJECT_SPAWN_ARRAY_OFFSETS, arrays):
        pointer = 0
        if slots:
            elements = ctypes.create_string_buffer(len(slots) * _PLANET_OBJECT_SPAWN_STRIDE)
            keep.append(elements)
            pointer = ctypes.addressof(elements)
            for index, (filename, seed, use_seed) in enumerate(slots):
                base = index * _PLANET_OBJECT_SPAWN_STRIDE
                if filename is None:
                    name_pointer, name_size = 0x10, 32
                else:
                    name = ctypes.create_string_buffer(filename.encode("ascii"))
                    keep.append(name)
                    name_pointer, name_size = ctypes.addressof(name), len(filename) + 1
                struct.pack_into(
                    "<Q", elements, base + _PLANET_OBJECT_SPAWN_FILENAME_OFFSET,
                    name_pointer,
                )
                # The game leaves unrelated bytes above the 32-bit string length.
                struct.pack_into(
                    "<Q", elements, base + _PLANET_OBJECT_SPAWN_FILENAME_OFFSET + 8,
                    (0xBEEF << 48) | name_size,
                )
                struct.pack_into(
                    "<Q", elements, base + _PLANET_OBJECT_SPAWN_SEED_OFFSET, seed
                )
                struct.pack_into(
                    "<B", elements, base + _PLANET_OBJECT_SPAWN_USE_SEED_OFFSET, use_seed
                )
        size = len(slots)
        struct.pack_into(
            "<I", planet, offset + _PLANET_OBJECT_SPAWN_CAPACITY_OFFSET,
            size if capacity is None else capacity,
        )
        struct.pack_into("<I", planet, offset + _PLANET_OBJECT_SPAWN_SIZE_OFFSET, size)
        struct.pack_into("<Q", planet, offset, pointer)
    return ctypes.addressof(planet), keep


class PlanetObjectCatalogTests(unittest.TestCase):
    def test_generated_types_apply_runtime_overrides(self) -> None:
        self.assertEqual(_djb2_64(STEAMVENT), 0xCDB6CF21B532CF10)
        self.assertEqual(_djb2_64(FISHFIENDROCK), 0xE68FD63426773658)
        self.assertNotIn(_djb2_64(STEAMVENT), FLORA_SCENE_HASHES | MINERAL_SCENE_HASHES)
        self.assertIn(_djb2_64(FISHFIENDROCK), MINERAL_SCENE_HASHES)

    def test_reads_classified_seeded_slots_from_all_spawn_arrays(self) -> None:
        planet, keep = _make_planet(
            ([], None),
            (
                [
                    (SMALLPLANT, 1, 1),
                    (MEDIUMROCK, 2, 1),
                    (STEAMVENT, 3, 1),
                    (FISHFIENDROCK, 4, 1),
                    (UNSCANNABLE, 5, 1),
                    (DESCRIPTOR, 6, 1),
                    (SMALLPLANT, 7, 0),  # Seedless slots have no discovery key0.
                    (SMALLPLANT.lower().replace("/", "\\"), 1, 1),  # Same identity.
                ],
                None,
            ),
            ([(MEDIUMROCK, 2, 1), (None, 9, 1), (SMALLPLANT, 8, 1)], 16),
        )

        snapshot = _read_planet_object_catalog(planet, UNIVERSE_ADDRESS)

        self.assertIsNone(snapshot.error)
        self.assertEqual(snapshot.array_sizes, (0, 8, 3))
        self.assertEqual(snapshot.matching_slots, 7)
        self.assertEqual(snapshot.unseeded_slots, 1)
        self.assertEqual(snapshot.invalid_slots, 1)
        self.assertEqual(snapshot.unclassified_scenes, ((STEAMVENT, 1), (UNSCANNABLE, 1)))
        self.assertEqual(
            [
                (int(entry.data.discovery_type), entry.seed, entry.scene_hash,
                 entry.array_index, entry.slot)
                for entry in snapshot.entries
            ],
            [
                (4, 1, _djb2_64(SMALLPLANT), 1, 0),
                (5, 2, _djb2_64(MEDIUMROCK), 1, 1),
                (5, 4, _djb2_64(FISHFIENDROCK), 1, 3),
                (4, 8, _djb2_64(SMALLPLANT), 2, 2),
            ],
        )
        for entry in snapshot.entries:
            self.assertEqual(entry.data.universe_address, UNIVERSE_ADDRESS)
            self.assertEqual(entry.data.key_count, 2)
            self.assertEqual(tuple(entry.data.keys[:2]), (entry.seed, entry.scene_hash))
        self.assertTrue(keep)

    def test_rejects_spawn_array_larger_than_capacity(self) -> None:
        planet, keep = _make_planet(
            ([(SMALLPLANT, 1, 1), (SMALLPLANT, 2, 1), (SMALLPLANT, 3, 1)], 2),
            ([], None),
            ([], None),
        )
        snapshot = _read_planet_object_catalog(planet, UNIVERSE_ADDRESS)
        self.assertEqual(snapshot.error, "spawn_array_size_invalid")
        self.assertEqual(snapshot.entries, ())
        self.assertTrue(keep)

    def test_reports_planet_without_generated_spawn_arrays(self) -> None:
        planet, keep = _make_planet(([], None), ([], None), ([], None))
        snapshot = _read_planet_object_catalog(planet, UNIVERSE_ADDRESS)
        self.assertEqual(snapshot.error, "spawn_arrays_empty")
        self.assertEqual(snapshot.array_sizes, (0, 0, 0))
        self.assertTrue(keep)


class SubmitFocusGuardTests(unittest.TestCase):
    def _make_batch(self) -> _SubmitBatch:
        candidate = _SceneCandidate(
            0, 0, -1, 0, 0.0, 0.0, 0.0, 0.0, "planet_object_catalog"
        )
        return _SubmitBatch(
            sequence=1,
            addresses=_GameAddresses(0, 0, 0, 0),
            application_data=0,
            discovery_manager=0,
            items=[(candidate, _DiscoveryData())],
            nearby_candidates=0,
            resolver_attempted=0,
            resolver_successful=0,
            interesting_resolutions=0,
            unique_discoveries=1,
            target_resolved=False,
            logged_resolved=0,
            type_text="none",
            unique_text="none",
            already_known=0,
            unknown=1,
            submit_truncated=False,
        )

    def test_foreground_check_returns_bool(self) -> None:
        self.assertIsInstance(_game_window_is_foreground(), bool)

    def test_queue_pauses_without_focus_and_waits_one_interval_after_resume(self) -> None:
        probe = DiscoveryProbe()
        batch = self._make_batch()
        probe._stage6_batch = batch

        with mock.patch.object(
            discovery_probe, "_game_window_is_foreground", return_value=False
        ):
            probe._submit_next_queued_discovery()
            probe._submit_next_queued_discovery()
        self.assertTrue(batch.focus_paused)
        self.assertEqual(batch.focus_pauses, 1)
        self.assertEqual(batch.next_index, 0)

        with mock.patch.object(
            discovery_probe, "_game_window_is_foreground", return_value=True
        ):
            probe._submit_next_queued_discovery()
        self.assertFalse(batch.focus_paused)
        self.assertEqual(batch.next_index, 0)
        self.assertGreater(batch.next_submit_time, time.monotonic())
        self.assertIs(probe._stage6_batch, batch)


def _signature_bytes(pattern: str) -> bytes:
    return bytes(0 if token in ("?", "??") else int(token, 16) for token in pattern.split())


def _is_known_code(code_rva: int, pointer_rva: int) -> bytes:
    load = code_rva + _IS_DISCOVERY_KNOWN_APPLICATION_LOAD_OFFSET
    return IS_KNOWN_PREFIX + struct.pack("<i", pointer_rva - (load + 7)) + IS_KNOWN_SUFFIX


def _make_module(functions: dict[int, bytes], size: int = 0x4000) -> ctypes.Array:
    """Minimal loaded PE image with one .text section at RVA 0x1000."""
    image = ctypes.create_string_buffer(size)
    pe = 0x80
    struct.pack_into("<I", image, 0x3C, pe)
    image[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<H", image, pe + 6, 1)  # NumberOfSections
    struct.pack_into("<H", image, pe + 20, 0xF0)  # SizeOfOptionalHeader
    struct.pack_into("<I", image, pe + 24 + 56, size)  # SizeOfImage
    struct.pack_into("<8sII", image, pe + 24 + 0xF0, b".text", 0x2000, 0x1000)
    for rva, code in functions.items():
        image[rva:rva + len(code)] = code
    return image


class GameAddressTests(unittest.TestCase):
    SUBMIT = _signature_bytes(_GAME_FUNCTION_SIGNATURES["SubmitDiscoveryData"])
    POST = _signature_bytes(_GAME_FUNCTION_SIGNATURES["PostSubmitDiscovery"])

    def test_finds_unique_clean_or_detoured_signature(self) -> None:
        pattern = _GAME_FUNCTION_SIGNATURES["PostSubmitDiscovery"]
        padding = b"\xCC" * 16
        self.assertEqual(_find_unique_pattern(padding + self.POST + padding, pattern), 16)
        detoured = b"\xE9\x11\x22\x33\x44" + self.POST[5:]
        self.assertEqual(_find_unique_pattern(padding + detoured, pattern), 16)
        self.assertIsNone(_find_unique_pattern(self.POST + padding + self.POST, pattern))
        self.assertIsNone(_find_unique_pattern(padding * 4, pattern))

    def test_resolves_functions_and_application_pointer_from_module(self) -> None:
        image = _make_module({
            0x1100: b"\xE9\x11\x22\x33\x44" + self.SUBMIT[5:],  # Hooked by pyMHF.
            0x1400: self.POST,
            0x1800: _is_known_code(0x1800, 0x3800),
        })
        base = ctypes.addressof(image)

        addresses, result = _resolve_game_addresses(base)

        self.assertEqual(result, "ok")
        self.assertEqual(
            addresses,
            _GameAddresses(base + 0x1100, base + 0x1400, base + 0x1800, base + 0x3800),
        )

    def test_rejects_ambiguous_signature_and_foreign_pointer(self) -> None:
        ambiguous = _make_module({
            0x1100: self.SUBMIT,
            0x1400: self.POST,
            0x1800: _is_known_code(0x1800, 0x3800),
            0x2000: self.POST,
        })
        self.assertEqual(
            _resolve_game_addresses(ctypes.addressof(ambiguous)),
            (None, "PostSubmitDiscovery_signature_unresolved"),
        )
        foreign = _make_module({
            0x1100: self.SUBMIT,
            0x1400: self.POST,
            0x1800: _is_known_code(0x1800, 0x9000),
        })
        self.assertEqual(
            _resolve_game_addresses(ctypes.addressof(foreign)),
            (None, "application_data_pointer_invalid"),
        )

    @unittest.skipUnless(GAME_EXE.is_file(), "installed NMS.exe not found")
    def test_signatures_resolve_in_installed_game(self) -> None:
        data = GAME_EXE.read_bytes()
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        count = struct.unpack_from("<H", data, pe + 6)[0]
        optional = struct.unpack_from("<H", data, pe + 20)[0]
        sections = {}
        for index in range(count):
            name, virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
                "<8sIIII", data, pe + 24 + optional + index * 40
            )
            sections[name.rstrip(b"\0")] = (virtual_address, virtual_size, raw_pointer, raw_size)
        text_rva, _, text_raw, text_size = sections[b".text"]
        text = data[text_raw:text_raw + text_size]

        offsets = {}
        for name, pattern in _GAME_FUNCTION_SIGNATURES.items():
            with self.subTest(function=name):
                offsets[name] = _find_unique_pattern(text, pattern)
                self.assertIsNotNone(offsets[name])
        load = offsets["IsDiscoveryKnown"] + _IS_DISCOVERY_KNOWN_APPLICATION_LOAD_OFFSET
        pointer_rva = text_rva + load + 7 + struct.unpack_from("<i", text, load + 3)[0]
        data_rva, data_size, _, _ = sections[b".data"]
        self.assertTrue(data_rva <= pointer_rva < data_rva + data_size)


class GameLayoutTests(unittest.TestCase):
    def test_selects_validated_new_or_legacy_layout(self) -> None:
        application_data = 0x10000000
        current_address = 0x00109000052FF9C0
        solar_system = 0x20000000
        expected = _GAME_LAYOUTS[1]
        planet_index = 2
        qwords = {
            application_data + expected.current_planet_address_offset: current_address,
            application_data + expected.solar_system_pointer_offset: solar_system,
            solar_system
            + _SOLAR_PLANETS_OFFSET
            + planet_index * _PLANET_STRIDE
            + _PLANET_DISCOVERY_DATA_OFFSET: current_address,
        }
        integers = {solar_system + _SOLAR_PLANET_COUNT_OFFSET: 3}

        with (
            mock.patch.object(
                discovery_probe, "_read_u64", side_effect=lambda address: qwords.get(address)
            ),
            mock.patch.object(
                discovery_probe, "_read_i32", side_effect=lambda address: integers.get(address)
            ),
        ):
            layout, result = _select_game_layout(application_data)

        self.assertEqual(result, "ok")
        self.assertEqual(layout, expected)

    def test_rejects_unvalidated_layouts(self) -> None:
        with (
            mock.patch.object(discovery_probe, "_read_u64", return_value=0),
            mock.patch.object(discovery_probe, "_read_i32", return_value=None),
        ):
            layout, result = _select_game_layout(0x10000000)

        self.assertIsNone(layout)
        self.assertEqual(result, "planet_catalog_context_unreadable")


if __name__ == "__main__":
    unittest.main()
