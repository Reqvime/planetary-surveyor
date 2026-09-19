"""Read-only known-status summary for every matching resource cluster."""

from __future__ import annotations

import ctypes
from pathlib import Path
import runpy

import discovery_probe as probe


PROJECT_ROOT = Path(__file__).parents[1]


def main() -> list[dict[str, object]]:
    catalogue = runpy.run_path(PROJECT_ROOT / "analysis" / "runtime_stage9_catalog.py")[
        "main"
    ]()
    matches = catalogue["matches"]
    clusters: list[list[tuple[int, int, int, int, int, str]]] = []
    for match in matches:
        if not clusters or match[0] - clusters[-1][-1][0] > 256:
            clusters.append([])
        clusters[-1].append(match)

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
    is_known_type = ctypes.CFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_uint64,
        ctypes.POINTER(probe._DiscoveryData),
    )
    is_known = is_known_type(addresses.is_known)
    lookup_context = application_data + probe._DISCOVERY_LOOKUP_CONTEXT_OFFSET

    summaries: list[dict[str, object]] = []
    for cluster in clusters:
        counts = {
            "flora_known": 0,
            "flora_unknown": 0,
            "mineral_known": 0,
            "mineral_unknown": 0,
        }
        unknown_entries: list[tuple[int, int, int, str]] = []
        for index, seed, _use_seed, ref_count, discovery_type, name in cluster:
            scene_hash = probe._djb2_64(name)
            data = probe._build_planet_object_discovery_data(
                planet.universe_address, seed, scene_hash, discovery_type
            )
            known = bool(is_known(lookup_context, ctypes.byref(data)))
            type_name = "flora" if discovery_type == 4 else "mineral"
            counts[f"{type_name}_{'known' if known else 'unknown'}"] += 1
            if not known:
                unknown_entries.append((index, ref_count, discovery_type, name))
        summaries.append(
            {
                "range": (cluster[0][0], cluster[-1][0]),
                "entries": len(cluster),
                "active": sum(match[3] > 1 for match in cluster),
                **counts,
                "unknown_entries": unknown_entries,
            }
        )
    return summaries


if __name__ == "__main__":
    main()
