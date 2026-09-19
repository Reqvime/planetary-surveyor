"""Read-only dump of the current planet's generated object spawn arrays."""

from __future__ import annotations

import ctypes
from pathlib import Path
import runpy

import discovery_probe as probe
import nmspy.data.exported_types as nmse


PROJECT_ROOT = Path(__file__).parents[1]


def _resource_tuple(source: str, index: int, resource) -> tuple[object, ...]:
    filename = str(resource.Filename).replace("\\", "/").upper()
    seed = int(resource.Seed.Seed) & 0xFFFFFFFFFFFFFFFF
    use_seed = int(resource.Seed.UseSeedValue)
    scene_hash = probe._djb2_64(filename) if filename else 0
    discovery_type = probe._SCENE_HASH_TYPES.get(scene_hash, 0)
    return source, index, filename, seed, use_seed, discovery_type


def main() -> dict[str, object]:
    module_base = probe._nms_module_base()
    addresses, error = probe._resolve_game_addresses(module_base)
    if addresses is None:
        raise RuntimeError(error)
    application_data = probe._read_u64(addresses.application_data_pointer)
    if not application_data:
        raise RuntimeError("application_data_unreadable")
    fauna = probe._read_current_planet_fauna_catalog(application_data)
    if fauna.error:
        raise RuntimeError(fauna.error)
    planet = ctypes.cast(
        fauna.planet_pointer + probe._PLANET_DATA_OFFSET,
        ctypes.POINTER(nmse.cGcPlanetData),
    ).contents
    spawn = planet.SpawnData
    entries: list[tuple[object, ...]] = []
    for source, values in (
        ("Objects", spawn.Objects),
        ("DetailObjects", spawn.DetailObjects),
        ("DistantObjects", spawn.DistantObjects),
        ("Landmarks", spawn.Landmarks),
    ):
        for index, item in enumerate(values):
            entries.append(_resource_tuple(source, index, item.Resource))
            for alt_index, resource in enumerate(item.AltResources):
                entries.append(
                    _resource_tuple(f"{source}[{index}].AltResources", alt_index, resource)
                )
    for list_index, selectable in enumerate(spawn.SelectableObjects):
        for index, item in enumerate(selectable.Objects):
            entries.append(
                _resource_tuple(f"SelectableObjects[{list_index}]", index, item.Resource)
            )
    return {
        "counts": {
            "Objects": len(spawn.Objects),
            "DetailObjects": len(spawn.DetailObjects),
            "DistantObjects": len(spawn.DistantObjects),
            "Landmarks": len(spawn.Landmarks),
            "SelectableObjects": len(spawn.SelectableObjects),
        },
        "entries": entries,
        "classified": [entry for entry in entries if entry[-1]],
        "unclassified": [entry for entry in entries if not entry[-1]],
    }


if __name__ == "__main__":
    main()
