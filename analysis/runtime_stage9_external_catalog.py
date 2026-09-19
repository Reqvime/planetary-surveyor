"""Read-only current-planet catalogue filtered by selected object-list files."""

from __future__ import annotations

import ctypes
from pathlib import Path
import runpy

import discovery_probe as probe


PROJECT_ROOT = Path(__file__).parents[1]


def main() -> dict[str, object]:
    external = runpy.run_path(
        PROJECT_ROOT / "analysis" / "runtime_stage9_external_lists.py"
    )["main"]()
    catalog = runpy.run_path(
        PROJECT_ROOT / "analysis" / "runtime_stage9_catalog.py"
    )["main"]()
    list_map = runpy.run_path(PROJECT_ROOT / "src" / "planet_object_lists.py")[
        "OBJECT_LIST_SCENE_HASHES"
    ]

    selected_lists = sorted(
        {
            option
            for entry in external["lists"]
            for option in entry["options"]
            if option
        }
    )
    missing_lists: list[str] = []
    allowed_hashes: set[int] = set()
    for filename in selected_lists:
        values = list_map.get(probe._djb2_64(filename))
        if values is None:
            missing_lists.append(filename)
            continue
        allowed_hashes.update(values)

    module_base = probe._nms_module_base()
    addresses, error = probe._resolve_game_addresses(module_base)
    if addresses is None:
        raise RuntimeError(error)
    application_data = probe._read_u64(addresses.application_data_pointer)
    if not application_data:
        raise RuntimeError("application_data_unreadable")
    planet = probe._read_current_planet_fauna_catalog(application_data)
    if planet.error:
        raise RuntimeError(planet.error)
    known_type = ctypes.CFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_uint64,
        ctypes.POINTER(probe._DiscoveryData),
    )
    is_known = known_type(addresses.is_known)
    lookup_context = application_data + probe._DISCOVERY_LOOKUP_CONTEXT_OFFSET

    entries: list[dict[str, object]] = []
    for index, seed, use_seed, ref_count, discovery_type, name in catalog["matches"]:
        scene_hash = probe._djb2_64(name)
        if scene_hash not in allowed_hashes:
            continue
        data = probe._build_planet_object_discovery_data(
            planet.universe_address, seed, scene_hash, discovery_type
        )
        entries.append(
            {
                "index": index,
                "seed": seed,
                "scene_hash": scene_hash,
                "ref_count": ref_count,
                "use_seed": use_seed,
                "type": discovery_type,
                "known": bool(is_known(lookup_context, ctypes.byref(data))),
                "name": name,
            }
        )

    by_seed: dict[int, list[dict[str, object]]] = {}
    for entry in entries:
        by_seed.setdefault(int(entry["seed"]), []).append(entry)
    duplicate_seeds = {
        seed: values for seed, values in by_seed.items() if len(values) > 1
    }
    return {
        "universe_address": planet.universe_address,
        "selected_list_count": len(selected_lists),
        "selected_lists": selected_lists,
        "missing_lists": missing_lists,
        "allowed_scene_count": len(allowed_hashes),
        "entries": entries,
        "entry_count": len(entries),
        "unique_seed_count": len(by_seed),
        "known_count": sum(bool(entry["known"]) for entry in entries),
        "unknown": [entry for entry in entries if not entry["known"]],
        "duplicate_seeds": duplicate_seeds,
    }


if __name__ == "__main__":
    main()
