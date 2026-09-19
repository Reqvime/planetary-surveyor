from __future__ import annotations

import ctypes
import struct
import unittest

from src.discovery_probe import (
    DiscoveryProbe,
    _DiscoveryData,
    _HANDLE_GENERATION_SHIFT,
    _SCENE_NODE_POSITION_OFFSET,
    _SCENE_NODE_STATUS_LIVE,
    _SCENE_NODE_STORED_HANDLE_OFFSET,
    _SCENE_NODE_STRIDE,
    _build_fauna_discovery_data,
    _build_planet_object_discovery_data,
    _collect_scene_candidates,
    _djb2_64,
    _discovery_fingerprint,
    _normalise_scene_filename,
)
from src.planet_object_types import FLORA_SCENE_HASHES, MINERAL_SCENE_HASHES


class Stage5SceneResolverTests(unittest.TestCase):
    def _make_scene(self):
        capacity = 8
        generation = 5
        target_lookup = 2
        nearby_lookup = 4
        far_lookup = 6
        target_handle = (generation << _HANDLE_GENERATION_SHIFT) | target_lookup
        nearby_handle = (generation << _HANDLE_GENERATION_SHIFT) | nearby_lookup
        far_handle = (generation << _HANDLE_GENERATION_SHIFT) | far_lookup

        handle_map = bytearray(b"\xff" * (capacity * 4))
        generations = bytearray(capacity * 2)
        node_pointers = bytearray(capacity * 8)
        statuses = bytearray(capacity)
        transforms = bytearray(capacity * _SCENE_NODE_STRIDE)
        nodes: list[ctypes.Array] = []

        for lookup, dense, handle, position in (
            (target_lookup, 1, target_handle, (10.0, 20.0, 30.0)),
            (nearby_lookup, 3, nearby_handle, (13.0, 24.0, 30.0)),
            (far_lookup, 5, far_handle, (210.0, 20.0, 30.0)),
        ):
            node = ctypes.create_string_buffer(0x10)
            struct.pack_into("<I", node, _SCENE_NODE_STORED_HANDLE_OFFSET, handle)
            nodes.append(node)
            struct.pack_into("<i", handle_map, lookup * 4, dense)
            struct.pack_into("<H", generations, lookup * 2, generation)
            struct.pack_into("<Q", node_pointers, dense * 8, ctypes.addressof(node))
            statuses[dense] = _SCENE_NODE_STATUS_LIVE
            struct.pack_into(
                "<fff",
                transforms,
                dense * _SCENE_NODE_STRIDE + _SCENE_NODE_POSITION_OFFSET,
                *position,
            )

        return (
            target_handle,
            bytes(handle_map),
            bytes(generations),
            bytes(node_pointers),
            bytes(statuses),
            bytes(transforms),
            nodes,
        )

    def test_collects_exact_live_nodes_inside_radius(self) -> None:
        target, handle_map, generations, pointers, statuses, transforms, nodes = (
            self._make_scene()
        )

        def node_handle_reader(pointer: int) -> int | None:
            if not pointer:
                return None
            return ctypes.c_uint32.from_address(
                pointer + _SCENE_NODE_STORED_HANDLE_OFFSET
            ).value

        snapshot = _collect_scene_candidates(
            handle_map,
            generations,
            pointers,
            statuses,
            transforms,
            target_handle=target,
            radius_metres=100.0,
            node_handle_reader=node_handle_reader,
        )

        self.assertIsNone(snapshot.error)
        self.assertEqual(len(snapshot.candidates), 2)
        self.assertEqual(snapshot.candidates[0].handle, target)
        self.assertAlmostEqual(snapshot.candidates[1].distance, 5.0)
        self.assertEqual(snapshot.exact_live_entries, 3)
        self.assertTrue(nodes)  # Keep pointed-to memory alive through assertions.

    def test_rejects_stale_target_handle(self) -> None:
        target, handle_map, generations, pointers, statuses, transforms, nodes = (
            self._make_scene()
        )
        wrong_target = target + (1 << _HANDLE_GENERATION_SHIFT)
        snapshot = _collect_scene_candidates(
            handle_map,
            generations,
            pointers,
            statuses,
            transforms,
            target_handle=wrong_target,
            radius_metres=100.0,
            node_handle_reader=lambda pointer: target,
        )
        self.assertEqual(snapshot.error, "target_generation_mismatch")
        self.assertTrue(nodes)

    def test_collects_around_explicit_player_position_without_target(self) -> None:
        target, handle_map, generations, pointers, statuses, transforms, nodes = (
            self._make_scene()
        )

        snapshot = _collect_scene_candidates(
            handle_map,
            generations,
            pointers,
            statuses,
            transforms,
            target_handle=0,
            radius_metres=100.0,
            node_handle_reader=lambda pointer: (
                ctypes.c_uint32.from_address(
                    pointer + _SCENE_NODE_STORED_HANDLE_OFFSET
                ).value
                if pointer
                else None
            ),
            center_position=(10.0, 20.0, 30.0),
        )

        self.assertIsNone(snapshot.error)
        self.assertEqual(snapshot.target_handle, 0)
        self.assertEqual(snapshot.target_dense_index, -1)
        self.assertEqual([item.handle for item in snapshot.candidates], [target, target + 2])
        self.assertTrue(nodes)

    def test_discovery_fingerprint_matches_submit_three_key_identity(self) -> None:
        data = _DiscoveryData()
        data.universe_address = 123
        data.discovery_type = 3
        data.key_count = 5
        data.keys[0] = 10
        data.keys[1] = 20
        data.keys[2] = 30
        data.keys[3] = 40
        data.keys[4] = 50
        self.assertEqual(_discovery_fingerprint(data), (123, 3, (10, 20, 30)))

    def test_normalises_creature_resource_like_game_scene_helper(self) -> None:
        self.assertEqual(
            _normalise_scene_filename(
                "models/planets/creatures/cowrig/cow.scene.mbin"
            ),
            "MODELS/PLANETS/CREATURES/COWRIG/COW.SCENE.MBIN",
        )

    def test_planet_fauna_formula_matches_six_live_resolver_species(self) -> None:
        universe_address = 4750989879310688
        cases = (
            (
                "ANTELOPE",
                "MODELS/PLANETS/CREATURES/ANTELOPERIG/ANTELOPE.SCENE.MBIN",
                1106933841620129108,
                25,
                1,
                (
                    0x0F5C9E76D3A05554,
                    0x9C1C7E2EB0BBDE4C,
                    0xBDFDFD9F54E4BB19,
                    0x8D4B556CAD7BB4B0,
                ),
            ),
            (
                "TWOLEGANTELOPE",
                "MODELS/PLANETS/CREATURES/ANTELOPERIG/ANTELOPETWOLEGS.SCENE.MBIN",
                7807473944484480359,
                25,
                1,
                (
                    0x6C59B82FCE1D8567,
                    0x74A95B08E1290351,
                    0x0859A4BA867BECEB,
                    0x8D4B556CAD7BB4B0,
                ),
            ),
            (
                "COW",
                "MODELS/PLANETS/CREATURES/COWRIG/COW.SCENE.MBIN",
                4047585448039819114,
                26,
                1,
                (
                    0x382BE9851C74276A,
                    0x109BB757445D45AE,
                    0x4046B48FDF342A62,
                    0xD2CEA454B725A367,
                ),
            ),
            (
                "GRUNT",
                "MODELS/PLANETS/CREATURES/GRUNTRIG/GRUNT.SCENE.MBIN",
                4736351104495284947,
                26,
                2,
                (
                    0x41BAE63C3AF872D3,
                    0x45801FB6A851EF5C,
                    0xADCA4D99DF1AF2C8,
                    0x5357AEBB4D6AA48C,
                ),
            ),
            (
                "CAT",
                "MODELS/PLANETS/CREATURES/CATRIG/CAT.SCENE.MBIN",
                -6219337508137421380,
                23,
                1,
                (
                    0xA9B0797CE134B5BC,
                    0x9C5BED221D9CEC6C,
                    0x8132E8F78B660FFF,
                    0xDF77C410BC877D1D,
                ),
            ),
            (
                "BIRD",
                "MODELS/PLANETS/CREATURES/SMALLBIRD/BIRD.SCENE.MBIN",
                7566199673871198129,
                1,
                0,
                (
                    0x69008A8414C4E7B1,
                    0xE7CAD69E2F26FF55,
                    0x85FA0E45074870D1,
                    0x9E1E08700CAFA4AC,
                ),
            ),
        )
        for creature_id, filename, seed, creature_type, rarity, expected in cases:
            with self.subTest(creature_id=creature_id):
                data = _build_fauna_discovery_data(
                    universe_address,
                    creature_id,
                    filename,
                    seed,
                    creature_type,
                    rarity,
                )
                self.assertEqual(data.discovery_type, 3)
                self.assertEqual(data.key_count, 4)
                self.assertEqual(tuple(data.keys[:4]), expected)

    def test_planet_fauna_formula_matches_saved_bird_record(self) -> None:
        data = _build_fauna_discovery_data(
            0x307700F86B2103,
            "BIRD",
            "MODELS/PLANETS/CREATURES/SMALLBIRD/BIRD.SCENE.MBIN",
            0x8D08620B2F6DC419,
            1,
            1,
        )
        self.assertEqual(
            tuple(data.keys[:4]),
            (
                0x8D08620B2F6DC419,
                0xE7CAD69E2F26FF55,
                0x9F92335D36120E70,
                0x7E330F373BC014D3,
            ),
        )

    def test_planet_object_catalog_contains_global_flora_and_mineral_scenes(self) -> None:
        self.assertEqual(len(FLORA_SCENE_HASHES), 192)
        self.assertEqual(len(MINERAL_SCENE_HASHES), 188)
        self.assertFalse(FLORA_SCENE_HASHES & MINERAL_SCENE_HASHES)
        self.assertIn(
            _djb2_64(
                "MODELS/PLANETS/BIOMES/COMMON/PLANTS/SMALLPLANT.SCENE.MBIN"
            ),
            FLORA_SCENE_HASHES,
        )
        self.assertIn(
            _djb2_64(
                "MODELS/PLANETS/BIOMES/COMMON/ROCKS/MEDIUM/"
                "MEDIUMROCK.SCENE.MBIN"
            ),
            MINERAL_SCENE_HASHES,
        )

    def test_builds_planet_object_two_key_discovery(self) -> None:
        data = _build_planet_object_discovery_data(
            0x207700F86B2103,
            0x84E96F1DCE7194F0,
            0xE12E10484B8A7BED,
            4,
        )
        self.assertEqual(data.universe_address, 0x207700F86B2103)
        self.assertEqual(tuple(data.keys[:2]), (
            0x84E96F1DCE7194F0,
            0xE12E10484B8A7BED,
        ))
        self.assertEqual(data.key_count, 2)
        self.assertEqual(data.discovery_type, 4)

    def test_f8_without_target_queues_player_centred_pass(self) -> None:
        probe = DiscoveryProbe()
        probe.request_nearby_discovery_submit()
        self.assertEqual(probe._stage6_pending_sequence, 1)

    def test_f8_blocks_active_submit_then_allows_another_pass(self) -> None:
        probe = DiscoveryProbe()
        probe.request_nearby_discovery_submit()
        self.assertEqual(probe._stage6_pending_sequence, 1)
        probe._stage6_pending_sequence = 0
        probe._stage6_active_sequence = 1
        probe.request_nearby_discovery_submit()
        self.assertEqual(probe._stage6_pending_sequence, 0)
        self.assertEqual(probe._stage6_sequence, 1)
        probe._release_stage6_attempt()
        probe._stage6_last_request_time -= 11.0
        probe.request_nearby_discovery_submit()
        self.assertEqual(probe._stage6_pending_sequence, 2)
        self.assertEqual(probe._stage6_sequence, 2)

if __name__ == "__main__":
    unittest.main()
